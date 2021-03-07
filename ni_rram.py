"""Defines the NI RRAM controller class"""
import json
import time
import warnings
import nidaqmx
import nidcpower
import nifgen
import numpy as np
from nihsdio import NIHSDIO, NIHSDIOException


# Warnings become errors
warnings.filterwarnings("error")


def accurate_delay(delay):
    """Function to provide accurate time delay"""
    _ = time.perf_counter() + delay
    while time.perf_counter() < _:
        pass


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

        # Initialize RRAM logging
        self.mlogfile = open(settings["master_log_file"], "w")
        self.plogfile = open(settings["prog_log_file"], "w")
        self.mlogfile.write(f"INIT {chip}\n")

        # Store/initialize parameters
        self.settings = settings
        self.settings["chip"] = chip
        self.addr = 0
        self.prof = {"READs": 0, "SETs": 0, "RESETs": 0}

        # Initialize NI-HSDIO driver
        self.hsdio = NIHSDIO(**settings["HSDIO"])

        # Initialize NI-DAQmx driver for READ voltage
        self.read_chan = nidaqmx.Task()
        self.read_chan.ai_channels.add_ai_voltage_chan(settings["DAQmx"]["chanMap"]["read_ai"])
        read_rate, spc = settings["READ"]["read_rate"], settings["READ"]["n_samples"]
        self.read_chan.timing.cfg_samp_clk_timing(read_rate, samps_per_chan=spc)

        # Initialize NI-DAQmx driver for WL voltages
        self.wl_ext_chans = []
        for chan in settings["DAQmx"]["chanMap"]["wl_ext"]:
            task = nidaqmx.Task()
            task.ao_channels.add_ao_voltage_chan(chan)
            task.timing.cfg_samp_clk_timing(settings["samp_clk_rate"], samps_per_chan=2)
            self.wl_ext_chans.append(task)

        # Initialize NI-DCPower driver for BL voltages
        self.bl_ext_chans = []
        for chan in settings["DCPower"]["chans"]:
            sess = nidcpower.Session(settings["DCPower"]["deviceID"], chan)
            # sess.current_limit = 1 # requires aux power input
            sess.voltage_level = 0
            sess.commit()
            sess.initiate()
            self.bl_ext_chans.append(sess)

        # Initialize NI-FGen driver for SL voltage
        self.sl_ext_chan = nifgen.Session(settings["FGen"]["deviceID"])
        self.sl_ext_chan.output_mode = nifgen.OutputMode.FUNC
        self.sl_ext_chan.configure_standard_waveform(nifgen.Waveform.DC, 0.0, frequency=10000000)
        self.sl_ext_chan.initiate()

        # Set address to 0
        self.set_addr(0)


    def read(self):
        """Perform a READ operation. Returns tuple with (res, cond, meas_i, meas_v)"""
        # Increment the number of READs
        self.prof["READs"] += 1

        # Address decoder enable
        self.decoder_enable()

        # Set voltages
        self.set_vsl(0)
        self.set_vbl(self.settings["READ"]["VBL"])
        self.set_vwl(self.settings["READ"]["VWL"])

        # Settling time for VBL
        accurate_delay(self.settings["READ"]["settling_time"])

        # Measure
        self.read_chan.start()
        meas_v = np.mean(self.read_chan.read(self.settings["READ"]["n_samples"]))
        self.read_chan.wait_until_done()
        self.read_chan.stop()
        meas_i = meas_v/self.settings["READ"]["shunt_res_value"]
        res = np.abs(self.settings["READ"]["VBL"]/meas_i - self.settings["READ"]["shunt_res_value"])
        cond = 1/res

        # Turn off VBL and VWL
        self.set_vbl(0)
        self.set_vwl(0)

        # Address decoder disable
        self.decoder_disable()

        # Log operation to master file
        self.mlogfile.write(f"{self.addr},READ,{res},{cond},{meas_i},{meas_v}\n")

        # Return measurement tuple
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

        # Address decoder enable
        self.decoder_enable()

        # Set voltages
        self.set_vsl(0)
        self.set_vbl(vbl)

        # Settling time for VBL
        accurate_delay(self.settings["SET"]["settling_time"])

        # Pulse VWL
        self.pulse_vwl(vwl, pulse_width)

        # Turn off VBL
        self.set_vbl(0)

        # Settling time for VBL
        accurate_delay(self.settings["SET"]["settling_time"])

        # Address decoder disable
        self.decoder_disable()

        # Log the pulse
        self.mlogfile.write(f"{self.addr},SET,{vwl},{vbl},0\n")

    def reset_pulse(self, vwl=None, vsl=None, pulse_width=None):
        """Perform a RESET operation."""
        # Get parameters
        vwl = self.settings["RESET"]["VWL"] if vwl is None else vwl
        vsl = self.settings["RESET"]["VSL"] if vsl is None else vsl
        pulse_width = self.settings["RESET"]["PW"] if pulse_width is None else pulse_width

        # Increment the number of SETs
        self.prof["RESETs"] += 1

        # Address decoder enable
        self.decoder_enable()

        # Set voltages
        self.set_vbl(0)
        self.set_vsl(vsl)

        # Settling time for VSL
        accurate_delay(self.settings["RESET"]["settling_time"])

        # Pulse VWL
        self.pulse_vwl(vwl, pulse_width)

        # Turn off VSL
        self.set_vsl(0)

        # Settling time for VSL
        accurate_delay(self.settings["RESET"]["settling_time"])

        # Address decoder disable
        self.decoder_disable()

        # Log the pulse
        self.mlogfile.write(f"{self.addr},RESET,{vwl},0,{vsl}\n")


    def set_vsl(self, voltage):
        """Set VSL using NI-FGen driver"""
        # Set DC offset to V/2 since it is doubled by FGen for some reason
        self.sl_ext_chan.func_dc_offset = voltage/2

    def set_vbl(self, voltage):
        """Set (active) VBL using NI-DCPower driver (inactive disabled)"""
        # LSB indicates active BL channel
        active_bl_chan = (self.addr >> 0) & 0b1
        active_bl = self.bl_ext_chans[active_bl_chan]
        inactive_bl = self.bl_ext_chans[1-active_bl_chan]

        # Set voltages and commit
        inactive_bl.voltage_level = 0
        inactive_bl.commit()
        active_bl.voltage_level = voltage
        active_bl.commit()
        inactive_bl.wait_for_event(nidcpower.Event.SOURCE_COMPLETE)
        active_bl.wait_for_event(nidcpower.Event.SOURCE_COMPLETE)

    def set_vwl(self, voltage):
        """Set (active) VWL using NI-DAQmx driver (inactive disabled)"""
        # Select 8th and 9th bit to get the channel and the driver card, respectively
        active_wl_chan = (self.addr >> 8) & 0b1
        active_wl_dev = (self.addr >> 9) & 0b1
        active_wl = self.wl_ext_chans[active_wl_dev]
        inactive_wl = self.wl_ext_chans[1-active_wl_dev]

        # Write voltage to hold
        signal = [[(1-active_wl_chan)*voltage]*2, [active_wl_chan*voltage]*2]
        inactive_wl.write([[0,0],[0,0]], auto_start=True)
        inactive_wl.wait_until_done()
        inactive_wl.stop()
        active_wl.write(signal, auto_start=True)
        active_wl.wait_until_done()
        active_wl.stop()

    def set_addr(self, addr):
        """Set the address and hold briefly"""
        # Update address
        self.addr = addr

        # Extract SL and WL addresses
        sl_addr = (self.addr >> 1) & 0b1111111
        wl_addr = (self.addr >> 10) & 0b111111

        # Write addresses to corresponding HSDIO channels
        self.hsdio.write_data_across_chans("sl_addr", sl_addr)
        self.hsdio.write_data_across_chans("wl_addr", wl_addr)
        accurate_delay(self.settings["addr_hold_time"])

        # Reset profiling counters
        self.prof = {"READs": 0, "SETs": 0, "RESETs": 0}

    def pulse_vwl(self, voltage, pulse_width):
        """Pulse (active) VWL using NI-DAQmx driver (inactive disabled)"""
        # Select 8th and 9th bit to get the channel and the driver card, respectively
        active_wl_chan = (self.addr >> 8) & 0b1
        active_wl_dev = (self.addr >> 9) & 0b1
        active_wl = self.wl_ext_chans[active_wl_dev]
        inactive_wl = self.wl_ext_chans[1-active_wl_dev]

        # Configure pulse width
        active_wl.timing.cfg_samp_clk_timing(1/pulse_width, samps_per_chan=2)

        # Write pulse
        signal = [[(1-active_wl_chan)*voltage, 0], [active_wl_chan*voltage, 0]]
        inactive_wl.write([[0,0],[0,0]], auto_start=True)
        inactive_wl.wait_until_done()
        inactive_wl.stop()
        active_wl.write(signal, auto_start=True)
        active_wl.wait_until_done()
        active_wl.stop()

    def decoder_enable(self):
        """Enable decoding circuitry using digital signals"""
        self.hsdio.write_data_across_chans("wl_dec_en", 0b11)
        self.hsdio.write_data_across_chans("sl_dec_en", 0b1)
        self.hsdio.write_data_across_chans("wl_clk", 0b1)

    def decoder_disable(self):
        """Disable decoding circuitry using digital signals"""
        self.hsdio.write_data_across_chans("wl_dec_en", 0b00)
        self.hsdio.write_data_across_chans("sl_dec_en", 0b0)
        self.hsdio.write_data_across_chans("wl_clk", 0b0)


    def dynamic_set(self, target_res, scheme="PINGPONG"):
        """Performs SET pulses in increasing fashion until resistance reaches target_res.
        Returns tuple (res, cond, meas_i, meas_v, success)."""
        # Get settings
        cfg = self.settings[scheme]

        # Iterative pulse-verify
        for vwl in np.arange(cfg["VWL_start"], cfg["VWL_stop"], cfg["VWL_step"]):
            for vbl in np.arange(cfg["VBL_start"], cfg["VBL_stop"], cfg["VBL_step"]):
                self.set_pulse(vwl, vbl, cfg["SET_PW"])
            res, cond, meas_i, meas_v = self.read()
            if res <= target_res:
                success = True
                break
        else:
            success = False

        # Return results
        return res, cond, meas_i, meas_v, success

    def dynamic_reset(self, target_res, scheme="PINGPONG"):
        """Performs RESET pulses in increasing fashion until resistance reaches target_res.
        Returns tuple (res, cond, meas_i, meas_v, success)."""
        # Get settings
        cfg = self.settings[scheme]

        # Iterative pulse-verify
        for vwl in np.arange(cfg["VWL_start"], cfg["VWL_stop"], cfg["VWL_step"]):
            for vsl in np.arange(cfg["VSL_start"], cfg["VSL_stop"], cfg["VSL_step"]):
                self.reset_pulse(vwl, vsl, cfg["RESET_PW"])
            res, cond, meas_i, meas_v = self.read()
            if res >= target_res:
                success = True
                break
        else:
            success = False

        # Return results
        return res, cond, meas_i, meas_v, success

    def target(self, target_res_low, target_res_high, max_attempts=25):
        """Performs SET/RESET pulses in increasing fashion until target range is achieved.
        Returns tuple (res, cond, meas_i, meas_v, attempt, success)."""
        # Iterative pulse-verify
        for attempt in range(max_attempts):
            res, cond, meas_i, meas_v = self.read()
            if res > target_res_high:
                res, cond, meas_i, meas_v, _ = self.dynamic_set(target_res_high)
            if res < target_res_low:
                res, cond, meas_i, meas_v, _ = self.dynamic_reset(target_res_low)
            if target_res_low < res and res < target_res_high:
                success = True
                break
            else:
                success = False

        # Return results
        return res, cond, meas_i, meas_v, attempt, success


    def close(self):
        """Close all NI sessions"""
        # Close NI-HSDIO
        self.hsdio.close()

        # Close NI-DAQmx AI
        self.read_chan.close()

        # Close NI-DAQmx AOs
        for task in self.wl_ext_chans:
            task.stop()
            task.close()

        # Close NI-DCPower
        for sess in self.bl_ext_chans:
            sess.abort()
            sess.close()

        # Close NI-FGen
        self.sl_ext_chan.abort()
        self.sl_ext_chan.close()

        # Close log fiels
        self.mlogfile.close()
        self.plogfile.close()

    def __del__(self):
        # Try to close session on deletion
        try:
            self.close()
        except NIHSDIOException:
            pass


if __name__=="__main__":
    # Basic test
    nirram = NIRRAM("Chip9")
