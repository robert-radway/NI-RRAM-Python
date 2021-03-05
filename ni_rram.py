"""Defines the NI RRAM controller class"""
import json
import time
import warnings
import nidaqmx
import nidcpower
import nifgen
import numpy as np
from ni_hsdio import NIHSDIO

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
    def __init__(self, chip, settings="settings.json"):
        # If settings is a string, load as JSON file
        if isinstance(settings, str):
            with open(settings) as settings_file:
                settings = json.load(settings_file)

        # Ensure settings is a dict
        if not isinstance(settings, dict):
            raise NIRRAMException(f"Settings should be a dict, got {repr(settings)}.")

        # TODO: initialize logger

        # Store/initialize parameters
        self.chip = chip
        self.settings = settings
        self.addr = 0
        self.prof = {"READs": 0, "SETs": 0, "RESETs": 0}

        # Initialize NI-HSDIO driver
        self.hsdio = NIHSDIO(**settings["HSDIO"])

        # Initialize NI-DAQmx driver for READ voltage
        self.read_chan = nidaqmx.Task()
        self.read_chan.ai_channels.add_ai_voltage_chan(settings["DAQmx"]["chanMap"]["read_ai"])
        self.read_chan.timing.cfg_samp_clk_timing(settings["READ"]["read_clk_rate"])

        # Initialize NI-DAQmx driver for WL voltages
        self.wl_ext_chans = []
        for chan in settings["DAQmx"]["chanMap"]["wl_ext"]:
            task = nidaqmx.Task()
            task.ao_channels.add_ao_voltage_chan(chan)
            task.timing.cfg_samp_clk_timing(settings["samp_clk_rate"])
            task.start()
            self.wl_ext_chans.append(task)

        # Initialize NI-DCPower driver for BL voltages
        self.bl_ext_chans = []
        for chan in settings["DCPower"]["chans"]:
            sess = nidcpower.Session(settings["DCPower"]["deviceID"], chan)
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
        self.set_address(0)

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
        meas_v = np.mean(self.read_chan.read(self.settings["READ"]["n_samples"]))
        meas_i = meas_v/self.settings["READ"]["shunt_res_value"]
        res = np.abs(self.settings["READ"]["VBL"]/meas_i - self.settings["READ"]["shunt_res_value"])
        cond = 1/res

        # Turn off VBL and VWL
        self.set_vbl(0)
        self.set_vwl(0)

        # Address decoder disable
        self.decoder_disable()

        # TODO: log READ operation

        # Return measurement tuple
        return res, cond, meas_i, meas_v

    def set_pulse(self, vwl=None, vbl=None, pw=None):
        

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
        active_bl.voltage_level = voltage
        active_bl.commit()
        inactive_bl.voltage_level = 0
        inactive_bl.commit()

    def set_vwl(self, voltage):
        """Set (active) VWL using NI-DAQmx driver (inactive disabled)"""
        # Select 8th and 9th bit to get the channel and the driver card, respectively
        active_wl_chan = (self.addr >> 8) & 0b1
        active_wl_dev = (self.addr >> 9) & 0b1
        active_wl = self.wl_ext_chans[active_wl_dev]
        inactive_wl = self.wl_ext_chans[1-active_wl_dev]

        # Write
        active_wl.write([(1-active_wl_chan)*voltage, active_wl_chan*voltage], auto_start=True)
        inactive_wl.write([0,0], auto_start=True)

    def pulse_vwl(self, voltage, pw):
        """Pulse (active) VWL using NI-DAQmx driver (inactive disabled)"""
        # Select 8th and 9th bit to get the channel and the driver card, respectively
        active_wl_chan = (self.addr >> 8) & 0b1
        active_wl_dev = (self.addr >> 9) & 0b1
        active_wl = self.wl_ext_chans[active_wl_dev]
        inactive_wl = self.wl_ext_chans[1-active_wl_dev]

        # Write
        active_wl.write([(1-active_wl_chan)*voltage, active_wl_chan*voltage], auto_start=True)
        inactive_wl.write([0,0], auto_start=True)

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

    def set_address(self, addr):
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

        # Give some time to shutdown
        time.sleep(1)

if __name__=="__main__":
    # Basic test
    nirram = NIRRAM("Chip9")
    for address in range(2000):
        nirram.set_address(address)
        if address % 100 == 0:
            print((address, nirram.read()),)
