import os
import json
import logging
import signal
from dataclasses import dataclass
import pyvisa
from autoprobe.util.timestamp import timestamp

@dataclass
class DeviceModule:
    """Data class containing a device module's location relative to die
    home position."""
    name: str
    x: int
    y: int


class Measurement:
    """Wrapper for running a measurement sweep. Contains metadata for timestamp
    and where to store measurement data, and handles CTRL + C to stop measurement
    and cleanup resources.
    
    Created by CascadeController, usage as follows:
    ```
    probe = CascadeController(...)

    with probe.start_measurement() as measurement:
        # store data into "measurement_data_folder/timestamp/..."
        data_folder = os.path.join(measurement.data_folder, measurement.timestamp)
        # do measurement stuff here
        run_measurement(data_folder) 
    ```
    """
    def __init__(
        self,
        data_folder,  # data folder to store measurements
        abort_handler, # function to call if measurement is stopped with CTRL + C
    ):
        self.data_folder = data_folder
        self.timestamp = timestamp() # timestamp string
        
        # replace CTRL + C handler with input handler to stop measurement
        self.abort_handler = abort_handler
        self._original_sigint_handler = signal.getsignal(signal.SIGINT)
        self._abort_after_measurement = False

        # callback for CTRL + C: abort program after current measurement finishes
        def abort_measurement(_sig, _frame):
            logging.info("Aborting program after measurement finishes")
            self._abort_after_measurement = True
        
        # TODO: way to force abort?
        # def force_abort_measurement(_sig, _frame):
        #     logging.info("FORCE ABORT!")
        #     if self._abort_after_measurement: # already clicked CTRL + C
        #         logging.info("Force aborting program immediately")
        #         self.abort_handler()
        #         exit(0)
        
        signal.signal(signal.SIGINT, abort_measurement)

    def __enter__(self):
        return self
    
    def __exit__(self, _type, _value, _traceback):
        # reset signal handlers
        signal.signal(signal.SIGINT, self._original_sigint_handler)
        # if abort after measurement, exit
        if self._abort_after_measurement:
            self.abort_handler()
            logging.info("Aborting program")
            exit(0)
            
    
class CascadeAutoProbe:
    """Cascade auto probe gpib controller interface."""

    def __init__(
        self,
        gpib_address,                     # gpib address of cascade controller
        data_folder,                      # folder containing all data and wafer/die module info
        die_x,                            # initial die x coordinate
        die_y,                            # initial die y coordinate
        current_module,                   # initial module location, needed to locate initial location in die
        log=True,                         # enable logging
        log_to_console=True,              # print log to console
        path_wafer_metadata="wafer.json", # path to wafer metadata file
        path_die_modules="modules.json",  # path to die modules information file
        invert_direction=True,            # some autoprobes use different die x,y coordinate systems
    ):
        self.gpib_address = gpib_address
        self.data_folder = data_folder
        self.die_x = die_x
        self.die_y = die_y
        self.invert_direction = invert_direction
        self.current_module = current_module # current module name, updated when moving to module

        if log:
            CascadeAutoProbe.init_logging(log_to_console)
        
        if not os.path.exists(self.data_folder):
            raise Exception(f"Data path {self.data_folder} does not exists")
        
        logging.info(f"Saving data at: {self.data_folder}")
        
        # load wafer metadata from
        self.wafer_size, self.die_size_x, self.die_size_y = CascadeAutoProbe.load_wafer_metadata(data_folder, path_wafer_metadata)
        logging.info(f"Wafer size = {self.wafer_size} mm")
        logging.info(f"Die size (x, y) = ({self.die_size_x}, {self.die_size_y})")
        logging.info(f"Initial die wafer map coords: x={die_x}, y={die_y}")
        
        # load die modules: returns a dict of module name: str => location
        # relative to home position (0, 0) which is the current location in
        # the cascade probe station when autoprobe begins running
        self.modules = CascadeAutoProbe.load_die_modules(data_folder, path_die_modules)
        logging.info(f"Loaded {len(self.modules)} die modules")

        # connect to cascde with gpib
        try:
            rm = pyvisa.ResourceManager()
            self.instrument_cascade = rm.open_resource(gpib_address)
            logging.info(self.instrument_cascade.query("*IDN?"))
        except:
            logging.error(f"Failed to connect to cascade autoprobe at {gpib_address}")
            logging.error(f"Running in dummy mode without GPIB")
            self.instrument_cascade = None
        
        # intialize chuck home by translating from current module location
        initial_module_location = self.modules[current_module]
        if self.instrument_cascade is not None:
            x0, y0, z0 = self.read_chuck_position() # intial position
            logging.info(f"Initial chuck position: x0={x0}, y0={y0}, z0={z0}")
            if self.invert_direction:
                self.set_chuck_home_at(x0 + initial_module_location.x, y0 + initial_module_location.y)
            else:
                self.set_chuck_home_at(x0 - initial_module_location.x, y0 - initial_module_location.y)
        logging.info(f"Initial module {current_module} location: x={initial_module_location.x}, y={initial_module_location.y}")
        logging.info(f"Die home set relative to current module location")


    @staticmethod
    def init_logging(
        log_to_console=True,
    ):
        """Helper to initialize logging output to file and console."""
        import logging

        # setup logging
        logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
        rootLogger = logging.getLogger()
        rootLogger.setLevel(logging.DEBUG)

        os.makedirs("logs", exist_ok=True)
        logFileHandler = logging.FileHandler(f"logs/{timestamp()}.log", mode="a", encoding=None, delay=False)
        logFileHandler.setLevel(logging.DEBUG)
        logFileHandler.setFormatter(logFormatter)
        rootLogger.addHandler(logFileHandler)

        if log_to_console:
            logConsoleHandler = logging.StreamHandler()
            logConsoleHandler.setLevel(logging.DEBUG)
            logConsoleHandler.setFormatter(logFormatter)
            rootLogger.addHandler(logConsoleHandler)
    
    @staticmethod
    def load_wafer_metadata(data_folder: str, path_wafer_metadata: str):
        """Load wafer metadata from `wafer.json` file in data_folder.
        This includes wafer size and die size.
        """
        p = os.path.join(data_folder, path_wafer_metadata)
        if not os.path.exists(p):
            raise Exception(f"Wafer metadata Data path {p} does not exist")
        with open(p, "r") as f:
            wafer_metadata = json.load(f)
            return wafer_metadata["wafer_size"], wafer_metadata["die_size_x"], wafer_metadata["die_size_y"]
    
    @staticmethod
    def load_die_modules(data_folder: str, path_die_modules: str):
        p = os.path.join(data_folder, path_die_modules)
        if not os.path.exists(p):
            raise Exception(f"Die modules file {p} does not exist")
        with open(p, "r") as f:
            raw_modules = json.load(f)
            modules = {}
            for mod_name, mod in raw_modules.items():
                modules[mod_name] = DeviceModule(mod_name, mod["x"], mod["y"])
            return modules
    
    def cleanup(self):
        """Cleanup resources."""
        logging.info("Cleaning up CascadeController resources")
        if self.instrument_cascade is not None:
            self.instrument_cascade.close() # disconnects from cascade gpib
    
    def start_measurement(self):
        """Return a measurement wrapper"""
        return Measurement(
            data_folder=self.current_module_data_folder(),
            abort_handler=self.cleanup, # if CTRL + C pressed, cleanup resources
        )

    def get_path_die(self, die_x: int, die_y: int):
        """Return path to store data for die at (x,y) in wafer map."""
        return os.path.join(self.data_folder, f"die_{die_x}_{die_y}")
    
    def get_path_module(self, module_name: str):
        """Return path to store data for module name at current
        die location (die_x, die_y)."""
        return os.path.join(self.data_folder, f"die_{self.die_x}_{self.die_y}", module_name)

    def current_module_data_folder(self):
        """Return path to store data for current module at current
        die location (die_x, die_y)."""
        return self.get_path_module(self.current_module)
    
    def read_chuck_position(self):
        """Return actual chuck stage position in X, Y, and Z coords.
        Default Compensation Mode is currently activated compensation mode
        of the kernel.
        Parameter Input:
        Unit (optional)
            Y - micron (default)
            I - mils
            X - index
        PosRef (optional):
            H - home
            Z - zero
            C - center
        Comp level (optional):
            D - default
            T - technology
            O - offset
            P - prober
            N - none
        """
        self.instrument_cascade.write(f"ReadChuckPosition Y Z")
        s = self.instrument_cascade.read() # read required to flush response
        self.instrument_cascade.query("*OPC?")
        chunks = s.split(" ") # format is like "0: 102500.321 102499.863 0.0"
        x = float(chunks[1])
        y = float(chunks[2])
        z = float(chunks[3])
        return x, y, z

    def set_chuck_home(self):
        """Set cascade autoprobe chuck home to current location.
        This is used in measurements to probe arrays relative to
        starting location.
            SetChuckHome Mode Unit
        Mode:
            0 - use current position
            V - use given value
        Unit
            Y - micron (default)
            I - mils
        """
        self.instrument_cascade.write(f"SetChuckHome 0 Y")
        self.instrument_cascade.read() # read required to flush response
        self.instrument_cascade.query("*OPC?")
    
    def set_chuck_home_at(self, x: float, y: float):
        """Set cascade autoprobe chuck home to current location.
        This is used in measurements to probe arrays relative to
        starting location.
            SetChuckHome Mode Unit
        Mode:
            0 - use current position
            V - use given value
        Unit
            Y - micron (default)
            I - mils
        """
        self.instrument_cascade.write(f"SetChuckHome V Y {x} {y}")
        self.instrument_cascade.read() # read required to flush response
        self.instrument_cascade.query("*OPC?")
    
    def move_chuck_relative(self, dx, dy):
        """Moves cascade autoprobe chuck relative to current location
        by (dx, dy). Command format is
            MoveChuck X Y PosRef Unit Velocity Compensation
        X: dx
        Y: dy
        PosRef:
            - H - home (default)
            - Z - zero
            - C - center
            - R - current position
        Unit:
            - Y - Micron (default)
            - I - Mils
            - X - Index
            - J - jog
        Velocity: velocity in percent (100% default)
        Compensation:
            - D - default (kernel setup default compensation)
            - T - technology, use prober, offset, and tech compensation
            - O - offset, use prober and offset
            - P - prober, use only prober
            - N - none, no compensation
        """
        if self.invert_direction:
            dx_ = -dx
            dy_ = -dy
        else:
            dx_ = dx
            dy_ = dy
        
        self.instrument_cascade.write(f"MoveChuck {dx_} {dy_} R Y 100")
        self.instrument_cascade.read() # read required to flush response
        self.instrument_cascade.query("*OPC?")
    
    def move_chuck_relative_to_home(self, x, y):
        """Moves wafer chuck relative to home position. See `move_chuck_relative`
        for MoveChuck command documentation.
        """
        if self.invert_direction:
            x_ = -x
            y_ = -y
        else:
            x_ = x
            y_ = y
        
        self.instrument_cascade.write(f"MoveChuck {x_} {y_} H Y 100")
        self.instrument_cascade.read() # read required to flush response
        self.instrument_cascade.query("*OPC?")
    
    def move_chuck_home(self):
        """Move chuck to previously set home position. See `move_chuck_relative`
        for MoveChuck command documentation.
        """
        self.instrument_cascade.write(f"MoveChuck 0 0 H Y 100")
        self.instrument_cascade.read() # read required to flush response
        self.instrument_cascade.query("*OPC?")
    
    def move_contacts_up(self):
        """Move contacts up (internally moves chuck down). Command is
            `MoveChuckAlign Velocity` (velocity = 100% default)
        """
        self.instrument_cascade.write(f"MoveChuckAlign 50")
        self.instrument_cascade.read() # read required to flush response
        self.instrument_cascade.query("*OPC?")
    
    def move_contacts_down(self):
        """Moves contacts down to touch device (internally moves chuck up).
            `MoveChuckContact Velocity` (velocity = 100% default)
        """
        self.instrument_cascade.write(f"MoveChuckContact 50")
        self.instrument_cascade.read() # read required to flush response
        self.instrument_cascade.query("*OPC?")
    
    def move_to_module(self, module_name: str):
        """Move to device module's location inside a die.
        """
        if module_name in self.modules:
            if self.current_module != module_name:
                self.current_module = module_name
                module = self.modules[module_name]
                logging.info(f"Move to {module_name} (x={module.x}, y={module.y})")
                if self.instrument_cascade is not None:
                    self.move_chuck_relative_to_home(module.x, module.y)
        else:
            logging.error(f"Module {module_name} does not exist")
    
    def move_to_die(self, new_die_x: int, new_die_y: int):
        """Move to specific die (x, y) in the wafer map."""
        die_dx = new_die_x - self.die_x
        die_dy = new_die_y - self.die_y
        if self.instrument_cascade is not None:
            if self.invert_direction:
                self.move_chuck_relative(- self.die_size_x * die_dx, - self.die_size_y * die_dy)
            else:
                self.move_chuck_relative(self.die_size_x * die_dx, self.die_size_y * die_dy)
        self.die_x = new_die_x
        self.die_y = new_die_y

    def move_die_relative(self, die_dx: int, die_dy: int):
        """Move to a die relative to current die (x, y) in the wafer map."""
        if self.instrument_cascade is not None:
            if self.invert_direction:
                self.move_chuck_relative(- self.die_size_x * die_dx, - self.die_size_y * die_dy)
            else:
                self.move_chuck_relative(self.die_size_x * die_dx, self.die_size_y * die_dy)
        self.die_x = self.die_x + die_dx
        self.die_y = self.die_y + die_dy