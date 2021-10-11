"""Defines the NI RRAM controller class"""
import glob
import json
import math
import time
import warnings
from os.path import abspath
import nidaqmx
import nidigital
import niscope
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
        self.addr = 0
        self.prof = {"READs": 0, "SETs": 0, "RESETs": 0}

        # Initialize NI-Digital driver
        self.digital = nidigital.Session(settings["NIDigital"]["deviceID"])
        self.digital.load_pin_map(settings["NIDigital"]["pinmap"])
        self.digital.load_specifications_levels_and_timing(*settings["NIDigital"]["specs"])
        self.digital.apply_levels_and_timing(*settings["NIDigital"]["specs"][1:])
        self.digital.unload_all_patterns()
        for pat in glob.glob(settings["NIDigital"]["patterns"]):
            print(pat)
            self.digital.load_pattern(abspath(pat))
        self.digital.burst_pattern("all_off")

        # Configure READ measurements
        if settings["READ"]["mode"] == "digital":
            # Configure NI-Digital current read measurements
            self.read_chan = self.digital.channels[settings["NIDigital"]["read_chan"]]
            self.read_chan.ppmu_aperture_time = settings["READ"]["aperture_time"]
            self.read_chan.ppmu_aperture_time_units = nidigital.PPMUApertureTimeUnits.SECONDS
            self.read_chan.ppmu_output_function = nidigital.PPMUOutputFunction.VOLTAGE
            self.read_chan.ppmu_current_limit_range = settings["READ"]["current_limit_range"]
            self.read_chan.ppmu_voltage_level = 0
            self.read_chan.ppmu_source()
        elif settings["READ"]["mode"] == "scope": 
            # Initialize NI-Scope driver for READ voltage
            self.scope = niscope.Session(settings["NIScope"]["deviceID"])
            self.read_chan = self.scope.channels[settings["NIScope"]["read_chan"]]
            self.read_chan.configure_vertical(
                range=5.0,
                coupling=niscope.VerticalCoupling.DC
            )
            self.scope.configure_horizontal_timing(
                min_sample_rate=settings["READ"]["read_rate"],
                min_num_pts=settings["READ"]["n_samples"],
                ref_position=0,
                num_records=settings["READ"]["n_records"],
                enforce_realtime=True
            )
        elif settings["READ"]["mode"] == "daqmx":
            # Initialize NI-DAQmx driver for READ voltage
            self.read_chan = nidaqmx.Task()
            self.read_chan.ai_channels.add_ai_voltage_chan(settings["DAQmx"]["chanMap"]["read_ai"])
            read_rate, spc = settings["READ"]["read_rate"], settings["READ"]["n_samples"]
            self.read_chan.timing.cfg_samp_clk_timing(read_rate, samps_per_chan=spc)
        else:
            raise NIRRAMException("Invalid READ mode specified in settings")

        # Set address and all voltages to 0
        self.set_addr(0)
        self.set_vwl(0)
        self.set_vbl(0)
        self.set_vsl(0)


    def read(self, allsamps=False):
        """Perform a READ operation. Returns tuple with (res, cond, meas_i, meas_v)"""
        # Increment the number of READs
        self.prof["READs"] += 1

        # Set voltages and settling time (pulse width)
        self.set_vsl(0)
        self.set_vbl(self.settings["READ"]["VBL"])
        self.set_vwl(self.settings["READ"]["VWL"])
        self.set_pw(self.settings["READ"]["settling_time"])

        # Measure
        if self.settings["READ"]["mode"] == "digital":
            # Measure with NI-Digital
            self.read_chan.selected_function = nidigital.SelectedFunction.PPMU
            self.read_chan.ppmu_source()
            self.digital.burst_pattern("read_on_nosl") # just for timing
            meas_v = 0
            meas_i = -self.read_chan.ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)[0]
            self.read_chan.selected_function = nidigital.SelectedFunction.DIGITAL
        elif self.settings["READ"]["mode"] == "scope":
            # Enable READ waveform
            self.digital.burst_pattern("read_on")
            # Measure with NI-Scope
            with self.scope.initiate():
                waveforms = self.read_chan.fetch(num_records=self.settings["READ"]["n_records"])
            samples = np.array([sample for waveform in waveforms for sample in waveform.samples])
            meas_v = np.mean(samples) - self.settings["READ"]["voltage_offset"] if not allsamps else samples
            meas_i = meas_v/self.settings["READ"]["gain"]/self.settings["READ"]["shunt_res_value"]
        elif self.settings["READ"]["mode"] == "daqmx":
            # Enable READ waveform
            self.digital.burst_pattern("read_on")
            # Measure with NI-DAQmx
            self.read_chan.start()
            meas_v = self.read_chan.read(self.settings["READ"]["n_samples"])
            meas_v = np.mean(meas_v) if not allsamps else np.array(meas_v)
            self.read_chan.wait_until_done()
            self.read_chan.stop()
            meas_i = meas_v/self.settings["READ"]["shunt_res_value"]
        else:
            raise NIRRAMException("Invalid READ mode specified in settings")

        # Compute values
        res = np.abs(self.settings["READ"]["VBL"]/meas_i - self.settings["READ"]["shunt_res_value"])
        cond = 1/res

        # Disable READ waveform
        self.digital.burst_pattern("all_off")

        # Log operation to master file
        self.mlogfile.write(f"{self.chip},{time.time()},{self.addr},")
        self.mlogfile.write(f"READ,{res},{cond},{meas_i},{meas_v}\n")

        # Return measurement tuple
        if allsamps:
            return res, cond, meas_i, meas_v, waveforms[0].x_increment
        else:
            return res, cond, meas_i, meas_v

    def form_pulse(self, vwl=None, vbl=None, pulse_width=None):
        """Perform a FORM operation."""
        # Get parameters
        vwl = self.settings["FORM"]["VWL"] if vwl is None else vwl
        vbl = self.settings["FORM"]["VBL"] if vbl is None else vbl
        pulse_width = self.settings["FORM"]["PW"] if pulse_width is None else pulse_width

        # Operation is equivalent to SET but with different parameters
        self.set_pulse(vwl, vbl, pulse_width)

    def set_pulse(self, vwl=None, vbl=None, pulse_width=None):
        """Perform a SET operation."""
        # Get parameters
        vwl = self.settings["SET"]["VWL"] if vwl is None else vwl
        vbl = self.settings["SET"]["VBL"] if vbl is None else vbl
        pulse_width = self.settings["SET"]["PW"] if pulse_width is None else pulse_width

        # Increment the number of SETs
        self.prof["SETs"] += 1

        # Set voltages
        self.set_vsl(0)
        self.set_vbl(vbl)
        self.set_vwl(vwl)

        # Pulse VWL
        self.pulse_vwl(pulse_width)

        # Log the pulse
        self.mlogfile.write(f"{self.chip},{time.time()},{self.addr},")
        self.mlogfile.write(f"SET,{vwl},{vbl},0,{pulse_width}\n")

    def reset_pulse(self, vwl=None, vsl=None, pulse_width=None):
        """Perform a RESET operation."""
        # Get parameters
        vwl = self.settings["RESET"]["VWL"] if vwl is None else vwl
        vsl = self.settings["RESET"]["VSL"] if vsl is None else vsl
        pulse_width = self.settings["RESET"]["PW"] if pulse_width is None else pulse_width

        # Increment the number of SETs
        self.prof["RESETs"] += 1

        # Set voltages
        self.set_vbl(0, other=vsl)
        self.set_vsl(vsl)
        self.set_vwl(vwl)

        # Pulse VWL
        self.pulse_vwl(pulse_width)

        # Log the pulse
        self.mlogfile.write(f"{self.chip},{time.time()},{self.addr},")
        self.mlogfile.write(f"RESET,{vwl},0,{vsl},{pulse_width}\n")


    def set_vsl(self, voltage):
        """Set VSL using NI-Digital driver"""
        assert(voltage <= 5)
        assert(voltage >= 0)
        sl_ext_chan = "sl_ext" if "test_struct" not in self.settings else "test_bottom_2"
        self.digital.channels[sl_ext_chan].configure_voltage_levels(0, voltage, 0, voltage, 0)

    def set_vbl(self, voltage, other=0):
        """Set (active) VBL using NI-Digital driver (inactive disabled)"""
        assert(voltage <= 5)
        assert(voltage >= 0)
        active_bl_chan = (self.addr >> 0) & 0b1 if self.settings["multi_bl_wl"] else 0
        for i in range(2 if self.settings["multi_bl_wl"] else 1):
            vhi = voltage if i == active_bl_chan else other
            bl_ext_chan = f"bl_ext_{i}" if "test_struct" not in self.settings else f"test_bottom_{i}"
            self.digital.channels[bl_ext_chan].configure_voltage_levels(0, vhi, 0, vhi, 0)


    def set_vwl(self, voltage_hi, voltage_lo=0):
        """Set (active) VWL using NI-Digital driver (inactive disabled)"""
        # Assertions
        assert(voltage_hi <= 4)
        assert(voltage_hi >= 0)
        assert(voltage_lo <= 4)
        assert(voltage_lo >= 0)
        
        wl_shift = 8 if "test_struct" not in self.settings else 1
        active_wl_chan = (self.addr >> wl_shift) & 0b11 if self.settings["multi_bl_wl"] else 0
        for i in range(4 if self.settings["multi_bl_wl"] else 1):
            vhi = voltage_hi if i == active_wl_chan else 0
            vlo = voltage_lo if i == active_wl_chan else 0
            wl_ext_chan = "wl_ext" if "test_struct" not in self.settings else "test_left"
            self.digital.channels[f"{wl_ext_chan}_{i}"].configure_voltage_levels(vlo, vhi, vlo, vhi, 0)

    def set_addr(self, addr):
        """Set the address"""
        # Update address
        self.addr = addr

        # Configure waveform
        if "test_struct" not in self.settings:
            broadcast = nidigital.SourceDataMapping.BROADCAST
            self.digital.pins["addr"].create_source_waveform_parallel("addr_waveform", broadcast)
            self.digital.write_source_waveform_broadcast("addr_waveform", [addr])
            self.digital.burst_pattern("load_addr")

        # Reset profiling counters
        self.prof = {"READs": 0, "SETs": 0, "RESETs": 0}

    def set_pw(self, pulse_width):
        """Set pulse width"""
        pw_register = nidigital.SequencerRegister.REGISTER0
        self.digital.write_sequencer_register(pw_register, int(round(pulse_width/20e-9)))

    def set_endurance_cycles(self, cycles):
        """Set number of endurance cycles"""
        cycle_register = nidigital.SequencerRegister.REGISTER1
        self.digital.write_sequencer_register(cycle_register, cycles)

    def pulse_vwl(self, pulse_width):
        """Pulse (active) VWL using NI-Digital driver (inactive are off)"""
        self.set_pw(pulse_width)
        self.digital.burst_pattern("pulse_wl")

    def dynamic_form(self, target_res=10000):
        """Performs SET pulses in increasing fashion until resistance reaches target_res.
        Returns tuple (res, cond, meas_i, meas_v, success)."""
        return self.dynamic_set(target_res, scheme="FORM")

    def dynamic_set(self, target_res, scheme="PINGPONG"):
        """Performs SET pulses in increasing fashion until resistance reaches target_res.
        Returns tuple (res, cond, meas_i, meas_v, success)."""
        # Get settings
        cfg = self.settings[scheme]

        # Iterative pulse-verify
        success = False
        for vwl in np.arange(cfg["VWL_SET_start"], cfg["VWL_SET_stop"], cfg["VWL_SET_step"]):
            for vbl in np.arange(cfg["VBL_start"], cfg["VBL_stop"], cfg["VBL_step"]):
                self.set_pulse(vwl, vbl, cfg["SET_PW"])
                res, cond, meas_i, meas_v = self.read()
                if res <= target_res:
                    success = True
                    break
            if success:
                break

        # Return results
        return res, cond, meas_i, meas_v, success

    def dynamic_reset(self, target_res, scheme="PINGPONG"):
        """Performs RESET pulses in increasing fashion until resistance reaches target_res.
        Returns tuple (res, cond, meas_i, meas_v, success)."""
        # Get settings
        cfg = self.settings[scheme]

        # Iterative pulse-verify
        success = False
        for vwl in np.arange(cfg["VWL_RESET_start"], cfg["VWL_RESET_stop"], cfg["VWL_RESET_step"]):
            for vsl in np.arange(cfg["VSL_start"], cfg["VSL_stop"], cfg["VSL_step"]):
                self.reset_pulse(vwl, vsl, cfg["RESET_PW"])
                res, cond, meas_i, meas_v = self.read()
                if res >= target_res:
                    success = True
                    break
            if success:
                break

        # Return results
        return res, cond, meas_i, meas_v, success

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

        # Close voltage READ equipment
        if self.settings["READ"]["mode"] == "scope":
            # Close NI-Scope
            self.scope.close()
        elif self.settings["READ"]["mode"] == "daqmx":
            # Close NI-DAQmx AI
            self.read_chan.close()

        # Close log files
        self.mlogfile.close()
        self.plogfile.close()


if __name__ == "__main__":
    # Basic test
    nirram = NIRRAM("C4")
    nirram.close()
