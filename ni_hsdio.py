"""Provides Python wrapper for NI-HSDIO C library DLL. Currently implements static generation."""
from ctypes import CDLL, c_int, c_uint, create_string_buffer, pointer


class NIHSDIOException(Exception):
    """Exception produced by the NIHSDIO class"""
    def __init__(self, msg):
        super().__init__(f"NIHSDIO: {msg}")


class NIHSDIO:
    """A wrapper class for NI-HSDIO C DLL. Also includes functions for static assignment."""

    # Logic family constants
    NIHSDIO_VAL_5_0V_LOGIC = 5
    NIHSDIO_VAL_3_3V_LOGIC = 6
    NIHSDIO_VAL_2_5V_LOGIC = 7
    NIHSDIO_VAL_1_8V_LOGIC = 8
    NIHSDIO_VAL_1_5V_LOGIC = 80
    NIHSDIO_VAL_1_2V_LOGIC = 81

    def __init__(self, deviceID, chanMap=None, channelList="", logicFamily=NIHSDIO_VAL_1_8V_LOGIC):
        # Store parameters
        self.device_id = deviceID
        self.chans = channelList
        self.chan_map = chanMap if chanMap is not None else {}

        # Create driver and VI session
        self.driver = CDLL("lib/niHSDIO_64.dll")
        self.sess = c_uint(0)

        # Initialize generation session
        self.init_generation_session(deviceID)

        # Configure voltage level
        self.configure_data_voltage_logic_family(channelList, logicFamily)

        # Assign static channels
        self.assign_static_channels(channelList)

    def init_generation_session(self, device_id):
        """Wrapper function: initialize HSDIO session for digital pattern generation"""
        # Create session
        device_id = bytes(device_id, 'utf-8')
        err = self.driver.niHSDIO_InitGenerationSession(device_id, 0, 0, None, pointer(self.sess))
        self.check_err(err)

    def configure_data_voltage_logic_family(self, chans="", logic_family=NIHSDIO_VAL_1_8V_LOGIC):
        """Wrapper function: configure data voltage logic family"""
        err = self.driver.niHSDIO_ConfigureDataVoltageLogicFamily(self.sess, chans, logic_family)
        self.check_err(err)

    def assign_static_channels(self, chans=""):
        """Wrapper function: configure channels for static digital generation"""
        # Create session
        err = self.driver.niHSDIO_AssignStaticChannels(self.sess, chans)
        self.check_err(err)

    def write_static(self, write_data, channel_mask=0xFFFFFFFF):
        """Wrapper function: write static data to configured channels"""
        err = self.driver.niHSDIO_WriteStaticU32(self.sess, write_data, channel_mask)
        self.check_err(err)

    def check_err(self, err):
        """Wrapper function: given an error code, return error description"""
        if err != 0:
            err_desc = create_string_buffer(1024)
            self.driver.niHSDIO_GetError(None, pointer(c_int(err)), 1024, err_desc)
            raise NIHSDIOException(err_desc.value)

    def close(self):
        """Wrapper function: close NI-HSDIO session"""
        self.check_err(self.driver.niHSDIO_close(self.sess))

    def write_data_across_chans(self, chans, data, debug=False):
        """Writes a pattern across channels. If chans is a string, it is interpreted as a
        channel map key. If chans is a list, it will be directly interpreted as the channels.
        data will be interpreted as an unsigned 32-bit integer."""
        # Type checking and conversion
        if isinstance(chans, str):
            chans = self.chan_map[chans]
        if not isinstance(chans, list):
            err = f"Channels must be specified as (or mapped to) a list: got {repr(chans)}."
            raise NIHSDIOException(err)

        # Convert data to binary string for bit access
        data = format(data, '032b')[::-1]

        # Reorder bits for static generation
        write_data = 0
        mask = 0
        for chan, bit in zip(chans, data):
            mask |= (1 << chan)
            write_data |= (int(bit) << chan)

        # Debug statements
        if debug:
            print("Write data:", write_data)
            print("Mask:", mask)
            print("Original data binary:", data[::-1])
            print("Write data binary:", format(write_data, '032b'))
            print("Mask binary:", format(mask, '032b'))
            print()

        # Write data using driver
        self.write_static(write_data, mask)

    def __del__(self):
        # Try to close session on deletion
        try:
            self.close()
        except NIHSDIOException:
            pass

if __name__=="__main__":
    # Initialize and run basic static generation tests
    nihsdio = NIHSDIO("Dev7", {"wl_addr": [1,3,5,7,9,11]})
    nihsdio.write_static(0xFFFFFFFF)
    nihsdio.write_data_across_chans("wl_addr", 10, debug=True)
    nihsdio.write_data_across_chans([13,15,30,28,26,24,22], 10, debug=True)
