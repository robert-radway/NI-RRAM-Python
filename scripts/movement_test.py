import os
import logging
import time
from autoprobe import CascadeAutoProbe

def run(
    die_x: int,          # initial die x coordinate
    die_y: int,          # initial die y coordinate
    current_module: str, # initial module location, needed to locate initial location in die
    gpib_address="GPIB0::22::INSTR",
    data_folder="test/dec3",
):
    probe = CascadeAutoProbe(
        gpib_address=gpib_address,
        data_folder=data_folder,
        die_x=die_x,
        die_y=die_y,
        current_module=current_module,
    )
    
    for module_column in [
        "si_nmos_1t1r_1",
        "si_nmos_1t1r_2",
    ]:
        for row in range(1, 2):
            module = f"{module_column}_row_{row}"
            probe.move_to_module(module)
            
            with probe.start_measurement() as measurement:
                path_save_data = os.path.join(measurement.data_folder, measurement.timestamp)
                logging.info("Starting measurement")
                time.sleep(3) # simulate measurement
                logging.info(f"Save data to: {path_save_data}")

    # return to starting module when done?
    probe.move_to_module(current_module)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Convert idvg gax sweep list into .h5 format")

    # require user input die x and y coordinates for safety, to ensure
    # user confirms correct die location before running

    parser.add_argument(
        "-x",
        dest="die_x",
        type=int,
        help="Die X coordinate",
    )
    parser.add_argument(
        "-y",
        dest="die_y",
        type=int,
        help="Die Y coordinate",
    )
    parser.add_argument(
        "current_module",
        type=str,
        help="Current module location",
    )
    parser.add_argument(
        "--gpib",
        type=str,
        dest="gpib_address",
        default="GPIB0::22::INSTR",
        help="GPIB address of cascade instrument",
    )

    args = parser.parse_args()
    if args.die_x is None or args.die_y is None:
        parser.error("Must specify die x and y coordinates")

    run(
        die_x=args.die_x,
        die_y=args.die_y,
        current_module=args.current_module,
        gpib_address=args.gpib_address,
    )