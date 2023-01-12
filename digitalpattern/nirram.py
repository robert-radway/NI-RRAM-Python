"""Defines the NI RRAM controller class"""
import glob
import tomli
import math
import time
import warnings
from os.path import abspath
import nidigital
import niswitch
import numpy as np
import pandas as pd
import csv
from datetime import datetime
from BitVector import BitVector
from .mask import RRAMArrayMask

# Warnings become errors
warnings.filterwarnings("error")


class NIRRAMException(Exception):
    """Exception produced by the NIRRAM class"""
    def __init__(self, msg):
        super().__init__(f"NIRRAM: {msg}")


class NIRRAM:
    """The NI RRAM controller class that controls the instrument drivers."""
    def __init__(
        self,
        chip,
        device,
        polarity = "NMOS",
        settings = "settings/default.toml",
    ):
        # flag for indicating if connection to ni session is open
        self.closed = True

        # If settings is a string, load as TOML file
        if isinstance(settings, str):
            with open(settings, "rb") as settings_file:
                settings = tomli.load(settings_file)

        # Ensure settings is a dict
        if not isinstance(settings, dict):
            raise NIRRAMException(f"Settings should be a dict, got {repr(settings)}.")

        # Convert NIDigital spec paths to absolute paths
        settings["NIDigital"]["specs"] = [abspath(path) for path in settings["NIDigital"]["specs"]]

        # Initialize RRAM logging
        self.mlogfile = open(settings["path"]["master_log_file"], "a")
        self.plogfile = open(settings["path"]["prog_log_file"], "a")
        self.datafile_path = settings["path"]["data_header"] + datetime.now().strftime("%Y%m%d-%H%M%S") + "_" + str(chip) + "_" + str(device) + ".csv"
        self.datafile = csv.writer(open(self.datafile_path, "a", newline=''))

        self.datafile.writerow(["Chip_ID", "Device_ID", "OP", "Row", "Col", "Res", "Cond", "Meas_I", "Meas_V", "Prog_VBL", "Prog_VSL", "Prog_VWL", "Prog_Pulse", "Success"])

        # Store/initialize parameters
        self.settings = settings
        self.chip = chip
        self.device = device
        self.target_res = settings["target_res"]
        self.op = settings["op"] # operations
        self.polarity = polarity
        
        # body voltages, str name => body voltage
        self.body = settings["device"]["body"]
        
        self.all_wls = settings["device"]["all_WLS"]
        self.all_bls = settings["device"]["all_BLS"]
        self.all_sls = settings["device"]["all_SLS"]

        self.wls = settings["device"]["WLS"]
        self.bls = settings["device"]["BLS"]
        self.sls = settings["device"]["SLS"]

        self.all_off_mask = RRAMArrayMask(self.all_wls, [], [], self.all_wls, self.all_bls, self.all_sls, self.polarity)

        # Only works for 1T1R arrays, sets addr idx and prof
        self.addr_idxs = {}
        self.addr_prof = {}
        for wl in self.wls:
            self.addr_idxs[wl] = {}
            self.addr_prof[wl] = {}
            for i in range(len(self.bls)):
                bl = self.bls[i]
                # temporary fix for 1TNR: if bls and sls len not equal, just use sl0
                if len(self.sls) == len(self.bls):
                    sl = self.sls[i]
                else:
                    sl = self.sls[0]
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
        self.closed = False

        # Configure READ measurements
        if self.op["READ"]["mode"] == "digital":
            for bl in self.bls:
                # Configure NI-Digital current read measurements
                self.digital.channels[bl].ppmu_aperture_time = self.op["READ"]["aperture_time"]
                self.digital.channels[bl].ppmu_aperture_time_units = nidigital.PPMUApertureTimeUnits.SECONDS
                self.digital.channels[bl].ppmu_output_function = nidigital.PPMUOutputFunction.VOLTAGE
                self.digital.channels[bl].ppmu_current_limit_range = self.op["READ"]["current_limit_range"]
                self.digital.channels[bl].ppmu_voltage_level = 0
                self.digital.channels[bl].ppmu_source()
            for sl in self.sls:
                # Configure NI-Digital current read measurements
                self.digital.channels[sl].ppmu_aperture_time = self.op["READ"]["aperture_time"]
                self.digital.channels[sl].ppmu_aperture_time_units = nidigital.PPMUApertureTimeUnits.SECONDS
                self.digital.channels[sl].ppmu_output_function = nidigital.PPMUOutputFunction.VOLTAGE
                self.digital.channels[sl].ppmu_current_limit_range = self.op["READ"]["current_limit_range"]
                self.digital.channels[sl].ppmu_voltage_level = 0
                self.digital.channels[sl].ppmu_source()
        else:
            raise NIRRAMException("Invalid READ mode specified in settings")

        # set body voltages
        for body_i, vbody_i in self.body.items(): self.ppmu_set_vbody(body_i, vbody_i)

        # Set address and all voltages to 0
        for bl in self.all_bls: self.set_vbl(bl, 0.0)
        for sl in self.all_sls: self.set_vsl(sl, 0.0)
        for wl in self.all_wls: self.set_vwl(wl, 0.0)

    def close(self):
        """Do cleanup and then close all NI sessions"""
        if not self.closed:
            # set all body voltages back to zero
            for body_i in self.body.keys(): self.ppmu_set_vbody(body_i, 0.0)
            
            # Close NI-Digital
            self.digital.close()

            # Close log files
            self.mlogfile.close()
            self.plogfile.close()
            # self.datafile.close()

            self.closed = True
    
    def __del__(self):
        """Make sure to automatically close connection in destructor."""
        self.close()
        
    """
    def set_relay_position(self, index, closed=True):
        with niswitch.Session("2571_2") as session:
            relay_name=session.get_relay_name(index=index+1) #one-indexed
            count=session.get_relay_count(relay_name=relay_name)
            position=session.get_relay_position(relay_name=relay_name)
            if position==niswitch.RelayPosition.CLOSED:
                if closed:
                    return 0
                else:
                    try: session.disconnect(channel1=f"no{index}", channel2=f"com{index}")
                    except: pass
                    session.connect(channel1=f"nc{index}", channel2=f"com{index}")
                    return 1
            else:
                if not closed:
                    return 0
                else:
                    try: session.disconnect(channel1=f"nc{index}", channel2=f"com{index}")    
                    except: pass
                    session.connect(channel1=f"no{index}", channel2=f"com{index}")
                    return 1
    """


    def read(self, vbl=None, vsl=None, vwl=None, vwl_unsel=None, vb=None, record=False):
        """Perform a READ operation. This operation works for single 1T1R devices and 
        arrays of devices, where each device has its own WL/BL.
        Returns list (per-bitline) of tuple with (res, cond, meas_i, meas_v)"""
        # Increment the number of READs
        # Let the cell relax after programming to get an accurate read 
        self.digital_all_off(self.op["READ"]["relaxation_cycles"])
        
        # Set the read voltage levels
        vbl = self.op["READ"][self.polarity]["VBL"] if vbl is None else vbl
        vwl = self.op["READ"][self.polarity]["VWL"] if vwl is None else vwl
        vsl = self.op["READ"][self.polarity]["VSL"] if vsl is None else vsl
        vb = self.op["READ"][self.polarity]["VB"] if vb is None else vb

        for bl in self.bls: 
            self.ppmu_set_vbl(bl,vbl)
            self.digital.channels[bl].selected_function = nidigital.SelectedFunction.PPMU
        for sl in self.sls: 
            self.ppmu_set_vsl(sl,vsl)
            self.digital.channels[sl].selected_function = nidigital.SelectedFunction.PPMU
        """
        for b in self.body: 
            assert( -2 <= vb <= 6)
            self.digital.channels[b].ppmu_voltage_level = vb
            self.digital.channels[b].selected_function = nidigital.SelectedFunction.PPMU
        """
        time.sleep(self.op["READ"]["settling_time"]) # let the supplies settle for accurate measurement
        
        # Measure
        res_array = pd.DataFrame(np.zeros((len(self.wls), len(self.bls))), self.wls, self.bls)
        cond_array = pd.DataFrame(np.zeros((len(self.wls), len(self.bls))), self.wls, self.bls)
        meas_i_array = pd.DataFrame(np.zeros((len(self.wls), len(self.bls))), self.wls, self.bls)
        meas_v_array = pd.DataFrame(np.zeros((len(self.wls), len(self.bls))), self.wls, self.bls)
        if self.op["READ"]["mode"] == "digital":
            # Measure with NI-Digital
            for wl in self.wls:
                # sets all WL voltages in the array: read WL is VWL, all others are VSL
                for wl_i in self.all_wls:
                    if wl_i == wl: self.ppmu_set_vwl(wl_i,vwl)
                    else: self.ppmu_set_vwl(wl_i,vsl)
                    self.digital.channels[wl_i].selected_function = nidigital.SelectedFunction.PPMU
                self.digital.ppmu_source()
                time.sleep(self.op["READ"]["settling_time"]) #Let the supplies settle for accurate measurement
                
                for bl in self.bls:
                    # DEBUGGING: test each bitline 
                    # for bl in self.bls:
                    # meas_v = self.digital.channels[bl].ppmu_measure(nidigital.PPMUMeasurementType.VOLTAGE)[0]
                    # meas_i = self.digital.channels[bl].ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)[0]
                    # meas_i_gate = self.digital.channels[wl].ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)[0]
                    # print(f"{bl} v: {meas_v} i: {meas_i} ig: {meas_i_gate}")
                    meas_v = self.digital.channels[bl].ppmu_measure(nidigital.PPMUMeasurementType.VOLTAGE)[0]
                    meas_i = self.digital.channels[bl].ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)[0]
                    meas_i_gate = self.digital.channels[wl].ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)[0]
                    #self.digital.channels[bl].selected_function = nidigital.SelectedFunction.DIGITAL
                    self.addr_prof[wl][bl]["READs"] +=1
                    # Compute values
                    res = np.abs((self.op["READ"][self.polarity]["VBL"] - self.op["READ"][self.polarity]["VSL"])/meas_i - self.op["READ"]["shunt_res_value"])
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
        self.digital_all_off(self.op["READ"]["relaxation_cycles"])

        # Log operation to master file
        # self.mlogfile.write(f"{self.chip},{time.time()},{self.addr},")
        # self.mlogfile.write(f"READ,{res},{cond},{meas_i},{meas_v}\n")
        # Return measurement results
        return res_array, cond_array, meas_i_array, meas_v_array
        
    def read_1tnr(self, vbl=None, vsl=None, vwl=None, vb=None, record=False):
        """Perform a READ operation for a 1TNR. In this case, a single
        FET is connected to multiple RRAMs. In this case, we have a
        single WL, single SL, and multiple BLs. We need to sequentially
        turn BL on/off to read that RRAM, while leaving other bitlines at
        VSL to prevent parallel current paths.
        
        Returns list (per-bitline) of tuple with (res, cond, meas_i, meas_v)
        """
        # Increment the number of READs
        # Let the cell relax after programming to get an accurate read 
        self.digital_all_off(self.op["READ"]["relaxation_cycles"])

        # Set the read voltage levels
        vbl = self.op["READ"][self.polarity]["VBL"] if vbl is None else vbl
        vwl = self.op["READ"][self.polarity]["VWL"] if vwl is None else vwl
        vsl = self.op["READ"][self.polarity]["VSL"] if vsl is None else vsl
        vb = self.op["READ"][self.polarity]["VB"] if vb is None else vb
        # print(f"READ @ vbl: {vbl}, vwl: {vwl}, vsl: {vsl}, vb: {vb}")

        # initially set both BLs and SLs to VSL
        for bl in self.bls: 
            self.ppmu_set_vbl(bl,vsl)
            self.digital.channels[bl].selected_function = nidigital.SelectedFunction.PPMU
        for sl in self.sls: 
            self.ppmu_set_vsl(sl,vsl)
            self.digital.channels[sl].selected_function = nidigital.SelectedFunction.PPMU
        for b in self.body: 
            assert( -2 <= vb <= 6)
            self.digital.channels[b].ppmu_voltage_level = vb
            self.digital.channels[b].selected_function = nidigital.SelectedFunction.PPMU

        time.sleep(self.op["READ"]["settling_time"]) #Let the supplies settle for accurate measurement

        # Measure
        res_array = pd.DataFrame(np.zeros((len(self.wls), len(self.bls))), self.wls, self.bls)
        cond_array = pd.DataFrame(np.zeros((len(self.wls), len(self.bls))), self.wls, self.bls)
        meas_i_array = pd.DataFrame(np.zeros((len(self.wls), len(self.bls))), self.wls, self.bls)
        meas_v_array = pd.DataFrame(np.zeros((len(self.wls), len(self.bls))), self.wls, self.bls)
        if self.op["READ"]["mode"] == "digital":
            # Measure with NI-Digital
            for wl in self.wls:
                for wl_i in self.wls:
                    if wl_i == wl: self.ppmu_set_vwl(wl_i, vwl)
                    else: self.ppmu_set_vwl(wl_i, vsl)
                    self.digital.channels[wl_i].selected_function = nidigital.SelectedFunction.PPMU
                self.digital.ppmu_source()
                time.sleep(self.op["READ"]["settling_time"]) #Let the supplies settle for accurate measurement
                
                for bl in self.bls:
                    # set specific bl and measure
                    self.ppmu_set_vbl(bl, vbl)
                    self.digital.channels[bl].ppmu_source()
                    time.sleep(self.op["READ"]["settling_time"]) #Let the supplies settle for accurate measurement

                    # test each bitline
                    # for x in self.bls:
                    #     meas_v = self.digital.channels[x].ppmu_measure(nidigital.PPMUMeasurementType.VOLTAGE)[0]
                    #     meas_i = self.digital.channels[x].ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)[0]
                    #     meas_i_gate = self.digital.channels[wl].ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)[0]
                    #     print(f"{x} v: {meas_v} i: {meas_i} ig: {meas_i_gate}")
                    
                    meas_v = self.digital.channels[bl].ppmu_measure(nidigital.PPMUMeasurementType.VOLTAGE)[0]
                    meas_i = self.digital.channels[bl].ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)[0]
                    meas_i_gate = self.digital.channels[wl].ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)[0]

                    # reset bl back to vsl
                    self.ppmu_set_vbl(bl, vsl)
                    self.digital.channels[bl].ppmu_source()
                    time.sleep(self.op["READ"]["settling_time"]) #Let the supplies settle for accurate measurement

                    #self.digital.channels[bl].selected_function = nidigital.SelectedFunction.DIGITAL
                    self.addr_prof[wl][bl]["READs"] +=1

                    # Compute values
                    res = np.abs((self.op["READ"][self.polarity]["VBL"] - self.op["READ"][self.polarity]["VSL"])/meas_i - self.op["READ"]["shunt_res_value"])
                    cond = 1/res
                    meas_i_array.loc[wl,bl] = meas_i
                    meas_v_array.loc[wl,bl] = meas_v
                    res_array.loc[wl,bl] = res
                    cond_array.loc[wl,bl] = cond
                    if record: 
                        self.datafile.writerow([self.chip, self.device, "READ", wl, bl, res, cond, meas_i, meas_v, meas_i_gate])
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

    def set_pulse(
        self,
        mask,
        bl_selected=None, # selected BL
        vwl=None,
        vbl=None,
        vsl=None,
        vbl_unsel=None,
        pulse_len=None,
    ):
        """Perform a SET operation.
        To support 1TNR devices (1 WL, 1 SL, multiple BLs), have input
        "bl" selection parameter. If "bl" is not None, this specifies the
        selected "bl". For all other unselected BLs, by default set their
        value to an intermediate voltage V/4 (based on Hsieh et al, IEDM 2019)
        to reduce impact of oversetting/overreseting unselected devices.

        This voltage must be relative to value between VSL and VBL,
        not just VBL/4 because VSL is not necessarily 0 V, so just taking
        VBL/4 can increase voltage when VSL > VBL and VBL is stepped down
        (e.g. in the case of PMOS). So we want `VSL + (VBL - VSL)/4.0`
        Example for SET (VSL fixed, sweep VBL):
            VSL     VBL     VBL/4     VSL + (VBL - VSL)/4
            2.0     1.4      0.35          1.85      
            2.0     1.2      0.30          1.8
            2.0     1.0      0.25          1.75
        """
        # Get parameters
        vwl = vwl if vwl is not None else self.op["SET"][self.polarity]["VWL"]
        vbl = vbl if vbl is not None else self.op["SET"][self.polarity]["VBL"]
        vsl = vsl if vsl is not None else self.op["SET"][self.polarity]["VSL"]
        vbl_unsel = vbl_unsel if vbl_unsel is not None else vsl + ((vbl - vsl) / 4.0)
        pulse_len = pulse_len if pulse_len is not None else self.op["SET"][self.polarity]["PW"] 
        
        # set voltages
        for bl_i in self.bls:
            if bl_selected is not None: # selecting specific bl, unselecting others
                vbl_i = vbl if bl_i == bl_selected else vbl_unsel
            else:
                vbl_i = vbl
            # print(f"Setting BL {bl_i} to {vbl_i} V")
            self.set_vbl(bl_i, vbl_i)
        
        for sl_i in self.sls:
            # print(f"Setting SL {sl_i} to {vsl} V")
            self.set_vsl(sl_i, vsl)
        
        for wl_i in self.wls:
            if self.polarity == "PMOS":
                self.set_vwl(wl_i, vsl, vwl_lo=vwl)
            else:
                self.set_vwl(wl_i, vwl)   
         
        # pulse WL
        self.pulse(mask, pulse_len=pulse_len)

        # Log the pulse
        #self.mlogfile.write(f"{self.chip},{time.time()},{self.addr},")
        #self.mlogfile.write(f"SET,{vwl},{vbl},0,{pulse_width}\n")

    def reset_pulse(
        self,
        mask,
        bl_selected=None, # selected BL
        vwl=None,
        vbl=None,
        vsl=None,
        vbl_unsel=None,
        pulse_len=None,
    ):
        """Perform a RESET operation.
        To support 1TNR devices (1 WL, 1 SL, multiple BLs), have input
        "bl" selection parameter. If "bl" is not None, this specifies the
        selected "bl". For all other unselected BLs, by default set their
        value to an intermediate voltage V/4 (based on Hsieh et al, IEDM 2019)
        to reduce impact of oversetting/overreseting unselected devices. 

        This voltage must be relative to value between VSL and VBL,
        not just VBL/4 because VSL is not necessarily 0 V, so just taking
        VBL/4 can increase voltage when VSL > VBL and VBL is stepped down
        (e.g. in the case of PMOS). So we want `VSL + (VBL - VSL)/4.0`
        Example for RESET (VBL fixed, sweep VSL):
            VSL     VBL     VBL/4     VSL + (VBL - VSL)/4
            1.4     2.0      0.5           1.55
            1.2     2.0      0.5           1.40
            1.0     2.0      0.5           1.25
        """
        # Get parameters
        vwl = vwl if vwl is None else self.op["RESET"][self.polarity]["VWL"]
        vbl = vbl if vbl is None else self.op["RESET"][self.polarity]["VBL"]
        vsl = vsl if vsl is None else self.op["RESET"][self.polarity]["VSL"]
        vbl_unsel = vbl_unsel if vbl_unsel is not None else vsl + ((vbl - vsl) / 4.0)
        pulse_len = pulse_len if pulse_len is None else self.op["RESET"][self.polarity]["PW"] 

        # set voltages
        for bl_i in self.bls:
            if bl_selected is not None: # selecting specific bl, unselecting others
                vbl_i = vbl if bl_i == bl_selected else vbl_unsel
            else:
                vbl_i = vbl
            # print(f"Setting BL {bl_i} to {vbl_i} V")
            self.set_vbl(bl_i, vbl_i)
        
        for sl_i in self.sls:
            # print(f"Setting SL {sl_i} to {vsl} V")
            self.set_vsl(sl_i, vsl)

        for wl_i in self.wls: 
            if self.polarity == "PMOS":
                self.set_vwl(wl_i, vsl, vwl_lo=vwl)
                # self.set_vwl(wl, vwl)
            else:
                self.set_vwl(wl_i, vwl) 

        # pulse WL
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
        assert(vsl_chan in self.all_sls)
        self.digital.channels[vsl_chan].configure_voltage_levels(vsl_lo, vsl, vsl_lo, vsl, 0)
        #print("Setting VSL: " + str(vsl) + " on chan: " + str(vsl_chan))

    def set_vbl(self, vbl_chan, vbl, vbl_lo=0):
        """Set (active) VBL using NI-Digital driver (inactive disabled)"""
        # assert(vbl <= 3.5)
        # assert(vbl >= 0)
        assert(vbl_chan in self.all_bls)
        self.digital.channels[vbl_chan].configure_voltage_levels(vbl_lo, vbl, vbl_lo, vbl, 0)

    def set_vwl(self, vwl_chan, vwl_hi, vwl_lo=0):
        """Set (active) VWL using NI-Digital driver (inactive disabled)"""
        # Assertions
        # assert(vwl_hi <= 2.5)
        # assert(vwl_hi >= 0)
        # assert(vwl_lo <= 2.5)
        # assert(vwl_lo >= 0)
        assert(vwl_chan in self.all_wls)
        self.digital.channels[vwl_chan].configure_voltage_levels(vwl_lo, vwl_hi, vwl_lo, vwl_hi, 0)

    def ppmu_set_vsl(self, vsl_chan, vsl):
        """Set VSL using NI-Digital driver"""
        assert(vsl <= 6)
        assert(vsl >= -2)
        assert(vsl_chan in self.all_sls)
        self.digital.channels[vsl_chan].ppmu_voltage_level = vsl
        self.digital.channels[vsl_chan].ppmu_source()
        #print("Setting VSL: " + str(vsl) + " on chan: " + str(vsl_chan))
    
    def ppmu_set_isl(self, isl_chan, isl):
        """Set ISL using NI-Digital driver"""
        assert(isl_chan in self.all_sls)
        self.digital.channels[isl_chan].ppmu_current_level = isl
        self.digital.channels[isl_chan].ppmu_source()

    def ppmu_set_vbl(self, vbl_chan, vbl):
        """Set (active) VBL using NI-Digital driver (inactive disabled)"""
        assert(vbl <= 6)
        assert(vbl >= -2)
        assert(vbl_chan in self.all_bls)
        self.digital.channels[vbl_chan].ppmu_voltage_level = vbl
        self.digital.channels[vbl_chan].ppmu_source()

    def ppmu_set_vwl(self, vwl_chan, vwl):
        """Set VSL using NI-Digital driver"""
        assert(vwl <= 6)
        assert(vwl >= -2)
        assert(vwl_chan in self.all_wls)
        self.digital.channels[vwl_chan].ppmu_voltage_level = vwl
        self.digital.channels[vwl_chan].ppmu_source()
        #print("Setting VSL: " + str(vsl) + " on chan: " + str(vsl_chan))

    def ppmu_set_vbody(self, vbody_chan, vbody):
        """Set VBODY using NI-Digital driver"""
        assert(vbody <= 3)
        assert(vbody >= -1)
        assert(vbody_chan in self.body)
        self.digital.channels[vbody_chan].ppmu_voltage_level = vbody
        self.digital.channels[vbody_chan].ppmu_current_limit_range = 32e-6
        self.digital.channels[vbody_chan].ppmu_source()
        #print("Setting VSL: " + str(vsl) + " on chan: " + str(vsl_chan))

    def digital_all_off(self, pulse_len=1, prepulse_len=0, postpulse_len=0, max_pulse_len=1200):
        waveform = [0 for i in range(max_pulse_len*len(self.all_wls))]
        # print(waveform)
        
        # Configure and send pulse waveform
        broadcast = nidigital.SourceDataMapping.BROADCAST
        self.digital.pins["BLSLWLS"].create_source_waveform_parallel("wl_data", broadcast)
        self.digital.write_source_waveform_broadcast("wl_data", waveform)
        self.set_pw(pulse_len+prepulse_len+postpulse_len)
        self.digital.burst_pattern("WL_PULSE_DEC3") #PULSE_MPW_ProbeCard

    def pulse(self, mask, pulse_len=10, prepulse_len=2, postpulse_len=2, max_pulse_len=1200):
        """Create pulse train. Format of bits is [BL SL WL]. For an array
        with 2 BLs, 2 SLs, and 2 WLs, the bits are ordered:
            [ BL0 BL1 SL0 SL1 WL0 WL1]
        To allow for BL/SL settling before pulsing the WL, pre-pend
        and post-pend pulses where WLs are 0. For example, if we are
        pulsing both WLs, with all BLs and SLs enabled, our pulses will be:
            [ 1 1 1 1 0 0 ]   } Pre-pulse (WL zero'd, BL/SL active)
            [ 1 1 1 1 0 0 ]
                 ...
            [ 1 1 1 1 1 1 ]   } Main pulse (WL active, BL/SL active)
            [ 1 1 1 1 1 1 ]
                 ...
            [ 1 1 1 1 0 0 ]   } Post-pulse (WL zero'd, BL/SL active)
            [ 1 1 1 1 0 0 ]
        """
        bl_bits_offset = len(self.all_wls) + len(self.all_sls)
        sl_bits_offset = len(self.all_wls)

        waveform = []
        for (wl_mask, bl_mask, sl_mask) in mask.get_pulse_masks():
            ### Print masks for debugging
            # print(f"wl_mask = {wl_mask}")
            # print(f"bl_mask = {bl_mask}")
            # print(f"sl_mask = {sl_mask}")

            if self.polarity =="NMOS":
                wl_pre_post_bits = BitVector(bitlist=(wl_mask & False)).int_val()
                wl_mask_bits = BitVector(bitlist=wl_mask).int_val()
                bl_mask_bits = BitVector(bitlist=bl_mask).int_val()
                sl_mask_bits = BitVector(bitlist=sl_mask).int_val()
            elif self.polarity =="PMOS":
                wl_pre_post_bits = BitVector(bitlist=(wl_mask | True)).int_val()
                wl_mask_bits = BitVector(bitlist=~wl_mask).int_val()
                bl_mask_bits = BitVector(bitlist=bl_mask).int_val()
                sl_mask_bits = BitVector(bitlist=~sl_mask).int_val()
            else:
                raise ValueError(f"Invalid polarity: {self.polarity}. Must be 'NMOS' or 'PMOS'.")
            
            # print(f"wl_mask_bits: {wl_mask_bits}")

            data_prepulse = (bl_mask_bits << bl_bits_offset) + (sl_mask_bits << sl_bits_offset) + wl_pre_post_bits
            data = (bl_mask_bits << bl_bits_offset) + (sl_mask_bits << sl_bits_offset) + wl_mask_bits
            data_postpulse = (bl_mask_bits << bl_bits_offset) + (sl_mask_bits << sl_bits_offset)  + wl_pre_post_bits

            ### print bits for debugging
            # print(f"data_prepulse = {data_prepulse:b}")
            # print(f"data = {data:b}")
            # print(f"data_postpulse = {data_postpulse:b}")

            waveform += [data_prepulse for i in range(prepulse_len)] + [data for i in range(pulse_len)] + [data_postpulse for i in range(postpulse_len)]
        
        # zero-pad rest of waveform
        waveform += [0 for i in range(max_pulse_len*len(self.all_wls) - len(waveform))]

        # print(waveform)
        
        # Configure and send pulse waveform
        broadcast = nidigital.SourceDataMapping.BROADCAST
        self.digital.pins["BLSLWLS"].create_source_waveform_parallel("wl_data", broadcast)
        self.digital.write_source_waveform_broadcast("wl_data", waveform)
        self.set_pw(prepulse_len + pulse_len + postpulse_len)
        self.digital.burst_pattern("WL_PULSE_DEC3")

    def set_pw(self, pulse_width):
        """Set pulse width"""
        pw_register = nidigital.SequencerRegister.REGISTER0
        self.digital.write_sequencer_register(pw_register, pulse_width)

    def set_endurance_cycles(self, cycles):
        """Set number of endurance cycles"""
        cycle_register = nidigital.SequencerRegister.REGISTER1
        self.digital.write_sequencer_register(cycle_register, cycles)

    def dynamic_form(
        self,
        is_1tnr=False,
        bl_selected=None, # select specific bl for 1TNR measurements
    ):
        """Performs SET pulses in increasing fashion until resistance reaches target_res.
        Returns tuple (res, cond, meas_i, meas_v, success)."""
        return self.dynamic_set(
            mode="FORM",
            is_1tnr=is_1tnr,
            bl_selected=bl_selected,
        )

    def dynamic_set(
        self,
        mode="SET",
        print_data=True,
        record=True,
        target_res=None, # target res, if None will use value in settings
        is_1tnr=False,
        bl_selected=None, # select specific bl for 1TNR measurements
    ):
        """Performs SET pulses in increasing fashion until resistance reaches target_res.
        Returns tuple (res, cond, meas_i, meas_v, success)."""
        # Get settings
        cfg = self.op[mode][self.polarity]
        target_res = target_res if target_res is not None else self.target_res[mode]
        vsl = cfg["VSL"]
        mask = RRAMArrayMask(self.wls, self.bls, self.sls, self.all_wls, self.all_bls, self.all_sls, self.polarity)
        
        # select read method
        read_pulse = self.read_1tnr if is_1tnr else self.read

        # Iterative pulse-verify
        success = False
        for pw in np.logspace(int(np.log10(cfg["PW_start"])), int(np.log10(cfg["PW_stop"])), cfg["PW_steps"]):
            for vwl in np.arange(cfg["VWL_SET_start"], cfg["VWL_SET_stop"], cfg["VWL_SET_step"]):
                for vbl in np.arange(cfg["VBL_start"], cfg["VBL_stop"], cfg["VBL_step"]):
                    #print(pw, vwl, vbl, vsl)
                    self.set_pulse(
                        mask,
                        bl_selected=bl_selected, # specific selected BL for 1TNR
                        vbl=vbl,
                        vsl=vsl,
                        vwl=vwl,
                        pulse_len=int(pw),
                    )
                    
                    # use settling if parameter present, to discharge parasitic cap
                    if "settling_time" in self.op[mode]:
                        time.sleep(self.op[mode]["settling_time"])

                    # read result resistance
                    res_array, cond_array, meas_i_array, meas_v_array = read_pulse()
                    #print(res_array)
                    
                    if bl_selected is None: # use array success condition: all in array must hit target
                        for wl_i in self.wls:
                            for bl_i in self.bls:
                                if (res_array.loc[wl_i, bl_i] <= target_res) & mask.mask.loc[wl_i, bl_i]:
                                    mask.mask.loc[wl_i, bl_i] = False
                        success = (mask.mask.to_numpy().sum()==0)
                    else: # 1TNR success condition: check if selected 1tnr cell hit target
                        success = True
                        for wl_i in self.wls:
                            if (res_array.loc[wl_i, bl_selected] > target_res) & mask.mask.loc[wl_i, bl_selected]:
                                success = False
                                break
                    
                    if success:
                        break
                if success:
                    break
            if success:
                break
        
        # report final cell results
        all_data = []
        for wl in self.wls:
            for bl in self.bls:
                cell_success = res_array.loc[wl,bl] <= target_res
                cell_data = [self.chip, self.device, mode, wl, bl, res_array.loc[wl,bl], cond_array.loc[wl,bl], meas_i_array.loc[wl,bl], meas_v_array.loc[wl,bl], vwl, vsl, vbl, pw, cell_success]
                if print_data: print(cell_data)
                if record: self.datafile.writerow(cell_data)
                all_data.append(cell_data)
        return all_data

    def dynamic_reset(
        self,
        mode="RESET",
        record=True,
        print_data=True,  # print data to console
        target_res=None,  # target res, if None will use value in settings
        is_1tnr=False,    # if 1TNR device, do different type of read
        bl_selected=None, # select specific bl for 1TNR measurements
    ):
        """Performs RESET pulses in increasing fashion until resistance reaches target_res.
        Returns tuple (res, cond, meas_i, meas_v, success)."""
        # Get settings
        cfg = self.op[mode][self.polarity]
        target_res = target_res if target_res is not None else self.target_res[mode]
        vbl = cfg["VBL"]
        mask = RRAMArrayMask(self.wls, self.bls, self.sls, self.all_wls, self.all_bls, self.all_sls, self.polarity)
        
        # select read method
        read_pulse = self.read_1tnr if is_1tnr else self.read
        # Iterative pulse-verify
        success = False
        for pw in np.logspace(int(np.log10(cfg["PW_start"])), int(np.log10(cfg["PW_stop"])), cfg["PW_steps"]):
            for vwl in np.arange(cfg["VWL_RESET_start"], cfg["VWL_RESET_stop"], cfg["VWL_RESET_step"]):
                for vsl in np.arange(cfg["VSL_start"], cfg["VSL_stop"], cfg["VSL_step"]):
                    self.reset_pulse(
                        mask,
                        bl_selected=bl_selected, # specific selected BL for 1TNR
                        vbl=vbl,
                        vsl=vsl,
                        vwl=vwl,
                        pulse_len=int(pw),
                    )
                    
                    # use settling if parameter present, to discharge parasitic cap
                    if "settling_time" in self.op[mode]:
                        time.sleep(self.op[mode]["settling_time"])
                    
                    # read result resistance
                    res_array, cond_array, meas_i_array, meas_v_array = read_pulse()
                    
                    if bl_selected is None: # use array success condition: all in array must hit target
                        for wl_i in self.wls:
                            for bl_i in self.bls:
                                if (res_array.loc[wl_i, bl_i] >= target_res) & mask.mask.loc[wl_i, bl_i]:
                                    mask.mask.loc[wl_i, bl_i] = False
                        success = (mask.mask.to_numpy().sum() == 0)
                    else: # 1TNR success condition: check if selected 1tnr cell hit target
                        success = True
                        for wl_i in self.wls:
                            if (res_array.loc[wl_i, bl_selected] < target_res) & mask.mask.loc[wl_i, bl_selected]:
                                success = False
                                break
                    if success:
                        break
                if success:
                    break
            if success:
                break
        
        # record final cell results
        all_data = []
        for wl in self.wls:
            for bl in self.bls:
                cell_success = res_array.loc[wl,bl] >= target_res
                cell_data = [self.chip, self.device, mode, wl, bl, res_array.loc[wl,bl], cond_array.loc[wl,bl], meas_i_array.loc[wl,bl], meas_v_array.loc[wl,bl], vwl, vsl, vbl, pw, cell_success]
                if print_data: print(cell_data)
                if record: self.datafile.writerow(cell_data)
                all_data.append(cell_data)
        
        return all_data


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

    def endurance_old(self, cycs=1000, read_cycs=None, pulse_width=None, reset_first=True, debug=True):
        """Do endurance cycle testing. Parameter read_cycs is number of cycles after which
        to measure one cycle (default: never READ)"""
        # Configure pulse width and cycle counts
        read_cycs = int(min(read_cycs if read_cycs is not None else 1e15, cycs))
        pulse_width = self.op["SET"]["PW"] if pulse_width is None else pulse_width
        self.set_pw(pulse_width)
        self.set_endurance_cycles(read_cycs)

        # Initialize return data
        data = []

        # Iterate to do cycles
        for cyc in range(int(math.ceil(cycs/read_cycs))):
            # Configure endurance voltages
            vbl = self.op["SET"]["VBL"]
            vwl = self.op["RESET"]["VWL"], self.op["SET"]["VWL"]
            vsl = self.op["RESET"]["VSL"]
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
    
    @staticmethod
    def get_read_cycles(
        max_cycles: int,
        sweep_schedule: list[tuple],
    ) -> list[int]:
        """
        Generates list of integer cycle numbers where the measurement should
        read and print output data. Based on input sweep schedule which allows
        unevenly spaced reads across max cycle count. Used for endurance
        measurement, where we want to do some form of logarithmic spaced
        reads to reduce the time of measurement, e.g. read on cycle:

            0 1 2 3 4 5 ... 10 20 ... 100 200 300 ... 1000 2000 ...

        This would be a sweep schedule defined in format:

            [(0, 1), (10, 10), (100, 100), (1000, 1000)]

        Each tuple element is (start_cycle, read_step_size), e.g. 
            (0, 1): after cycle 0, read every 1x cycle
            (10, 10): after cycle 10, read every 10x cycle
            (100, 100): after cycle 100, read every 100x cycle
            ...
        """
        next_read_cycles = []
        num_schedule_steps = len(sweep_schedule)

        n = 0
        schedule_idx = 0
        next_schedule_idx = min(schedule_idx + 1, num_schedule_steps - 1)
        schedule_step_cycle, step_count = sweep_schedule[schedule_idx]
        next_step_cycle, next_step_count = sweep_schedule[next_schedule_idx]

        while n <= max_cycles:
            next_read_cycles.append(n)

            n += step_count

            # update schedule step size
            if schedule_idx < len(sweep_schedule) - 1 and n >= next_step_cycle:
                schedule_idx += 1
                next_schedule_idx = min(schedule_idx + 1, num_schedule_steps - 1)
                schedule_step_cycle, step_count = sweep_schedule[schedule_idx]
                next_step_cycle, next_step_count = sweep_schedule[next_schedule_idx]

        return next_read_cycles
    
    def endurance_dynamic_set_reset(
        self,
        max_cycles: int,
        sweep_schedule: list[tuple],
        max_failures: int = 100,
        record: bool = True,
        print_data: bool = True,
        target_res_reset: float = None, # target res for reset, if None will use value in settings
        target_res_set: float = None,   # target res for set, if None will use value in settings
        is_1tnr: bool = False,          # if 1TNR device, do different type of read
        fail_on_all: bool = True,       # if True, will record failure if ALL devices in an array fail
    ):
        """Run endurance measurement with dynamic set/reset to hit target res.
        This runs series of set/reset cycles, then periodically reads based
        on input sweep schedule. After `max_failures` to hit a target res
        in a row, the sweep will stop.
        """
        # keep in reverse order so we can pop off the end
        next_record_cycles = NIRRAM.get_read_cycles(max_cycles, sweep_schedule)[::-1]

        cycle = 0
        next_record_cycle = next_record_cycles.pop()

        total_failures = 0 # total number of failures detected
        sequential_failures = 0 # number of failures in a row

        while cycle <= max_cycles:
            data_reset = self.dynamic_reset(target_res=target_res_reset, print_data=False, record=False, is_1tnr=is_1tnr)
            data_set = self.dynamic_set(target_res=target_res_set, print_data=False, record=False, is_1tnr=is_1tnr)

            if cycle >= next_record_cycle:
                # print and record measured data (append cycle number in front)
                for d in data_reset:
                    d_with_cycle = [cycle] + d
                    if print_data: print(d_with_cycle)
                    if record: self.datafile.writerow(d_with_cycle)
                for d in data_set:
                    d_with_cycle = [cycle] + d
                    if print_data: print(d_with_cycle)
                    if record: self.datafile.writerow(d_with_cycle)
                
                next_record_cycle = next_record_cycles.pop()
            
            # check and accumulate failures
            if fail_on_all:
                failed_reset = True
                failed_set = True
                for d in data_reset:
                    success = d[-1]
                    if success == True:
                        failed_reset = False
                        break
                for d in data_set:
                    success = d[-1]
                    if success == True:
                        failed_set = False
                        break
                if failed_reset or failed_set:
                    total_failures += 1
                    sequential_failures += 1
                else:
                    sequential_failures = 0 # reset failures in row, ignore random errors
            else: # fail on any error in any device
                failed_reset = False
                failed_set = False
                for d in data_reset:
                    success = d[-1]
                    if success == False:
                        failed_reset = True
                        break
                if failed_reset == False:
                    for d in data_set:
                        success = d[-1]
                        if success == False:
                            failed_set = True
                            break
                if failed_reset or failed_set:
                    total_failures += 1
                    sequential_failures += 1
                else:
                    sequential_failures = 0 # reset failures in row, ignore random errors
            
            if sequential_failures >= max_failures:
                print(f"Endurance sweep reached max failures (sequential failures = {sequential_failures}, total failures = {total_failures})")
                break

            cycle += 1

        print(f"Endurance sweep ended at cycle = {cycle}, total failures = {total_failures}")

    def sweep_gradual_reset_in_range(
        self,
        res_low: float,       # resistance low bound for set before resetting
        res_high: float,      # resistance high bound for stopping reset before setting
        mode="RESET_SWEEP", # mode containing reset gradual config
        record=True,          # record output data
    ):
        """This is used to sweep achievable resistances values, by sweeping a series
        of reset pulses and recording the value after each pulse:
        1. First run a dynamic set to push device to a specific `res_low` target
        2. For each value in the VSL sweep, reset pulse device, record resistance
        3. Break when `res_high` target hit. 
        """

        # initialization: do built in set to get into res_low target
        self.dynamic_set(target_res=res_low)

        # get settings for this
        cfg = self.op[mode][self.polarity]
        vbl = cfg["VBL"]
        vwl = cfg["VWL"]
        pw = cfg["PW"]
        pcount = cfg["PCOUNT"]
        mask = RRAMArrayMask(self.wls, self.bls, self.sls, self.all_wls, self.all_bls, self.all_sls, self.polarity)

        # iterative reset pulse, save resistance after each pulse regardless of outcome
        success = False
        for vsl in np.arange(cfg["VSL_start"], cfg["VSL_stop"], cfg["VSL_step"]):
            # do "pcount" pulses
            for i in range(pcount):
                self.set_pulse(mask, vbl=vbl, vsl=vsl, vwl=vwl, pulse_len=int(pw))
                res_array, cond_array, meas_i_array, meas_v_array = self.read()

                # save data
                for wl in self.wls:
                    for bl in self.bls:
                        cell_success = False
                        if (res_array.loc[wl,bl] >= res_high) & mask.mask.loc[wl,bl]:
                            cell_success = True
                            mask.mask.loc[wl,bl] = False
                        data = [self.chip, self.device, mode, wl, bl, res_array.loc[wl,bl], cond_array.loc[wl,bl], meas_i_array.loc[wl,bl], meas_v_array.loc[wl,bl], vwl, vsl, vbl, pw, cell_success]
                        print(f"{i}. {data}")
                        if record: self.datafile.writerow(data)
            
            success = (mask.mask.to_numpy().sum()==0)
            if success:
                print(f"REACHED TARGET {res_high}, BREAKING.")
                break
        

    def sweep_gradual_set_in_range(
        self,
        res_low: float,     # resistance low bound for set before resetting
        res_high: float,    # resistance high bound for stopping reset before setting
        mode="SET_SWEEP",   # mode containing reset gradual config
        record=True,        # record output data
    ):
        """This is used to sweep achievable resistances values, by sweeping a series
        of reset pulses and recording the value after each pulse:
        1. First run a dynamic reset to push device to a specific `res_low` target
        2. For each value in the VSL sweep, reset pulse device, record resistance
        3. Break when `res_high` target hit. 
        """

        # initialization: do built in set to get into res_low target
        self.dynamic_reset(target_res=res_high)

        # get settings for this
        cfg = self.op[mode][self.polarity]
        vsl = cfg["VSL"]
        vwl = cfg["VWL"]
        pw = cfg["PW"]
        pcount = cfg["PCOUNT"]
        mask = RRAMArrayMask(self.wls, self.bls, self.sls, self.all_wls, self.all_bls, self.all_sls, self.polarity)

        # iterative reset pulse, save resistance after each pulse regardless of outcome
        success = False
        for vbl in np.arange(cfg["VBL_start"], cfg["VBL_stop"], cfg["VBL_step"]):
            # do "pcount" pulses
            for i in range(pcount):
                self.set_pulse(mask, vbl=vbl, vsl=vsl, vwl=vwl, pulse_len=int(pw))
                res_array, cond_array, meas_i_array, meas_v_array = self.read()

                # save data
                for wl in self.wls:
                    for bl in self.bls:
                        cell_success = False
                        if (res_array.loc[wl,bl] <= res_low) & mask.mask.loc[wl,bl]:
                            cell_success = True
                            mask.mask.loc[wl,bl] = False
                        data = [self.chip, self.device, mode, wl, bl, res_array.loc[wl,bl], cond_array.loc[wl,bl], meas_i_array.loc[wl,bl], meas_v_array.loc[wl,bl], vwl, vsl, vbl, pw, cell_success]
                        print(f"{i}. {data}")
                        if record: self.datafile.writerow(data)
            
            success = (mask.mask.to_numpy().sum()==0)
            if success:
                print(f"REACHED TARGET {res_high}, BREAKING.")
                break
    
    def targeted_intermediate_set(
        self,
        target_res: float,  # target resistance
        res_high: float,    # resistance high bound for stopping reset before setting
    ):
        """
        Perform set that targets an intermediate value, for multi-bit programming.
        Based on RADAR method by

        This combines two passes:
        1. Coarse targeting pass:
            Goal is to enter a coarse resistance range near target
            (in max number of iterations before failing).

        2. Fine targeting pass:
            Goal is to enter a fine resistance range near target
            (in max number of iterations before failing). 
        
        """
        # initialization: do built in set to get into res_low target
        self.dynamic_reset(target_res=res_high)

        # get settings for this
        cfg = self.op[mode][self.polarity]
        vsl = cfg["VSL"]
        vwl = cfg["VWL"]
        pw = cfg["PW"]
        pcount = cfg["PCOUNT"]
        mask = RRAMArrayMask(self.wls, self.bls, self.sls, self.all_wls, self.all_bls, self.all_sls, self.polarity)

        # iterative reset pulse, save resistance after each pulse regardless of outcome
        success = False
        for vbl in np.arange(cfg["VBL_start"], cfg["VBL_stop"], cfg["VBL_step"]):
            # do "pcount" pulses
            for i in range(pcount):
                self.set_pulse(mask, vbl=vbl, vsl=vsl, vwl=vwl, pulse_len=int(pw))
                res_array, cond_array, meas_i_array, meas_v_array = self.read()

                # save data
                for wl in self.wls:
                    for bl in self.bls:
                        cell_success = False
                        if (res_array.loc[wl,bl] <= res_low) & mask.mask.loc[wl,bl]:
                            cell_success = True
                            mask.mask.loc[wl,bl] = False
                        data = [self.chip, self.device, mode, wl, bl, res_array.loc[wl,bl], cond_array.loc[wl,bl], meas_i_array.loc[wl,bl], meas_v_array.loc[wl,bl], vwl, vsl, vbl, pw, cell_success]
                        print(f"{i}. {data}")
                        if record: self.datafile.writerow(data)
            
            success = (mask.mask.to_numpy().sum()==0)
            if success:
                print(f"REACHED TARGET {res_high}, BREAKING.")
                break

if __name__ == "__main__":
    # Basic test
    nirram = NIRRAM("C4")
    nirram.close()
