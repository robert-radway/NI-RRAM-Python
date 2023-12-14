"""Defines the NI RRAM controller class"""
import glob
import tomli
import math
import time
import warnings
from dataclasses import dataclass
from os.path import abspath
import nidigital
import niswitch
import numpy as np
import pandas as pd
import csv
from datetime import datetime
from BitVector import BitVector
from .mask import RRAMArrayMask
from . import util

# Warnings become errors
warnings.filterwarnings("error")

@dataclass
class RRAMOperationResult:
    """Data class to store measured parameters from an RRAM operation
    (e.g. set, reset, form, etc.)
    """
    chip: str
    device: str
    mode: str
    wl: str
    bl: str
    res: float
    cond: float
    i: float
    v: float
    vwl: float
    vsl: float
    vbl: float
    pw: float
    success: bool


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
        self.all_channels = self.all_wls + self.all_bls + self.all_sls

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
        ###TODO This replaces the DEC3.digilevles and DEC4.digitiming files
        ### you should update TOMLS accordingly to parameterise the configure_time
        self.digital.create_time_set("test")
        self.digital.configure_time_set_period("test", 1e-8)
        self.digital.channels[self.all_channels].write_static(nidigital.WriteStaticPinState.ZERO)
        self.digital.unload_all_patterns()
        for pattern in glob.glob(settings["NIDigital"]["patterns"]):
            print(pattern)
            #TODO you can remove this grep and just do the single pattern that is all that is needed now
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
            for sl in self.sls:
                # Configure NI-Digital current read measurements
                self.digital.channels[sl].ppmu_aperture_time = self.op["READ"]["aperture_time"]
                self.digital.channels[sl].ppmu_aperture_time_units = nidigital.PPMUApertureTimeUnits.SECONDS
                self.digital.channels[sl].ppmu_output_function = nidigital.PPMUOutputFunction.VOLTAGE
                self.digital.channels[sl].ppmu_current_limit_range = self.op["READ"]["current_limit_range"]
        else:
            raise NIRRAMException("Invalid READ mode specified in settings")

        # set body voltages
        for body_i, vbody_i in self.body.items(): self.ppmu_set_vbody(body_i, vbody_i)

        # Set address and all voltages to 0
        for bl in self.all_bls: self.set_vbl(bl, 0.0, 0.0)
        for sl in self.all_sls: self.set_vsl(sl, 0.0, 0.0)
        for wl in self.all_wls: self.set_vwl(wl, 0.0, 0.0)
        self.digital.commit()

    def close(self):
        """Do cleanup and then close all NI sessions"""
        if not self.closed:
            # set all body voltages back to zero
            for body_i in self.body.keys(): self.ppmu_set_vbody(body_i, 0.0)
            print("[close] set body")
            self.ppmu_all_pins_to_zero()

            # Close NI-Digital
            # print("[close] TRY digital.close()", self.digital.is_done())
            # self.digital.close()
            # print("[close] COMPLETED digital.close()")

            # Close log files
            self.mlogfile.close()
            print("[close] mlogfile.close()")
            self.plogfile.close()
            print("[close] plogfile.close()")
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


    def read(
        self,
        vbl=None,
        vsl=None,
        vwl=None,
        vwl_unsel_offset=None,
        vb=None,
        record=False,
    ):
        """Perform a READ operation. This operation works for single 1T1R devices and 
        arrays of devices, where each device has its own WL/BL.
        Returns list (per-bitline) of tuple with (res, cond, meas_i, meas_v)"""
        # Increment the number of READs        
        # Set the read voltage levels
        vbl = self.op["READ"][self.polarity]["VBL"] if vbl is None else vbl
        vwl = self.op["READ"][self.polarity]["VWL"] if vwl is None else vwl
        vsl = self.op["READ"][self.polarity]["VSL"] if vsl is None else vsl
        vb = self.op["READ"][self.polarity]["VB"] if vb is None else vb

        # unselected WL bias parameter
        if vwl_unsel_offset is None:
            if "VWL_UNSEL_OFFSET" in self.op["READ"][self.polarity]:
                vwl_unsel_offset = self.op["READ"][self.polarity]["VWL_UNSEL_OFFSET"]
            else:
                vwl_unsel_offset = 0.0
        
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
                    if wl_i == wl:
                        self.ppmu_set_vwl(wl_i, vwl)
                    else: # UNSELECTED WLs: set to ~vsl with some offset (to reduce bias)
                        self.ppmu_set_vwl(wl_i, vsl + vwl_unsel_offset)
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
        # self.digital_all_off(self.op["READ"]["relaxation_cycles"])
        self.ppmu_all_pins_to_zero()
        time.sleep(self.op["READ"]["settling_time"]) # let the supplies settle
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
        self.ppmu_all_pins_to_zero()

        # Log operation to master file
        # self.mlogfile.write(f"{self.chip},{time.time()},{self.addr},")
        # self.mlogfile.write(f"READ,{res},{cond},{meas_i},{meas_v}\n")
        # Return measurement results
        return res_array, cond_array, meas_i_array, meas_v_array

    def set_pulse(
        self,
        mask,
        mode="SET",
        bl_selected=None, # selected BL
        vwl=None,
        vbl=None,
        vsl=None,
        vbl_unsel=None,
        vwl_unsel_offset=None,
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
        vwl = vwl if vwl is not None else self.op[mode][self.polarity]["VWL"]
        vbl = vbl if vbl is not None else self.op[mode][self.polarity]["VBL"]
        vsl = vsl if vsl is not None else self.op[mode][self.polarity]["VSL"]
        vbl_unsel = vbl_unsel if vbl_unsel is not None else vsl + ((vbl - vsl) / 2.0)
        pulse_len = pulse_len if pulse_len is not None else self.op[mode][self.polarity]["PW"] 
        
        self.digital.channels[self.all_channels].write_static(nidigital.WriteStaticPinState.X)

        # unselected WL bias parameter
        if vwl_unsel_offset is None:
            if "VWL_UNSEL_OFFSET" in self.op[mode][self.polarity]:
                vwl_unsel_offset = self.op[mode][self.polarity]["VWL_UNSEL_OFFSET"]
            else:
                vwl_unsel_offset = 0.0
        
        # set voltages
        for bl_i in self.bls:
            if bl_selected is not None: # selecting specific bl, unselecting others
                vbl_i = vbl if bl_i == bl_selected else vbl_unsel
            else:
                vbl_i = vbl
            # print(f"Setting BL {bl_i} to {vbl_i} V")
            self.set_vbl(bl_i, vbl = vbl_i, vbl_lo = vsl)
        
        for sl_i in self.sls:
            # print(f"Setting SL {sl_i} to {vsl} V")
            self.set_vsl(sl_i, vsl = vsl, vsl_lo = vsl)
        
        # Unselected Wls add in bias
        for wl_i in self.all_wls: 
            if wl_i in self.wls:
                self.set_vwl(wl_i, vwl_hi = vwl, vwl_lo = vsl)
            else:
                self.set_vwl(wl_i, vwl_hi = vsl, vwl_lo = vsl + vwl_unsel_offset)

        # Update the voltages    
        self.digital.commit()

        # Issue the pulse
        self.pulse(mask, pulse_len=pulse_len)

        # Turn everything off high Z
        self.digital_all_pins_to_zero()

        # # reset to high Z
        # for wl_i in self.wls:
        #     self.digital.channels[wl_i].termination_mode = nidigital.TerminationMode.HIGH_Z

        # Log the pulse
        #self.mlogfile.write(f"{self.chip},{time.time()},{self.addr},")
        #self.mlogfile.write(f"SET,{vwl},{vbl},0,{pulse_width}\n")

    def reset_pulse(
        self,
        mask,
        mode="RESET",
        bl_selected=None, # selected BL
        vwl=None,
        vbl=None,
        vsl=None,
        vbl_unsel=None,
        vwl_unsel_offset=None,
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
        vwl = vwl if vwl is not None else self.op[mode][self.polarity]["VWL"]
        vbl = vbl if vbl is not None else self.op[mode][self.polarity]["VBL"]
        vsl = vsl if vsl is not None else self.op[mode][self.polarity]["VSL"]
        vbl_unsel = vbl_unsel if vbl_unsel is not None else vsl + ((vbl - vsl) /1.1)
        pulse_len = pulse_len if pulse_len is not None else self.op[mode][self.polarity]["PW"] 
        # unselected WL bias parameter
        if vwl_unsel_offset is None:
            if "VWL_UNSEL_OFFSET" in self.op[mode][self.polarity]:
                vwl_unsel_offset = self.op[mode][self.polarity]["VWL_UNSEL_OFFSET"]
            else:
                vwl_unsel_offset = 0.0


        self.digital.channels[self.all_channels].write_static(nidigital.WriteStaticPinState.X)

        # set voltages
        
        for wl_i in self.all_wls:
            if wl_i in self.wls:
                self.set_vwl(wl_i, vwl_hi = vwl, vwl_lo = vbl)
            else:
                # Unselected Wls add in bias
                self.set_vwl(wl_i, vwl_hi = vbl, vwl_lo = vbl + vwl_unsel_offset)

        for bl_i in self.bls:
            if bl_selected is not None: 
                # selecting specific bl, unselecting others
                vbl_i = vbl if bl_i == bl_selected else vbl_unsel
            else:
                vbl_i = vbl
            # print(f"Setting BL {bl_i} to {vbl_i} V")
            self.set_vbl(bl_i, vbl = vbl_i, vbl_lo = vbl_i)

        for sl_i in self.sls:
            # print(f"Setting SL {sl_i} to {vsl} V")
            self.set_vsl(sl_i, vsl = vsl, vsl_lo = vbl)

        # Update the voltages    
        self.digital.commit()

        # Issue the pulse
        self.pulse(mask, pulse_len=pulse_len)

        # Turn everything off high Z
        self.digital_all_pins_to_zero()

        # Log the pulse
        #self.mlogfile.write(f"{self.chip},{time.time()},{self.addr},")
        #self.mlogfile.write(f"RESET,{vwl},0,{vsl},{pulse_width}\n")
    
    def digital_all_pins_to_zero(self):
        """
        High z down to zero
        """
        self.digital.channels[self.all_channels].write_static(nidigital.WriteStaticPinState.X)
        for chan in self.all_channels:
            self.digital.channels[chan].configure_voltage_levels(0, 0, 0, 0, 0)
        self.digital.commit()

        return
     
    def ppmu_all_pins_to_zero(self):
        """ 
        Cleans up after PPMU operation (otherwise levels default when going back digital)
        """
        for chan in self.all_channels:
            self.digital.channels[chan].ppmu_voltage_level = 0
        self.digital.ppmu_source()
        return
    
    def set_vsl(self, vsl_chan, vsl, vsl_lo):
        """Set VSL using NI-Digital driver"""
        assert(vsl_chan in self.all_sls)
        self.digital.channels[vsl_chan].configure_voltage_levels(vsl_lo, vsl, vsl_lo, vsl, 0)
        #print("Setting VSL: " + str(vsl) + " on chan: " + str(vsl_chan))
        return

    def set_vbl(self, vbl_chan, vbl, vbl_lo):
        """Set (active) VBL using NI-Digital driver (inactive disabled)"""
        assert(vbl_chan in self.all_bls)
        self.digital.channels[vbl_chan].configure_voltage_levels(vbl_lo, vbl, vbl_lo, vbl, 0)
        return

    def set_vwl(self, vwl_chan, vwl_hi, vwl_lo):
        """Set (active) VWL using NI-Digital driver (inactive disabled)"""
        assert(vwl_chan in self.all_wls)
        self.digital.channels[vwl_chan].configure_voltage_levels(vwl_lo, vwl_hi, vwl_lo, vwl_hi, 0)
        return

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
    
    def ppmu_set_all_to_voltage(self, val, vwl_chan=None, vsl_chan=None, vbl_chan=None):
        """Set all VWL, VSL, VBL at once to a single value. Used for boosting
        voltages to a different level, e.g. for NBTI script.
        """
        assert(val <= 6)
        assert(val >= -2)
        if vwl_chan is not None:
            assert(vwl_chan in self.all_wls)
        if vsl_chan is not None:
            assert(vsl_chan in self.all_sls)
        if vbl_chan is not None:
            assert(vbl_chan in self.all_bls)
        
        if vwl_chan is not None:
            self.digital.channels[vwl_chan].ppmu_voltage_level = val
        if vsl_chan is not None:
            self.digital.channels[vsl_chan].ppmu_voltage_level = val
        if vbl_chan is not None:
            self.digital.channels[vbl_chan].ppmu_voltage_level = val
        self.digital.ppmu_source()

    def ppmu_set_vbody(self, vbody_chan, vbody):
        """Set VBODY using NI-Digital driver"""
        assert(vbody <= 3)
        assert(vbody >= -1)
        assert(vbody_chan in self.body)
        self.digital.channels[vbody_chan].ppmu_voltage_level = vbody
        self.digital.channels[vbody_chan].ppmu_current_limit_range = 32e-6
        self.digital.channels[vbody_chan].ppmu_source()
        #print("Setting VSL: " + str(vsl) + " on chan: " + str(vsl_chan))

    #TODO
    #max_pulse length must be leass than the prepulse_len + postpulse_len + pulse_lne
    #WL_first is currently defaulting off
    def pulse(self, mask, pulse_len=10, prepulse_len=2, postpulse_len=0, max_pulse_len=10000, wl_first=True):
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
            if not wl_first:
                wl_pre_post_bits = BitVector(bitlist=(wl_mask & False)).int_val()
                wl_mask_bits = BitVector(bitlist=wl_mask).int_val()
                bl_mask_bits = BitVector(bitlist=bl_mask).int_val()
                sl_mask_bits = BitVector(bitlist=sl_mask).int_val()

                data_prepulse = (bl_mask_bits << bl_bits_offset) + (sl_mask_bits << sl_bits_offset) + wl_pre_post_bits
                data = (bl_mask_bits << bl_bits_offset) + (sl_mask_bits << sl_bits_offset) + wl_mask_bits
                data_postpulse = (bl_mask_bits << bl_bits_offset) + (sl_mask_bits << sl_bits_offset)  + wl_pre_post_bits
            else: 
                bl_pre_post_bits = BitVector(bitlist=(bl_mask & False)).int_val()
                sl_pre_post_bits = BitVector(bitlist=(sl_mask & False)).int_val()
                wl_mask_bits = BitVector(bitlist=wl_mask).int_val()
                bl_mask_bits = BitVector(bitlist=bl_mask).int_val()
                sl_mask_bits = BitVector(bitlist=sl_mask).int_val()

                data_prepulse = (bl_pre_post_bits << bl_bits_offset) + (sl_pre_post_bits << sl_bits_offset) + wl_mask_bits
                data = (bl_mask_bits << bl_bits_offset) + (sl_mask_bits << sl_bits_offset) + wl_mask_bits
                data_postpulse = (bl_pre_post_bits << bl_bits_offset) + (sl_pre_post_bits << sl_bits_offset)  + wl_mask_bits
           
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
        return

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
        """Performs SET pulses in increasing fashion until resistance reaches
        target_res (either input or in the `target_res` config).
        This will try to SET ALL CELLS in self.bls and self.wls.
        Returns tuple (res, cond, meas_i, meas_v, success).
        """
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
            print(pw)
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
                    self.ppmu_all_pins_to_zero()
                    
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
        temp_int = 0
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
                    self.ppmu_all_pins_to_zero()
                    
                    # use settling if parameter present, to discharge parasitic cap
                    if "settling_time" in self.op[mode]:
                        time.sleep(self.op[mode]["settling_time"])
                    
                    # read result resistance
                    res_array, cond_array, meas_i_array, meas_v_array = read_pulse()
                    
                    if bl_selected is None: # use array success condition: all in array must hit target
                        for wl_i in self.wls:
                            for bl_i in self.bls:
                                print(res_array.loc[wl_i,bl_i])
                                if (res_array.loc[wl_i, bl_i] >= target_res) & mask.mask.loc[wl_i, bl_i]:
                                    mask.mask.loc[wl_i, bl_i] = False
                        success = (mask.mask.to_numpy().sum() == 0)
                    else: # 1TNR success condition: check if selected 1tnr cell hit target
                        success = True
                        
                        for wl_i in self.wls:
                            # if temp_int == 50:
                            #     print([res_array.loc[wl_i,"BL_0"],res_array.loc[wl_i,"BL_1"]])
                            #     temp_int = 0
                            # else:
                            #     temp_int += 1
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
    
    def sample_resistance_at_bias(
        self,
        mode, # used to get config settings
        initialize_cell_fn, # use bound method, either nisys.dynamic_reset or nisys.dynamic_set
        pulse_fn, # use bound method, either nisys.reset_pulse or nisys.set_pulse
        bl = None, # bl to use
        sl = None, # sl to use
        wl = None, # wl to use
        vbl_sweep = None, # vbl sweep
        vsl_sweep = None, # vsl sweep
        vwl_sweep = None, # vwl sweep
        samples: int = 100,
        pw: int = 1, # pulse width
        debug: bool = False,
    ) -> dict:
        """
        Use this to create a plot of mean + variance of resistance
        from setting/resetting rram versus bias conditions vbl, vsl, vwl.

        This function sweeps vbl, vsl, vwl and samples rram resistances
        measured after applying that bias onto a cleared cell.
        Basic concept of operation is,

            pw = 10 # some fixed constant pulse width, e.g. 10 us

            for vbl, vsl, vwl in sweeps:
                res_samples = []
                for n in range(samples):
                    initialize_cell_fn() # either reset or set to initial condition
                    res = pulse_fn(vbl, vsl, vwl, pw)
                    res_samples.append(res)
                save(res_samples, vbl, vsl, vwl, pw) 

        With results, we can plot a matrix of mean/variance of resistance
        from the pulse operation.

        Note: Written only for single 1T1R cell, does not support 1TNR.
        """
        from itertools import product

        bl = bl if bl is not None else self.bls[0]
        sl = sl if sl is not None else self.sls[0]
        wl = wl if wl is not None else self.wls[0]
        pw = int(pw) # make sure pulse width is an integer

        # operation config
        cfg = self.op[mode][self.polarity]

        # settling time
        settling_time = cfg["settling_time"] if "settling_time" in cfg else None

        # create sweeps if input sweep is None
        def get_sweep_from_config(
            var: str,
            var_start: str,
            var_stop: str,
            var_step: str,
        ):
            """Create sweep from cfg file. First checks if sweep
            start/stop/step variables are defined and create linear sweep
            from those parameters. If not defined, try to make a single
            sweep point list from the fixed value defined.
            """
            if var_start in cfg and var_stop in cfg and var_step in cfg:
                var_sweep = util.linear_sweep({"start": cfg[var_start], "stop": cfg[var_stop], "step": cfg[var_step]})
            elif var in cfg:
                var_sweep = [cfg[var]]
            else:
                raise ValueError(f"No {var} sweep specified and no sweep or value in config")
            return var_sweep
        
        if vbl_sweep is None:
            vbl_sweep = get_sweep_from_config(var="VBL", var_start="VBL_start", var_stop="VBL_stop", var_step="VBL_step")
        if vsl_sweep is None:
            vsl_sweep = get_sweep_from_config(var="VSL", var_start="VSL_start", var_stop="VSL_stop", var_step="VSL_step")
        if vwl_sweep is None:
            vwl_sweep = get_sweep_from_config(var="VWL", var_start="VWL_start", var_stop="VWL_stop", var_step="VWL_step")

        if debug:
            print(f"vbl_sweep: {vbl_sweep}")
            print(f"vsl_sweep: {vsl_sweep}")
            print(f"vwl_sweep: {vwl_sweep}")
        
        # data to save:
        # - bias sweeps and pw configs
        # - res sample dict mapping each sweep point tuple (vbl, vsl, vwl) => list of sample resistances
        res_samples_at_bias = {
            "mode": mode,
            "samples": samples,
            "target_res_hrs": self.target_res.get("RESET", 0),
            "target_res_lrs": self.target_res.get("SET", 0),
            "vbl_sweep": vbl_sweep,
            "vsl_sweep": vsl_sweep,
            "vwl_sweep": vwl_sweep,
            "pw": pw,
            "settling_time": settling_time,
            "res": {}, # map (vbl, vsl, vwl) => list of sample resistances
        }

        failed = False # flag to indicate cell initialization failed

        mask = RRAMArrayMask([wl], [bl], [sl], self.all_wls, self.all_bls, self.all_sls, self.polarity)

        for vbl, vsl, vwl in product(vbl_sweep, vsl_sweep, vwl_sweep):
            # print current sample bias point
            print(f"sampling @ vbl={vbl}, vsl={vsl}, vwl={vwl}, pw={pw}")
            res_samples = []
            for _n in range(samples):
                # initialize cell (dynamic reset or dynamic set), if failed exit
                self.dynamic_reset() # do set/reset cycle, otherwise we can end up in overset or overform state which messes up sampling
                self.dynamic_set()
                response = initialize_cell_fn()
                
                success = response[0][-1] # "cell_success" variable
                if not success:
                    print("FAILED TO INITIALIZE CELL...BREAKING SWEEP...")
                    failed = True
                    break
                
                # use settling if present
                if settling_time is not None:
                    time.sleep(settling_time)
                
                pulse_fn(
                    mask,
                    vbl=vbl,
                    vsl=vsl,
                    vwl=vwl,
                    pulse_len=pw,
                )

                # use settling if present
                if settling_time is not None:
                    time.sleep(settling_time)
                
                # read result resistance
                res_array, cond_array, meas_i_array, meas_v_array = self.read(record=True)
                res = res_array.loc[wl, bl]
                res_samples.append(res)
            
            # do mean/variance statistics
            if len(res_samples) > 1:
                res_samples = np.array(res_samples)
                res_mean = np.mean(res_samples)
                res_median = np.median(res_samples)
                res_std = np.std(res_samples)

                # save res_samples and statistics
                res_samples_at_bias["res"][vbl, vsl, vwl] = {
                    "mean": res_mean,
                    "median": res_median,
                    "std": res_std,
                    "values": res_samples,
                }

            # if failed to initialize cell, early exit
            if failed:
                break

        return res_samples_at_bias
    
    def targeted_dynamic_set(
        self,
        mode,
        record=True,
        print_data=True,        # print data to console
        max_attempts: int = 10, # max number of attempts before failing and exiting
        is_1tnr = False,        # if True, use 1TNR methods
        bl_selected = None,     # for 1TNR: if not None, use this selected bl
        debug=True,             # print additional debugging lines
    ):
        """
        Coarse/fine set within a resistance window
        """
        from itertools import product

        # unpack operation config
        cfg = self.op[mode][self.polarity]
        pw = int(cfg["PW"])
        res_high_coarse = cfg["res_high_coarse"]
        res_high_fine = cfg["res_high_fine"]
        res_low = cfg["res_low"]
        vsl = cfg["VSL"]

        # coarse sweep params
        vwl_coarse_start = cfg["VWL_coarse_start"]
        vwl_coarse_stop = cfg["VWL_coarse_stop"]
        vwl_coarse_step = cfg["VWL_coarse_step"]
        vbl_coarse_start = cfg["VBL_coarse_start"]
        vbl_coarse_stop = cfg["VBL_coarse_stop"]
        vbl_coarse_step = cfg["VBL_coarse_step"]
        vwl_coarse_sweep = util.linear_sweep({"start": vwl_coarse_start, "stop": vwl_coarse_stop, "step": vwl_coarse_step})
        vbl_coarse_sweep = util.linear_sweep({"start": vbl_coarse_start, "stop": vbl_coarse_stop, "step": vbl_coarse_step})
        
        # fine window
        vwl_fine_window_high = cfg["VWL_fine_window_high"]
        vwl_fine_window_low = cfg["VWL_fine_window_low"]
        vwl_fine_step = cfg["VWL_fine_step"]
        vwl_fine_limit = cfg["VWL_fine_limit"]
        vbl_fine_window_high = cfg["VBL_fine_window_high"]
        vbl_fine_window_low = cfg["VBL_fine_window_low"]
        vbl_fine_step = cfg["VBL_fine_step"]
        vbl_fine_limit = cfg["VBL_fine_limit"]

        # settling time function
        settling_time = cfg["settling_time"] if "settling_time" in cfg else None
        if settling_time is not None:
            def settling_delay(): time.sleep(settling_time)
        else:
            def settling_delay(): pass
            
        # select read method based on array or 1TNR device
        read_pulse = self.read_1tnr if is_1tnr else self.read

        # perform coarse/fine multibit steps
        for _n in range(max_attempts):
            if debug: print(f"{mode} STEP {_n}")

            # run initialization sequence: do reset/set/reset cycle
            self.dynamic_reset(record=True, print_data=debug)
            settling_delay()
            self.dynamic_set(record=True, print_data=debug)
            settling_delay()
            self.dynamic_reset(record=True, print_data=debug)
            settling_delay()

            # flag that any cell over-set past `res_low` threshold
            failed_res_too_low = False

            # COARSE SET SWEEP
            # bl/wl mask
            mask = RRAMArrayMask(self.wls, self.bls, self.sls, self.all_wls, self.all_bls, self.all_sls, self.polarity)
            coarse_success = False
            for vwl, vbl in product(vwl_coarse_sweep, vbl_coarse_sweep):
                if debug: print(pw, vwl, vbl, vsl)

                self.set_pulse(
                    mask,
                    bl_selected=bl_selected, # specific selected BL for 1TNR
                    vbl=vbl,
                    vsl=vsl,
                    vwl=vwl,
                    pulse_len=pw,
                )
                
                # use settling if parameter present, to discharge parasitic cap and FET NBTI
                settling_delay()

                # read result resistance
                res_array, cond_array, meas_i_array, meas_v_array = read_pulse()
                #print(res_array)
                
                # success condition: each cell res in range [res_low, res_high_coarse]
                # TODO: we can abstract this out
                if bl_selected is None:
                    for wl_i in self.wls:
                        for bl_i in self.bls:
                            if res_array.loc[wl_i, bl_i] <= res_low:
                                failed_res_too_low = True
                            if (res_array.loc[wl_i, bl_i] <= res_high_coarse) & mask.mask.loc[wl_i, bl_i]:
                                mask.mask.loc[wl_i, bl_i] = False
                    coarse_success = (mask.mask.to_numpy().sum()==0)
                else: # 1TNR success condition: check if selected 1tnr cell hit target
                    coarse_success = True
                    for wl_i in self.wls:
                        if res_array.loc[wl_i, bl_selected] <= res_low:
                            failed_res_too_low = True
                        if (res_array.loc[wl_i, bl_selected] > res_high_coarse) & mask.mask.loc[wl_i, bl_selected]:
                            coarse_success = False
                            break
                
                if coarse_success or failed_res_too_low:
                    break
            
            if failed_res_too_low:
                if debug: print(f"FAILED COARSE: cell res <= {res_low}...")
                continue # try again from beginning
            elif not coarse_success:
                if debug: print(f"FAILED COARSE: not all cells in coarse range res <= {res_high_coarse}")
                continue # try again from beginning
            
            # use successful coarse conditions as "center" point to
            # create a window for new fine voltage sweep
            # clamp these values using "fine_limit" so our window
            # does not overset device
            vwl_fine_start = vwl + vwl_fine_window_high
            vwl_fine_stop = vwl + vwl_fine_window_low
            if vwl_fine_step < 0:
                vwl_fine_stop = max(vwl_fine_stop, vwl_fine_limit)
            else:
                vwl_fine_stop = min(vwl_fine_stop, vwl_fine_limit)
            
            vbl_fine_start = vbl + vbl_fine_window_high
            vbl_fine_stop = vbl + vbl_fine_window_low
            if vbl_fine_step < 0:
                vbl_fine_stop = max(vbl_fine_stop, vbl_fine_limit)
            else:
                vbl_fine_stop = min(vbl_fine_stop, vbl_fine_limit)

            vwl_fine_sweep = util.linear_sweep({"start": vwl_fine_start, "stop": vwl_fine_stop, "step": vwl_fine_step})
            vbl_fine_sweep = util.linear_sweep({"start": vbl_fine_start, "stop": vbl_fine_stop, "step": vbl_fine_step})

            # FINE SET SWEEP
            # bl/wl mask
            mask = RRAMArrayMask(self.wls, self.bls, self.sls, self.all_wls, self.all_bls, self.all_sls, self.polarity)
            fine_success = False
            for vwl, vbl in product(vwl_fine_sweep, vbl_fine_sweep):
                #print(pw, vwl, vbl, vsl)
                self.set_pulse(
                    mask,
                    bl_selected=bl_selected, # specific selected BL for 1TNR
                    vbl=vbl,
                    vsl=vsl,
                    vwl=vwl,
                    pulse_len=pw,
                )
                
                # use settling if parameter present, to discharge parasitic cap and FET NBTI
                settling_delay()

                # read result resistance
                res_array, cond_array, meas_i_array, meas_v_array = read_pulse()
                #print(res_array)
                
                # success condition: each cell res in range [res_low, res_high_fine]
                # TODO: we can abstract this out
                if bl_selected is None:
                    for wl_i in self.wls:
                        for bl_i in self.bls:
                            if res_array.loc[wl_i, bl_i] <= res_low:
                                failed_res_too_low = True
                            if (res_array.loc[wl_i, bl_i] <= res_high_fine) & mask.mask.loc[wl_i, bl_i]:
                                mask.mask.loc[wl_i, bl_i] = False
                    fine_success = (mask.mask.to_numpy().sum()==0)
                else: # 1TNR success condition: check if selected 1tnr cell hit target
                    fine_success = True
                    for wl_i in self.wls:
                        if res_array.loc[wl_i, bl_selected] <= res_low:
                            failed_res_too_low = True
                        if (res_array.loc[wl_i, bl_selected] > res_high_fine) & mask.mask.loc[wl_i, bl_selected]:
                            fine_success = False
                            break
                
                if fine_success or failed_res_too_low:
                    break
            
            if failed_res_too_low:
                if debug: print(f"FAILED FINE: cell res <= {res_low}...")
                continue # try again from beginning
            
            if fine_success:
                break # SUCCESS!!!
        
        # report final cell results
        all_data = []
        for wl in self.wls:
            for bl in self.bls:
                cell_success = res_array.loc[wl,bl] <= res_high_fine and res_array.loc[wl,bl] >= res_low
                cell_data = [self.chip, self.device, mode, wl, bl, res_array.loc[wl,bl], cond_array.loc[wl,bl], meas_i_array.loc[wl,bl], meas_v_array.loc[wl,bl], vwl, vsl, vbl, pw, cell_success]
                if print_data: print(cell_data)
                if record: self.datafile.writerow(cell_data)
                all_data.append(cell_data)

        return all_data


    def targeted_intermediate_set_radar_method(
        self,
        res_high: float = None,       # resistance high bound for stopping reset before setting
        res_coarse_min: float = None, # coarse resistance window min
        res_coarse_max: float = None, # coarse resistance window max
        res_fine_min: float = None,   # fine resistance window min, final resistance target
        res_fine_max: float = None,   # fine resistance window max, final resistance target
        max_coarse_steps: int = 10,   # max number of coarse steps before failing and exiting
        max_fine_steps: int = 10,     # max number of fine steps before failing and exiting
        is_1tnr=False,                # if True, use 1TNR methods
        bl_selected=None,             # for 1TNR: if not None, use this selected bl
    ):
        """
        Perform set that targets an intermediate value, for multi-bit programming.
        Based on RADAR method by 

        This combines two passes:
        1. Coarse targeting pass:
            Goal is to enter a coarse resistance range near target
            (with max iterations `max_course_steps` before failing and exiting).

        2. Fine targeting pass:
            Goal is to enter a fine resistance range near target
            (with max iterations `max_fine_steps` before failing and exiting). 

        Currently NOT using this because I dont believe in fine resets
        -acyu
        """
        # select read method based on array or 1TNR device
        read_pulse = self.read_1tnr if is_1tnr else self.read

        # initialization: do built in set to get into res_low target
        self.dynamic_reset(target_res=res_high)

        # get initial resistance
        res_array, cond_array, meas_i_array, meas_v_array = read_pulse()

        # temporarily have additional dict to store each cells resistances
        # after each operation (need to interface between old read pulse
        # format and new RRAMOperationResult data format)
        cell_res = {}
        for wl in self.wls:
            for bl in self.bls:
                cell_res[wl, bl] = res_array.loc[wl, bl]
        
        # =====================================================================
        # COARSE SET/RESET PASS:
        # goal is to get within res range [res_coarse_min, res_coarse_max]
        # =====================================================================
        need_to_set = False
        need_to_reset = False
        # first check if coarse steps needed
        for wl in self.wls:
            for bl in self.bls:
                if cell_res[wl, bl] < res_coarse_min:
                    need_to_reset = True
                elif cell_res[wl, bl] > res_coarse_max:
                    need_to_set = True

        if need_to_set or need_to_reset:
            n_coarse = 0
            while n_coarse < max_coarse_steps:
                n_coarse += 1

                # run coarse set/reset pulses (note: INTERNALLY these functions
                # will mask off completed cells that already hit target)
                if need_to_set:
                    result = self.dynamic_pulse_for_multibit(
                        mode="SET_COARSE",
                        res_compare_op=util.Comparison.LESS_OR_EQUALS,
                        target_res=res_coarse_max,
                        is_1tnr=is_1tnr,
                        bl_selected=bl_selected,
                    )
                    # update cell resistances and `need_to_set` and `need_to_reset`
                    need_to_set = False
                    need_to_reset = False
                    for wl in self.wls:
                        for bl in self.bls:
                            res = result[wl, bl].res
                            cell_res[wl, bl] = res
                            if res < res_coarse_min:
                                need_to_reset = True
                            elif res > res_coarse_max:
                                need_to_set = True
                
                if need_to_reset:
                    result = self.dynamic_pulse_for_multibit(
                        mode="RESET_COARSE",
                        res_compare_op=util.Comparison.GREATER_OR_EQUALS,
                        target_res=res_coarse_min,
                        is_1tnr=is_1tnr,
                        bl_selected=bl_selected,
                    )
                    # update cell resistances and `need_to_set` and `need_to_reset`
                    need_to_set = False
                    need_to_reset = False
                    for wl in self.wls:
                        for bl in self.bls:
                            res = result[wl, bl].res
                            cell_res[wl, bl] = res
                            if res < res_coarse_min:
                                need_to_reset = True
                            elif res > res_coarse_max:
                                need_to_set = True
        
        # =====================================================================
        # FINE SET/RESET PASS:
        # goal is to get within res range [res_fine_min, res_fine_max]
        # =====================================================================
        need_to_set = False
        need_to_reset = False
        # first check if fine steps needed
        for wl in self.wls:
            for bl in self.bls:
                if cell_res[wl, bl] < res_fine_min:
                    need_to_reset = True
                elif cell_res[wl, bl] > res_fine_max:
                    need_to_set = True
        
        if need_to_set or need_to_reset:
            n_fine = 0
            for n_fine in range(max_fine_steps):
                n_fine += 1

                # run fine set/reset pulses (note: INTERNALLY these functions
                # will mask off completed cells that already hit target)
                if need_to_set:
                    result = self.dynamic_pulse_for_multibit(
                        mode="SET_FINE",
                        res_compare_op=util.Comparison.LESS_OR_EQUALS,
                        target_res=res_fine_max,
                        is_1tnr=is_1tnr,
                        bl_selected=bl_selected,
                    )
                    # update cell resistances and `need_to_set` and `need_to_reset`
                    need_to_set = False
                    need_to_reset = False
                    for wl in self.wls:
                        for bl in self.bls:
                            res = result[wl, bl].res
                            cell_res[wl, bl] = res
                            if res < res_fine_min:
                                need_to_reset = True
                            elif res > res_fine_max:
                                need_to_set = True
                
                if need_to_reset:
                    result = self.dynamic_pulse_for_multibit(
                        mode="RESET_FINE",
                        res_compare_op=util.Comparison.GREATER_OR_EQUALS,
                        target_res=res_fine_min,
                        is_1tnr=is_1tnr,
                        bl_selected=bl_selected,
                    )
                    # update cell resistances and `need_to_set` and `need_to_reset`
                    need_to_set = False
                    need_to_reset = False
                    for wl in self.wls:
                        for bl in self.bls:
                            res = result[wl, bl].res
                            cell_res[wl, bl] = res
                            if res < res_fine_min:
                                need_to_reset = True
                            elif res > res_fine_max:
                                need_to_set = True


    def dynamic_pulse_for_multibit(
        self,
        mode,
        res_compare_op: util.Comparison, # comparison enum type indicating <=, >=, == operator to compare to target_res
        target_res=None,                 # target res, if None will use value in settings
        record=True,                     # if True, record data to file
        print_data=True,                 # print data to console
        is_1tnr=False,                   # if 1TNR device, do different type of read
        bl_selected=None,                # select specific bl for 1TNR measurements
        debug=True,                      # if True, print additional debug info
    ) -> dict[tuple[str, str], RRAMOperationResult]:
        """Performs BL pulses in increasing fashion until resistance meets
        `target_res` goal based on `res_compare_op` (e.g. `res <= target_res`
        or `res >= target_res`).

        Input has a `res_compare_op` enum which is also a callable function that
        does `res_compare_op(a, b)` ---> `a CMP b`, where CMP becomes an
        operator like <= or >=. Typically use:
        - reset: Comparison.GREATER_OR_EQUALS ---> `res >= target_res`
        - set: Comparison.LESS_OR_EQUALS ---> `res <= target_res`

        Returns a dict mapping WL, BL locations to a RRAMOperationResult 
        with operation results: `result[WL, BL] -> RRAMOperationResult`
        """
        # Get settings
        cfg = self.op[mode][self.polarity]
        target_res = target_res if target_res is not None else self.target_res[mode]
        vbl = cfg["VBL"]

        # select read method
        read_pulse = self.read_1tnr if is_1tnr else self.read

        # get initial resistance
        res_array, cond_array, meas_i_array, meas_v_array = read_pulse()

        # create cell pulse mask, indicates cells to send pulses to
        mask = RRAMArrayMask(self.wls, self.bls, self.sls, self.all_wls, self.all_bls, self.all_sls, self.polarity)
        for wl in self.wls:
            for bl in self.bls:
                if mask.mask.loc[wl,bl] & res_compare_op(res_array.loc[wl,bl], target_res):
                    mask.mask.loc[wl,bl] = False
            # if all cells meet target, we can skip running
            success = (mask.mask.to_numpy().sum() == 0)
        
        if success == False:
            # sweep value lists
            vwl_sweep = util.linear_sweep({"start": cfg[f"VWL_start"], "stop": cfg[f"VWL_stop"], "step": cfg[f"VWL_step"]})
            vsl_sweep = util.linear_sweep({"start": cfg["VSL_start"], "stop": cfg["VSL_stop"], "step": cfg["VSL_step"]})
            pw_sweep = util.log10_sweep({"start": cfg["PW_start"], "stop": cfg["PW_stop"], "steps": cfg["PW_steps"]})
            if debug:
                print(f"vwl_sweep: {vwl_sweep}")
                print(f"vsl_sweep: {vsl_sweep}")
                print(f"pw_sweep: {pw_sweep}")

            # Iterative pulse-verify
            # order is try increase PW, then increase VSL, then try increase VWL 
            for vwl in vwl_sweep:
                for vsl in vsl_sweep:
                    for pw in pw_sweep:
                        self.reset_pulse( # TODO: MAKE THIS A GENERALIZED PULSE FOR THIS OP
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

                        res_array, cond_array, meas_i_array, meas_v_array = read_pulse()
                        for wl in self.wls:
                            for bl in self.bls:
                                if mask.mask.loc[wl,bl] & res_compare_op(res_array.loc[wl,bl], target_res):
                                    mask.mask.loc[wl,bl] = False
                        success = (mask.mask.to_numpy().sum() == 0)
                        if success:
                            break
                    if success:
                        break
                if success:
                    break
        
        # record final cell results
        all_data = {} # dict with all cell results
        for wl in self.wls:
            for bl in self.bls:
                cell_success = res_compare_op(res_array.loc[wl,bl], target_res)
                cell_data = [self.chip, self.device, mode, wl, bl, res_array.loc[wl,bl], cond_array.loc[wl,bl], meas_i_array.loc[wl,bl], meas_v_array.loc[wl,bl], vwl, vsl, vbl, pw, cell_success]
                
                if print_data: print(cell_data)
                if record: self.datafile.writerow(cell_data)

                all_data[wl, bl] = RRAMOperationResult(
                    chip=self.chip,
                    device=self.device,
                    mode=mode,
                    wl=wl,
                    bl=bl,
                    res=res_array.loc[wl, bl],
                    cond=cond_array.loc[wl, bl],
                    i=meas_i_array.loc[wl, bl],
                    v=meas_v_array.loc[wl, bl],
                    vwl=vwl,
                    vsl=vsl,
                    vbl=vbl,
                    pw=pw,
                    success=cell_success,
                )
        
        return all_data

    def cnfet_pulse_cycling(
        self,
        cycles: int,
        pattern: str = "set_reset", # pulse cycling pattern, e.g. "set_reset" or "read"
        t_set: int = None,   # override t_set pulse width, in [us]
        t_reset: int = None, # override t_reset pulse width, in [us]
        t_dwell: int = None, # override t_dwell pulse width, in [us]
    ):
        """Runs sequence of pulses for `cycles` on a CNFET.
        Used for seeing cycling VT stability (e.g. NBTI/PBTI effects).
        Combine with `cnfet_spot_iv` to read voltage/current after
        each cycling sequence.
        """
        config = self.settings["cnfet"][pattern]
        pattern = config["pattern"] # ni pattern name string
        body = list(self.body)[0]
        bl = self.bls[0]
        sl = self.sls[0]
        wl = self.wls[0]

        # pulse widths
        t_set = int(t_set) if t_set is not None else int(config["t_set"])
        t_reset = int(t_reset) if t_reset is not None else int(config["t_reset"])
        t_dwell = int(t_dwell) if t_dwell is not None else int(config["t_dwell"])
        
        # unpack voltages from settings file
        # Body low/high voltage
        v_body_lo = float(config["v_body_lo"])
        v_body_hi = float(config["v_body_hi"])
        # BL low/high voltage
        v_bl_lo = float(config["v_bl_lo"])
        v_bl_hi = float(config["v_bl_hi"])
        # SL low/high voltage
        v_sl_lo = float(config["v_sl_lo"])
        v_sl_hi = float(config["v_sl_hi"])
        # WL low/high voltage
        v_wl_lo = float(config["v_wl_lo"])
        v_wl_hi = float(config["v_wl_hi"])

        # write config registers with cycles and pulse widths
        register_cycles = nidigital.SequencerRegister.REGISTER0   # number of set/reset cycles
        register_pw_set = nidigital.SequencerRegister.REGISTER1   # set pulse width
        register_pw_reset = nidigital.SequencerRegister.REGISTER2 # reset pulse width
        register_pw_dwell = nidigital.SequencerRegister.REGISTER3   # dwell time pulse width

        self.digital.write_sequencer_register(register_cycles, int(cycles))
        self.digital.write_sequencer_register(register_pw_set, t_set)
        self.digital.write_sequencer_register(register_pw_reset, t_reset)
        self.digital.write_sequencer_register(register_pw_dwell, t_dwell)

        # set ppmu hi/lo voltages
        self.digital.channels[body].configure_voltage_levels(v_body_lo, v_body_hi, v_body_lo, v_body_hi, 0.0)
        self.digital.channels[bl].configure_voltage_levels(v_bl_lo, v_bl_hi, v_bl_lo, v_bl_hi, 0.0)
        self.digital.channels[sl].configure_voltage_levels(v_sl_lo, v_sl_hi, v_sl_lo, v_sl_hi, 0.0)
        self.digital.channels[wl].configure_voltage_levels(v_wl_lo, v_wl_hi, v_wl_lo, v_wl_hi, 0.0)
        self.digital.ppmu_source()

        # make pattern X states output Vterm = 0 V
        for pin in (body, bl, sl, wl):
            self.digital.channels[pin].termination_mode = nidigital.TerminationMode.VTERM

        # pulses pattern for `cycles` (stored in register_cycles)
        try:
            self.digital.burst_pattern(
                pattern, # cnfet_pmos_pulse_cycling.digipat
                timeout=300.0, # in seconds, enough for ~100,000 cycles with 100 us set , 1000 us dwell
            ) 
        except Exception as err:
            import traceback
            print(Exception, err)
            print(traceback.format_exc())
        
        # reconfigure pins to zero voltage and reset termination modes to high-z 
        for pin in (body, bl, sl, wl):
            self.digital.channels[pin].configure_voltage_levels(0.0, 0.0, 0.0, 0.0, 0.0)
            self.digital.channels[pin].termination_mode = nidigital.TerminationMode.HIGH_Z
        self.digital.ppmu_source()

    def cnfet_spot_iv(
        self,
        v_wl,
        v_bl,
        v_sl,
        v_body = 0.0,
        current_limit_range = 32e-6, # for S/D
    ) -> dict:
        body = list(self.body)[0]
        bl = self.bls[0]
        sl = self.sls[0]
        wl = self.wls[0]

        self.digital.channels[bl].ppmu_aperture_time = self.op["READ"]["aperture_time"]
        self.digital.channels[bl].ppmu_aperture_time_units = nidigital.PPMUApertureTimeUnits.SECONDS
        self.digital.channels[bl].ppmu_output_function = nidigital.PPMUOutputFunction.VOLTAGE
        self.digital.channels[bl].ppmu_current_limit_range = current_limit_range

        self.digital.channels[sl].ppmu_aperture_time = self.op["READ"]["aperture_time"]
        self.digital.channels[sl].ppmu_aperture_time_units = nidigital.PPMUApertureTimeUnits.SECONDS
        self.digital.channels[sl].ppmu_output_function = nidigital.PPMUOutputFunction.VOLTAGE
        self.digital.channels[sl].ppmu_current_limit_range = current_limit_range

        self.digital.channels[wl].ppmu_aperture_time = self.op["READ"]["aperture_time"]
        self.digital.channels[wl].ppmu_aperture_time_units = nidigital.PPMUApertureTimeUnits.SECONDS
        self.digital.channels[wl].ppmu_output_function = nidigital.PPMUOutputFunction.VOLTAGE
        self.digital.channels[wl].ppmu_current_limit_range = 2e-6

        # set ppmu to measurement levels
        self.digital.channels[body].ppmu_voltage_level = v_body
        self.digital.channels[wl].ppmu_voltage_level = v_wl
        self.digital.channels[bl].ppmu_voltage_level = v_bl
        self.digital.channels[sl].ppmu_voltage_level = v_sl
        self.digital.ppmu_source()
        
        meas_v_bl = self.digital.channels[bl].ppmu_measure(nidigital.PPMUMeasurementType.VOLTAGE)[0]
        meas_i_bl = self.digital.channels[bl].ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)[0]
        # meas_v_sl = self.digital.channels[sl].ppmu_measure(nidigital.PPMUMeasurementType.VOLTAGE)[0]
        # meas_i_sl = self.digital.channels[sl].ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)[0]
        meas_v_wl = self.digital.channels[wl].ppmu_measure(nidigital.PPMUMeasurementType.VOLTAGE)[0]
        meas_i_wl = self.digital.channels[wl].ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)[0]

        # to ignore sl measurement
        meas_v_sl = 0
        meas_i_sl = 0

        # reset ppmu to measurement levels
        for pin in (body, wl, bl, sl):
            self.digital.channels[pin].ppmu_voltage_level = 0.0
        self.digital.ppmu_source()

        return {
            "v_bl": meas_v_bl,
            "i_bl": meas_i_bl,
            "v_sl": meas_v_sl,
            "i_sl": meas_i_sl,
            "v_wl": meas_v_wl,
            "i_wl": meas_i_wl,
        }
    
    def cnfet_iv_sweep(
        self,
        v_wl,
        v_bl,
        v_sl,
        v_body = 0.0,
        v_0 = 0.0,
        v_wl_0 = 0.0,
        current_limit_range = 32e-6, # for S/D
        measure_i_bl = True,
        measure_v_bl = False,
        measure_i_sl = False,
        measure_v_sl = False,
        measure_i_wl = False,
        measure_v_wl = False,
    ) -> dict:
        """Short IV sweep vs v_wl."""
        meas_v_bl = []
        meas_i_bl = []
        meas_v_sl = []
        meas_i_sl = []
        meas_v_wl = []
        meas_i_wl = []

        body = list(self.body)[0]
        bl = self.bls[0]
        sl = self.sls[0]
        wl = self.wls[0]

        self.digital.channels[bl].ppmu_aperture_time = self.op["READ"]["aperture_time"]
        self.digital.channels[bl].ppmu_aperture_time_units = nidigital.PPMUApertureTimeUnits.SECONDS
        self.digital.channels[bl].ppmu_output_function = nidigital.PPMUOutputFunction.VOLTAGE
        self.digital.channels[bl].ppmu_current_limit_range = current_limit_range

        self.digital.channels[sl].ppmu_aperture_time = self.op["READ"]["aperture_time"]
        self.digital.channels[sl].ppmu_aperture_time_units = nidigital.PPMUApertureTimeUnits.SECONDS
        self.digital.channels[sl].ppmu_output_function = nidigital.PPMUOutputFunction.VOLTAGE
        self.digital.channels[sl].ppmu_current_limit_range = current_limit_range

        self.digital.channels[wl].ppmu_aperture_time = self.op["READ"]["aperture_time"]
        self.digital.channels[wl].ppmu_aperture_time_units = nidigital.PPMUApertureTimeUnits.SECONDS
        self.digital.channels[wl].ppmu_output_function = nidigital.PPMUOutputFunction.VOLTAGE
        self.digital.channels[wl].ppmu_current_limit_range = 2e-6

        # set ppmu to measurement levels
        self.digital.channels[body].ppmu_voltage_level = v_body
        self.digital.channels[bl].ppmu_voltage_level = v_bl
        self.digital.channels[sl].ppmu_voltage_level = v_sl
        self.digital.ppmu_source()

        # sweep VWL
        for v_wl_i in v_wl:
            self.digital.channels[wl].ppmu_voltage_level = v_wl_i
            self.digital.ppmu_source()
            
            if measure_v_bl:
                meas_v_bl.append(self.digital.channels[bl].ppmu_measure(nidigital.PPMUMeasurementType.VOLTAGE)[0])
            if measure_i_bl:
                meas_i_bl.append(self.digital.channels[bl].ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)[0])
            if measure_v_sl:
                meas_v_sl.append(self.digital.channels[sl].ppmu_measure(nidigital.PPMUMeasurementType.VOLTAGE)[0])
            if measure_i_sl:
                meas_i_sl.append(self.digital.channels[sl].ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)[0])
            if measure_v_wl:
                meas_v_wl.append(self.digital.channels[wl].ppmu_measure(nidigital.PPMUMeasurementType.VOLTAGE)[0])
            if measure_i_wl:
                meas_i_wl.append(self.digital.channels[wl].ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)[0])

        # reset ppmu to measurement levels
        self.digital.channels[wl].ppmu_voltage_level = v_wl_0
        for pin in (body, bl, sl):
            self.digital.channels[pin].ppmu_voltage_level = v_0
        self.digital.ppmu_source()

        return {
            "v_bl": meas_v_bl,
            "i_bl": meas_i_bl,
            "v_sl": meas_v_sl,
            "i_sl": meas_i_sl,
            "v_wl": meas_v_wl,
            "i_wl": meas_i_wl,
        }

if __name__ == "__main__":
    # Basic test
    nirram = NIRRAM("C4")
    nirram.close()
