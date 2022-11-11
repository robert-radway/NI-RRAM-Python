"""Defines the NI RRAM controller class"""
import glob
import json
import math
import time
import warnings
from os.path import abspath
import nidigital
import numpy as np
import pandas as pd
import csv
from datetime import datetime
from BitVector import BitVector

# Warnings become errors
warnings.filterwarnings("error")


class RRAMArrayMaskException(Exception):
    """Exception produced by the ArrayMask class"""
    def __init__(self, msg):
        super().__init__(f"ArrayMask: {msg}")

class NIRRAMException(Exception):
    """Exception produced by the NIRRAM class"""
    def __init__(self, msg):
        super().__init__(f"NIRRAM: {msg}")

class RRAMArrayMask:
    def __init__(self, wls, bls, sls, all_wls, all_bls, all_sls, polarity, init_state=None):
        #Indicates Mask of bits that need further programming
        if len(bls) == len(sls):
            if init_state is None:
                self.mask = pd.DataFrame(np.array([[(bl in bls) and (wl in wls) for bl in all_bls] for wl in all_wls]), all_wls, all_bls)
            else: self.mask = init_state
            self.wls = wls
            self.bls = bls
            self.sls = sls
            self.polarity = polarity
        else: raise RRAMArrayMaskException("1TNR Operations Not Supported")
    
    def get_pulse_masks(self):
        masks = []
        needed_wls = self.mask[self.mask.apply(np.sum,axis=1).ge(1)]
        for wl in needed_wls.index:
            wl_mask = self.mask.index == wl
            bl_mask = pd.Series.to_numpy(needed_wls.loc[wl])
            sl_mask = bl_mask & False
            masks.append((wl_mask, bl_mask, sl_mask))
        return masks

    def update_mask(self, failing):
        self.mask = failing

class NIRRAM:
    """The NI RRAM controller class that controls the instrument drivers."""
    def __init__(self, chip, device, polarity = "NMOS", settings="settings/default.json"):
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
        self.datafile_path = settings["data_header"] + datetime.now().strftime("%Y%m%d-%H%M%S") + "_" + str(chip) + "_" + str(device) + ".csv"
        self.datafile = csv.writer(open(self.datafile_path, "a", newline=''))

        self.datafile.writerow(["Chip_ID", "Device_ID", "OP", "Row", "Col", "Res", "Cond", "Meas_I", "Meas_V", "Prog_VBL", "Prog_VSL", "Prog_VWL", "Prog_Pulse", "Success"])

        # Store/initialize parameters
        self.settings = settings
        self.chip = chip
        self.device = device

        self.polarity = polarity
        
        self.wls = settings["WLS"]
        self.bls = settings["BLS"]
        self.sls = settings["SLS"]
        self.body = settings["BODY"]

        self.all_wls = settings["all_WLS"]
        self.all_bls = settings["all_BLS"]
        self.all_sls = settings["all_SLS"]

        self.all_off_mask = RRAMArrayMask(self.all_wls, [], [], self.all_wls, self.all_bls, self.all_sls, self.polarity)

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



    def read(self, vbl=None, vsl=None, vwl=None, vb=None, record=False):
        """Perform a READ operation. Returns list (per-bitline) of tuple with (res, cond, meas_i, meas_v)"""
        # Increment the number of READs
        # Let the cell relax after programming to get an accurate read 
        self.digital_all_off(self.settings["READ"]["relaxation_cycles"])
        
        # Set the read voltage levels
        vbl = self.settings["READ"][self.polarity]["VBL"] if vbl is None else vbl
        vwl = self.settings["READ"][self.polarity]["VWL"] if vwl is None else vwl
        vsl = self.settings["READ"][self.polarity]["VSL"] if vsl is None else vsl
        vb = self.settings["READ"][self.polarity]["VB"] if vb is None else vb

        for bl in self.bls: 
            self.ppmu_set_vbl(bl,vbl)
            self.digital.channels[bl].selected_function = nidigital.SelectedFunction.PPMU
        for sl in self.sls: 
            self.ppmu_set_vsl(sl,vsl)
            self.digital.channels[sl].selected_function = nidigital.SelectedFunction.PPMU
        for wl in self.wls: 
            self.ppmu_set_vwl(wl,vwl)
            self.digital.channels[wl].selected_function = nidigital.SelectedFunction.PPMU
        for b in self.body: 
            assert( -2 <= vb <= 6)
            self.digital.channels[b].ppmu_voltage_level = vb
            self.digital.channels[b].selected_function = nidigital.SelectedFunction.PPMU

        self.digital.ppmu_source()
        time.sleep(self.settings["READ"]["settling_time"]) #Let the supplies settle for accurate measurement
        
        # Measure
        res_array = pd.DataFrame(np.zeros((len(self.wls), len(self.bls))), self.wls, self.bls)
        cond_array = pd.DataFrame(np.zeros((len(self.wls), len(self.bls))), self.wls, self.bls)
        meas_i_array = pd.DataFrame(np.zeros((len(self.wls), len(self.bls))), self.wls, self.bls)
        meas_v_array = pd.DataFrame(np.zeros((len(self.wls), len(self.bls))), self.wls, self.bls)
        if self.settings["READ"]["mode"] == "digital":
            # Measure with NI-Digital
            for wl in self.wls:
                for bl in self.bls:
                    meas_v = self.digital.channels[bl].ppmu_measure(nidigital.PPMUMeasurementType.VOLTAGE)[0]
                    meas_i = self.digital.channels[bl].ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)[0]
                    meas_i_gate = self.digital.channels[wl].ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)[0]
                    #self.digital.channels[bl].selected_function = nidigital.SelectedFunction.DIGITAL
                    self.addr_prof[wl][bl]["READs"] +=1
                    # Compute values
                    res = np.abs((self.settings["READ"][self.polarity]["VBL"] - self.settings["READ"][self.polarity]["VSL"])/meas_i - self.settings["READ"]["shunt_res_value"])
                    cond = 1/res
                    meas_i_array.loc[wl,bl] = meas_i
                    meas_v_array.loc[wl,bl] = meas_v
                    res_array.loc[wl,bl] = res
                    cond_array.loc[wl,bl] = cond
                    if record: 
                        self.datafile.writerow([self.chip, self.device, "READ", wl, bl, res, cond, meas_i, meas_v])
                        print([self.chip, self.device, "READ", wl, bl, res, cond, meas_i, meas_v, meas_i_gate])
        else:
            raise NIRRAMException("Invalid READ mode specified in settings")

        # Disable READ, make sure all the supplies in off state for any subsequent operations
        self.digital_all_off(10)

        # Log operation to master file
        # self.mlogfile.write(f"{self.chip},{time.time()},{self.addr},")
        # self.mlogfile.write(f"READ,{res},{cond},{meas_i},{meas_v}\n")
        # Return measurement results
        return res_array, cond_array, meas_i_array, meas_v_array

    def form_pulse(self, mask, vwl=None, vbl=None, vsl=None, pulse_len=None):
        """Perform a FORM operation."""
        # Get parameters
        vwl = self.settings["FORM"][self.polarity]["VWL"] if vwl is None else vwl
        vbl = self.settings["FORM"][self.polarity]["VBL"] if vbl is None else vbl
        vsl = self.settings["FORM"][self.polarity]["VBL"] if vsl is None else vsl
        pulse_len = self.settings["FORM"][self.polarity]["PW"] if pulse_len is None else pulse_len

        # Operation is equivalent to SET but with different parameters
        self.set_pulse(mask, vwl, vbl, vsl, pulse_len)

    def set_pulse(self, mask, vwl=None, vbl=None, vsl=None, pulse_len=None):
        """Perform a SET operation."""
        # Get parameters
        vwl = self.settings["SET"][self.polarity]["VWL"] if vwl is None else vwl
        vbl = self.settings["SET"][self.polarity]["VBL"] if vbl is None else vbl
        vsl = self.settings["SET"][self.polarity]["VSL"] if vsl is None else vsl
        pulse_len = self.settings["SET"][self.polarity]["PW"] if pulse_len is None else pulse_len

        # Increment the number of SETs
        #self.prof["SETs"] += 1

        # Set voltages
        for bl in self.bls: self.set_vbl(bl, vbl)
        for sl in self.sls: self.set_vsl(sl, vsl)
        for wl in self.wls: 
            if self.polarity == "PMOS":
                self.set_vwl(wl, vsl, vwl_lo=vwl)
            else:
                self.set_vwl(wl, vwl)        
        # Pulse WL
        self.pulse(mask, pulse_len=pulse_len)
        # Log the pulse
        #self.mlogfile.write(f"{self.chip},{time.time()},{self.addr},")
        #self.mlogfile.write(f"SET,{vwl},{vbl},0,{pulse_width}\n")

    def reset_pulse(self, mask, vwl=None, vbl=None, vsl=None, pulse_len=None):
        """Perform a RESET operation."""
        # Get parameters
        vwl = self.settings["RESET"][self.polarity]["VWL"] if vwl is None else vwl
        vbl = self.settings["RESET"][self.polarity]["VBL"] if vbl is None else vbl
        vsl = self.settings["RESET"][self.polarity]["VSL"] if vsl is None else vsl
        pulse_len = self.settings["RESET"][self.polarity]["PW"] if pulse_len is None else pulse_len

        # Increment the number of SETs
        #self.prof["RESETs"] += 1

        # Set voltages
        for bl in self.bls: self.set_vbl(bl, vbl)
        for sl in self.sls: self.set_vsl(sl, vsl)
        for wl in self.wls: 
            if self.polarity == "PMOS":
                #self.set_vwl(wl, vsl, vwl_lo=vwl)
                self.set_vwl(wl, vwl)
            else:
                self.set_vwl(wl, vwl)

        self.pulse(mask, pulse_len=pulse_len)

        # Log the pulse
        #self.mlogfile.write(f"{self.chip},{time.time()},{self.addr},")
        #self.mlogfile.write(f"RESET,{vwl},0,{vsl},{pulse_width}\n")

    def set_vsl(self, vsl_chan, vsl, vsl_lo=0):
        """Set VSL using NI-Digital driver"""
        # if self.polarity == "NMOS":
        #     assert(vsl <= 4)
        #     assert(vsl >= 0)
        # if self.polarity == "PMOS":
        assert(vsl_chan in self.sls)
        self.digital.channels[vsl_chan].configure_voltage_levels(vsl_lo, vsl, vsl_lo, vsl, 0)
        #print("Setting VSL: " + str(vsl) + " on chan: " + str(vsl_chan))

    def set_vbl(self, vbl_chan, vbl, vbl_lo=0):
        """Set (active) VBL using NI-Digital driver (inactive disabled)"""
        # assert(vbl <= 3.5)
        # assert(vbl >= 0)
        assert(vbl_chan in self.bls)
        self.digital.channels[vbl_chan].configure_voltage_levels(vbl_lo, vbl, vbl_lo, vbl, 0)

    def set_vwl(self, vwl_chan, vwl_hi, vwl_lo=0):
        """Set (active) VWL using NI-Digital driver (inactive disabled)"""
        # Assertions
        # assert(vwl_hi <= 2.5)
        # assert(vwl_hi >= 0)
        # assert(vwl_lo <= 2.5)
        # assert(vwl_lo >= 0)
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

    def digital_all_off(self, pulse_len=1, prepulse_len=0, postpulse_len=0, max_pulse_len=1200):
        waveform = [0 for i in range(max_pulse_len*len(self.all_wls))]
        # print(waveform)
        
        # Configure and send pulse waveform
        broadcast = nidigital.SourceDataMapping.BROADCAST
        self.digital.pins["BLSLWLS"].create_source_waveform_parallel("wl_data", broadcast)
        self.digital.write_source_waveform_broadcast("wl_data", waveform)
        self.set_pw(pulse_len+prepulse_len+postpulse_len)
        self.digital.burst_pattern("WL_PULSE_DEC3")

    def pulse(self, mask, pulse_len=10, prepulse_len=2, postpulse_len=2, max_pulse_len=1200):
        """Create pulse train"""
        waveform = []
        for (wl_mask, bl_mask, sl_mask) in mask.get_pulse_masks():
            #print(wl_mask, bl_mask, sl_mask)
            if self.polarity=="NMOS":
                wl_prepost_bits = BitVector(bitlist=(wl_mask & False)).int_val()
                wl_mask_bits = BitVector(bitlist=wl_mask).int_val()
                bl_mask_bits = BitVector(bitlist=bl_mask).int_val()
                sl_mask_bits = BitVector(bitlist=sl_mask).int_val()
            elif self.polarity=="PMOS":
                wl_prepost_bits = BitVector(bitlist=(wl_mask | True)).int_val()
                wl_mask_bits = BitVector(bitlist=~wl_mask).int_val()
                bl_mask_bits = BitVector(bitlist=bl_mask).int_val()
                sl_mask_bits = BitVector(bitlist=~sl_mask).int_val()
            
            data_prepulse = (bl_mask_bits << (len(self.all_wls) + len(self.all_sls))) + (sl_mask_bits << (len(self.all_wls))) + wl_prepost_bits
            data = (bl_mask_bits << (len(self.all_wls) + len(self.all_sls))) + (sl_mask_bits << (len(self.all_wls))) + wl_mask_bits
            data_postpulse = (bl_mask_bits << (len(self.all_wls) + len(self.all_sls))) + (sl_mask_bits << (len(self.all_wls)))  + wl_prepost_bits
            waveform += [data_prepulse for i in range(prepulse_len)] + [data for i in range(pulse_len)] + [data_postpulse for i in range(postpulse_len)]
        
        waveform += [0 for i in range(max_pulse_len*len(self.all_wls) - len(waveform))]
        # print(waveform)
        
        # Configure and send pulse waveform
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

    def dynamic_set(self, mode="SET", record=True):
        """Performs SET pulses in increasing fashion until resistance reaches target_res.
        Returns tuple (res, cond, meas_i, meas_v, success)."""
        # Get settings
        cfg = self.settings[mode][self.polarity]
        target_res = self.settings["TARGETS"][mode]
        vsl = cfg["VSL"]
        mask = RRAMArrayMask(self.wls, self.bls, self.sls, self.all_wls, self.all_bls, self.all_sls, self.polarity)
        # Iterative pulse-verify
        success = False
        for pw in np.logspace(int(np.log10(cfg["PW_start"])), int(np.log10(cfg["PW_stop"])), cfg["PW_steps"]):
            for vwl in np.arange(cfg["VWL_SET_start"], cfg["VWL_SET_stop"], cfg["VWL_SET_step"]):
                for vbl in np.arange(cfg["VBL_start"], cfg["VBL_stop"], cfg["VBL_step"]):
                    self.set_pulse(mask, vbl=vbl, vsl=vsl, vwl=vwl, pulse_len=int(pw))
                    res_array, cond_array, meas_i_array, meas_v_array = self.read()
                    for wl in self.wls:
                        for bl in self.bls:
                            if res_array.loc[wl,bl] <= target_res:
                                mask.mask.loc[wl,bl] = False
                                data = [self.chip, self.device, mode, wl, bl, res_array.loc[wl,bl], cond_array.loc[wl,bl], meas_i_array.loc[wl,bl], meas_v_array.loc[wl,bl], vwl, vsl, vbl, pw, True]
                                print(data)
                                if record: self.datafile.writerow(data)
                    success = (mask.mask.to_numpy().sum()==0)
                    if success:
                        break
                if success:
                    break
            if success:
                break
        # Return results
        for wl in self.wls:
            for bl in self.bls:
                if res_array.loc[wl,bl] > target_res:
                    data = [self.chip, self.device, mode, wl, bl, res_array.loc[wl,bl], cond_array.loc[wl,bl], meas_i_array.loc[wl,bl], meas_v_array.loc[wl,bl], vwl, vsl, vbl, pw, False]
                    print(data)
                    if record: self.datafile.writerow(data)

    def dynamic_reset(self, mode="RESET", record=True):
        """Performs RESET pulses in increasing fashion until resistance reaches target_res.
        Returns tuple (res, cond, meas_i, meas_v, success)."""
        # Get settings
        cfg = self.settings[mode][self.polarity]
        target_res = self.settings["TARGETS"][mode]
        vbl = cfg["VBL"]
        mask = RRAMArrayMask(self.wls, self.bls, self.sls, self.all_wls, self.all_bls, self.all_sls, self.polarity)
        # Iterative pulse-verify
        success = False
        for pw in np.logspace(int(np.log10(cfg["PW_start"])), int(np.log10(cfg["PW_stop"])), cfg["PW_steps"]):
            for vwl in np.arange(cfg["VWL_RESET_start"], cfg["VWL_RESET_stop"], cfg["VWL_RESET_step"]):
                for vsl in np.arange(cfg["VSL_start"], cfg["VSL_stop"], cfg["VSL_step"]):
                    self.set_pulse(mask, vbl=vbl, vsl=vsl, vwl=vwl, pulse_len=int(pw))
                    res_array, cond_array, meas_i_array, meas_v_array = self.read()
                    for wl in self.wls:
                        for bl in self.bls:
                            if res_array.loc[wl,bl] >= target_res:
                                mask.mask.loc[wl,bl] = False
                                data = [self.chip, self.device, mode, wl, bl, res_array.loc[wl,bl], cond_array.loc[wl,bl], meas_i_array.loc[wl,bl], meas_v_array.loc[wl,bl], vwl, vsl, vbl, pw, True]
                                print(data)
                                if record: self.datafile.writerow(data)
                    success = (mask.mask.to_numpy().sum()==0)
                    if success:
                        break
                if success:
                    break
            if success:
                break
        # Return results
        for wl in self.wls:
            for bl in self.bls:
                if res_array.loc[wl,bl] < target_res:
                    data = [self.chip, self.device, mode, wl, bl, res_array.loc[wl,bl], cond_array.loc[wl,bl], meas_i_array.loc[wl,bl], meas_v_array.loc[wl,bl], vwl, vsl, vbl, pw, False]
                    print(data)
                    if record: self.datafile.writerow(data)

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
        # self.datafile.close()


if __name__ == "__main__":
    # Basic test
    nirram = NIRRAM("C4")
    nirram.close()
