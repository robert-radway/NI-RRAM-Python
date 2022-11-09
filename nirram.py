"""Defines the NI RRAM controller class"""
import glob
import json
import math
import time
import warnings
from os.path import abspath
import nidigital
import numpy as np


# Warnings become errors
warnings.filterwarnings("error")


class NIRRAMException(Exception):
    """Exception produced by the NIRRAM class"""
    def __init__(self, msg):
        super().__init__(f"NIRRAM: {msg}")


class NIRRAM:
    """The NI RRAM controller class that controls the instrument drivers."""
    def __init__(self, chip, settings="settings/default.json"):
        # If settings is a string, load as JSON file
        if isinstance(settings, str):
            with open(settings) as settings_file:
                settings = json.load(settings_file)

        # Ensure settings is a dict
        if not isinstance(settings, dict):
            raise NIRRAMException(f"Settings should be a dict, got {repr(settings)}.")

        # Convert NIDigital spec paths to absolute paths
        settings["NIDigital"]["specs"] = [abspath(path) for path in settings["NIDigital"]["specs"]]

        # Initialize RRAM logging
        self.mlogfile = open(settings["master_log_file"], "a")
        self.plogfile = open(settings["prog_log_file"], "a")

        # Store/initialize parameters
        self.settings = settings
        self.chip = chip
        self.bls = settings["BLS"]
        self.sls = settings["SLS"]
        self.wls = settings["WLS"]

        # Only works for 1T1R arrays
        self.addr_idxs = {}
        self.addr_prof = {}
        for wl in self.wls:
            self.addr_idxs[wl] = {}
            self.addr_prof[wl] = {}
            for i in range(len(self.bls)):
                bl = self.bls[i]
                sl = self.sls[i]
                self.addr_idxs[wl][bl] = (bl, sl, wl)
                self.addr_prof[wl][bl] = {"FORMs": 0, "READs": 0, "SETs": 0, "RESETs": 0} 

        # Initialize NI-Digital driver
        self.digital = nidigital.Session(settings["NIDigital"]["deviceID"])
        self.digital.load_pin_map(settings["NIDigital"]["pinmap"])
        self.digital.load_specifications_levels_and_timing(*settings["NIDigital"]["specs"])
        self.digital.apply_levels_and_timing(*settings["NIDigital"]["specs"][1:])
        self.digital.unload_all_patterns()
        for pattern in glob.glob(settings["NIDigital"]["patterns"]):
            print(pattern)
            self.digital.load_pattern(abspath(pattern))

        # Configure READ measurements
        if settings["READ"]["mode"] == "digital":
            for bl in self.bls:
                # Configure NI-Digital current read measurements
                self.digital.channels[bl].ppmu_aperture_time = settings["READ"]["aperture_time"]
                self.digital.channels[bl].ppmu_aperture_time_units = nidigital.PPMUApertureTimeUnits.SECONDS
                self.digital.channels[bl].ppmu_output_function = nidigital.PPMUOutputFunction.VOLTAGE
                self.digital.channels[bl].ppmu_current_limit_range = settings["READ"]["current_limit_range"]
                self.digital.channels[bl].ppmu_voltage_level = 0
                self.digital.channels[bl].ppmu_source()
            for sl in self.sls:
                # Configure NI-Digital current read measurements
                self.digital.channels[sl].ppmu_aperture_time = settings["READ"]["aperture_time"]
                self.digital.channels[sl].ppmu_aperture_time_units = nidigital.PPMUApertureTimeUnits.SECONDS
                self.digital.channels[sl].ppmu_output_function = nidigital.PPMUOutputFunction.VOLTAGE
                self.digital.channels[sl].ppmu_current_limit_range = settings["READ"]["current_limit_range"]
                self.digital.channels[sl].ppmu_voltage_level = 0
                self.digital.channels[sl].ppmu_source()
        else:
            raise NIRRAMException("Invalid READ mode specified in settings")

        # Set address and all voltages to 0
        for bl in self.bls: self.set_vbl(bl,0)
        for sl in self.sls: self.set_vsl(sl,0)
        for wl in self.wls: self.set_vwl(wl,0)



    def read(self, vbl=None, vsl=None, vwl=None):
        """Perform a READ operation. Returns list (per-bitline) of tuple with (res, cond, meas_i, meas_v)"""
        # Increment the number of READs
        # Set voltages and settling time (pulse width)
        self.digital_all_off(100)
        vbl = self.settings["READ"]["VBL"] if vbl is None else vbl
        vwl = self.settings["READ"]["VWL"] if vwl is None else vwl
        vsl = 0 if vsl is None else vsl
        for bl in self.bls: 
            self.ppmu_set_vbl(bl,vbl)
            self.digital.channels[bl].selected_function = nidigital.SelectedFunction.PPMU
        for sl in self.sls: 
            self.ppmu_set_vsl(sl,0)
            self.digital.channels[sl].selected_function = nidigital.SelectedFunction.PPMU
        for wl in self.wls: 
            self.ppmu_set_vwl(wl,vwl)
            self.digital.channels[wl].selected_function = nidigital.SelectedFunction.PPMU

        self.digital.ppmu_source()
        #self.set_pw(self.settings["READ"]["settling_time"])
        measurement = []
        time.sleep(1e-6)
        # self.pulse(bl_mask =0b1111, sl_mask=0b1111, wl_mask=0b1111, pulse_len=self.settings["READ"]["settling_time"])
        # Measure
        if self.settings["READ"]["mode"] == "digital":
            # Measure with NI-Digital
            for wl in self.wls:
                for bl in self.bls:
                    meas_v = self.digital.channels[bl].ppmu_measure(nidigital.PPMUMeasurementType.VOLTAGE)[0]
                    meas_i = self.digital.channels[bl].ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)[0]
                    #self.digital.channels[bl].selected_function = nidigital.SelectedFunction.DIGITAL
                    self.addr_prof[wl][bl]["READs"] +=1
                    # Compute values
                    res = np.abs(self.settings["READ"]["VBL"]/meas_i - self.settings["READ"]["shunt_res_value"])
                    cond = 1/res
                    measurement.append((res, cond, meas_i, meas_v))
        else:
            raise NIRRAMException("Invalid READ mode specified in settings")


        # Disable READ waveform
        #self.digital_all_off()

        # # Log operation to master file
        # self.mlogfile.write(f"{self.chip},{time.time()},{self.addr},")
        # self.mlogfile.write(f"READ,{res},{cond},{meas_i},{meas_v}\n")

        # Return measurement tuple
        return measurement

    def form_pulse(self, wl_mask=0b1111, bl_mask=0b1111, vwl=None, vbl=None, pulse_len=None):
        """Perform a FORM operation."""
        # Get parameters
        vwl = self.settings["FORM"]["VWL"] if vwl is None else vwl
        vbl = self.settings["FORM"]["VBL"] if vbl is None else vbl
        pulse_len = self.settings["FORM"]["PW"] if pulse_len is None else pulse_len

        # Operation is equivalent to SET but with different parameters
        self.set_pulse(wl_mask, bl_mask, vwl, vbl, pulse_len)

    def set_pulse(self, wl_mask=0b1111, bl_mask=0b1111, vwl=None, vbl=None, pulse_len=None):
        """Perform a SET operation."""
        # Get parameters
        vwl = self.settings["SET"]["VWL"] if vwl is None else vwl
        vbl = self.settings["SET"]["VBL"] if vbl is None else vbl
        pulse_len = self.settings["SET"]["PW"] if pulse_len is None else pulse_len

        # Increment the number of SETs
        #self.prof["SETs"] += 1

        # Set voltages
        for bl in self.bls: self.set_vbl(bl, vbl)
        for sl in self.sls: self.set_vsl(sl, 0)
        for wl in self.wls: self.set_vwl(wl, vwl)
        
        # Pulse WL
        self.pulse(bl_mask=bl_mask, wl_mask=wl_mask, pulse_len=pulse_len)
        # Log the pulse
        #self.mlogfile.write(f"{self.chip},{time.time()},{self.addr},")
        #self.mlogfile.write(f"SET,{vwl},{vbl},0,{pulse_width}\n")

    def reset_pulse(self, wl_mask=0b1111, sl_mask=0b1111, vwl=None, vsl=None, pulse_len=None):
        """Perform a RESET operation."""
        # Get parameters
        vwl = self.settings["RESET"]["VWL"] if vwl is None else vwl
        vsl = self.settings["RESET"]["VSL"] if vsl is None else vsl
        pulse_len = self.settings["RESET"]["PW"] if pulse_len is None else pulse_len

        # Increment the number of SETs
        #self.prof["RESETs"] += 1

        # Set voltages
        for bl in self.bls: self.set_vbl(bl, 0)
        for sl in self.sls: self.set_vsl(sl, vsl)
        for wl in self.wls: self.set_vwl(wl, vwl)

        self.pulse(sl_mask=sl_mask, wl_mask=wl_mask, pulse_len=pulse_len)

        # Log the pulse
        #self.mlogfile.write(f"{self.chip},{time.time()},{self.addr},")
        #self.mlogfile.write(f"RESET,{vwl},0,{vsl},{pulse_width}\n")

    def set_vsl(self, vsl_chan, vsl):
        """Set VSL using NI-Digital driver"""
        assert(vsl <= 5)
        assert(vsl >= 0)
        assert(vsl_chan in self.sls)
        self.digital.channels[vsl_chan].configure_voltage_levels(0, vsl, 0, vsl, 0)
        #print("Setting VSL: " + str(vsl) + " on chan: " + str(vsl_chan))

    def set_vbl(self, vbl_chan, vbl):
        """Set (active) VBL using NI-Digital driver (inactive disabled)"""
        assert(vbl <= 3.5)
        assert(vbl >= 0)
        assert(vbl_chan in self.bls)
        self.digital.channels[vbl_chan].configure_voltage_levels(0, vbl, 0, vbl, 0)

    def set_vwl(self, vwl_chan, vwl_hi, vwl_lo=0):
        """Set (active) VWL using NI-Digital driver (inactive disabled)"""
        # Assertions
        assert(vwl_hi <= 2.5)
        assert(vwl_hi >= 0)
        assert(vwl_lo <= 2.5)
        assert(vwl_lo >= 0)
        assert(vwl_chan in self.wls)
        self.digital.channels[vwl_chan].configure_voltage_levels(vwl_lo, vwl_hi, vwl_lo, vwl_hi, 0)

    def ppmu_set_vsl(self, vsl_chan, vsl):
        """Set VSL using NI-Digital driver"""
        assert(vsl <= 6)
        assert(vsl >= -2)
        assert(vsl_chan in self.sls)
        self.digital.channels[vsl_chan].ppmu_voltage_level = vsl
        #print("Setting VSL: " + str(vsl) + " on chan: " + str(vsl_chan))

    def ppmu_set_vbl(self, vbl_chan, vbl):
        """Set (active) VBL using NI-Digital driver (inactive disabled)"""
        assert(vbl <= 6)
        assert(vbl >= -2)
        assert(vbl_chan in self.bls)
        self.digital.channels[vbl_chan].ppmu_voltage_level = vbl

    def ppmu_set_vwl(self, vwl_chan, vwl):
        """Set (active) VWL using NI-Digital driver (inactive disabled)"""
        # Assertions
        assert(vwl <= 6)
        assert(vwl >= -2)
        assert(vwl_chan in self.wls)
        self.digital.channels[vwl_chan].ppmu_voltage_level = vwl

    def digital_all_off(self, pulse_len=1):
        self.pulse(pulse_len=pulse_len, prepulse_len=0, postpulse_len=0)

    def pulse(self, bl_mask = 0b0000, sl_mask = 0b0000, wl_mask = 0b0000, pulse_len=10, prepulse_len=2, postpulse_len=2, max_waveform_len=2000):
        """Pass wl data to the pulse train"""
        data_prepulse = (bl_mask << 8) + (sl_mask << 4) 
        data = (bl_mask << 8) + (sl_mask << 4) + wl_mask
        data_postpulse = (bl_mask << 8) + (sl_mask << 4)
        waveform = [data_prepulse for i in range(prepulse_len)] + [data for i in range(pulse_len)] + [data_postpulse for i in range(postpulse_len)] + [0 for i in range(max_waveform_len-pulse_len-prepulse_len-postpulse_len)]
        # Configure waveform
        #print(waveform)
        broadcast = nidigital.SourceDataMapping.BROADCAST
        self.digital.pins["BLSLWLS"].create_source_waveform_parallel("wl_data", broadcast)
        self.digital.write_source_waveform_broadcast("wl_data", waveform)
        self.set_pw(pulse_len+prepulse_len+postpulse_len)
        self.digital.burst_pattern("WL_PULSE_DEC3")

    def set_pw(self, pulse_width):
        """Set pulse width"""
        pw_register = nidigital.SequencerRegister.REGISTER0
        self.digital.write_sequencer_register(pw_register, pulse_width)

    def set_endurance_cycles(self, cycles):
        """Set number of endurance cycles"""
        cycle_register = nidigital.SequencerRegister.REGISTER1
        self.digital.write_sequencer_register(cycle_register, cycles)

    def dynamic_form(self):
        """Performs SET pulses in increasing fashion until resistance reaches target_res.
        Returns tuple (res, cond, meas_i, meas_v, success)."""
        return self.dynamic_set(mode="FORM")

    def dynamic_set(self, mode="SET"):
        """Performs SET pulses in increasing fashion until resistance reaches target_res.
        Returns tuple (res, cond, meas_i, meas_v, success)."""
        # Get settings
        cfg = self.settings[mode]
        target_res = self.settings["TARGETS"][mode]
        # Iterative pulse-verify
        success = False
        for pw in np.logspace(int(np.log10(cfg["PW_start"])), int(np.log10(cfg["PW_stop"])), cfg["PW_steps"]):
            for vwl in np.arange(cfg["VWL_SET_start"], cfg["VWL_SET_stop"], cfg["VWL_SET_step"]):
                for vbl in np.arange(cfg["VBL_start"], cfg["VBL_stop"], cfg["VBL_step"]):
                    #print(pw,vwl,vbl)
                    self.set_pulse(vbl=vbl, vwl=vwl, pulse_len=int(pw))
                    res, cond, meas_i, meas_v = self.read()[0]
                    if res <= target_res:
                        success = True
                        break
                if success:
                    break
            if success:
                break
        # Return results
        return res, cond, meas_i, meas_v, success, vwl, vbl, pw

    def dynamic_reset(self, mode="RESET"):
        """Performs RESET pulses in increasing fashion until resistance reaches target_res.
        Returns tuple (res, cond, meas_i, meas_v, success)."""
        # Get settings
        cfg = self.settings[mode]
        target_res = self.settings["TARGETS"][mode]
        # Iterative pulse-verify
        success = False
        for pw in np.logspace(int(np.log10(cfg["PW_start"])), int(np.log10(cfg["PW_stop"])), cfg["PW_steps"]):
            for vwl in np.arange(cfg["VWL_RESET_start"], cfg["VWL_RESET_stop"], cfg["VWL_RESET_step"]):
                for vsl in np.arange(cfg["VSL_start"], cfg["VSL_stop"], cfg["VSL_step"]):
                    #print(pw,vwl,vsl)
                    self.reset_pulse(vsl=vsl, vwl=vwl, pulse_len=int(pw))
                    res, cond, meas_i, meas_v = self.read()[0]
                    if res >= target_res:
                        success = True
                        break
                if success:
                    break
            if success:
                break
        # Return results
        return res, cond, meas_i, meas_v, success, vwl, vsl, pw

    def target(self, target_res_lo, target_res_hi, scheme="PINGPONG", max_attempts=25, debug=True):
        """Performs SET/RESET pulses in increasing fashion until target range is achieved.
        Returns tuple (res, cond, meas_i, meas_v, attempt, success)."""
        # Assert the resistance is greater than 6kOhm
        assert(target_res_lo >= 6000)
        assert(target_res_hi >= target_res_lo)

        # Iterative pulse-verify
        success = False
        for attempt in range(max_attempts):
            res, cond, meas_i, meas_v = self.read()
            if debug:
                print("ATTEMPT", attempt)
                print("RES", res)
            if res > target_res_hi:
                if debug:
                    print("DYNSET", res)
                res, cond, meas_i, meas_v, _ = self.dynamic_set(target_res_hi, scheme)
            if res < target_res_lo:
                if debug:
                    print("DYNRESET", res)
                res, cond, meas_i, meas_v, _ = self.dynamic_reset(target_res_lo, scheme)
            if target_res_lo <= res <= target_res_hi:
                success = True
                break

        # Log results
        self.plogfile.write(f"{self.addr},{self.chip},{scheme},")
        self.plogfile.write(f"{target_res_lo},{target_res_hi},{res},")
        self.plogfile.write(f"{self.prof['READs']},{self.prof['SETs']},{self.prof['RESETs']},")
        self.plogfile.write(f"{success}\n")

        # Return results
        return res, cond, meas_i, meas_v, attempt, success

    def target_g(self, target_g_lo, target_g_hi, scheme="PINGPONG", max_attempts=25, debug=True):
        """Performs SET/RESET pulses in increasing fashion until target range is achieved.
        Returns tuple (res, cond, meas_i, meas_v, attempt, success)."""
        self.target(1/target_g_hi, 1/target_g_lo, scheme, max_attempts, debug)

    def endurance(self, cycs=1000, read_cycs=None, pulse_width=None, reset_first=True, debug=True):
        """Do endurance cycle testing. Parameter read_cycs is number of cycles after which
        to measure one cycle (default: never READ)"""
        # Configure pulse width and cycle counts
        read_cycs = int(min(read_cycs if read_cycs is not None else 1e15, cycs))
        pulse_width = self.settings["SET"]["PW"] if pulse_width is None else pulse_width
        self.set_pw(pulse_width)
        self.set_endurance_cycles(read_cycs)

        # Initialize return data
        data = []

        # Iterate to do cycles
        for cyc in range(int(math.ceil(cycs/read_cycs))):
            # Configure endurance voltages
            vbl = self.settings["SET"]["VBL"]
            vwl = self.settings["RESET"]["VWL"], self.settings["SET"]["VWL"]
            vsl = self.settings["RESET"]["VSL"]
            self.set_vbl(vbl)
            self.set_vwl(*vwl)
            self.set_vsl(vsl)

            # Run endurance waveform
            if reset_first:
                self.digital.burst_pattern("endurance_reset_first")
            else:
                self.digital.burst_pattern("endurance_set_first")

            # Log the endurance cycles
            self.mlogfile.write(f"{self.chip},{time.time()},{self.addr},")
            self.mlogfile.write(f"ENDURANCE,{vwl},{vbl},{vsl},{pulse_width},{read_cycs}\n")

            # Cycle manually, read, record
            if reset_first:
                self.reset_pulse()
                resetread = self.read()
                self.set_pulse()
                setread = self.read()
                data.append(((cyc+1)*read_cycs, resetread, setread))
            else:
                self.set_pulse()
                setread = self.read()
                self.reset_pulse()
                resetread = self.read()
                data.append(((cyc+1)*read_cycs, setread, resetread))

            # Debugging print statements
            if debug:
                print(((cyc+1)*read_cycs, setread, resetread))

        # Return endurance results
        return data


    def close(self):
        """Close all NI sessions"""
        # Close NI-Digital
        self.digital.close()

        # Close log files
        self.mlogfile.close()
        self.plogfile.close()


if __name__ == "__main__":
    # Basic test
    nirram = NIRRAM("C4")
    nirram.close()
