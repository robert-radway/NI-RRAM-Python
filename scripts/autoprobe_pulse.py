"""Script to perform a read voltage sweep on a chip"""
import argparse
import logging
import numpy as np
from digitalpattern.nirram import NIRRAM
from autoprobe import CascadeAutoProbe
import matplotlib.pyplot as plt

def run(
    die_x: int,          # initial die x coordinate
    die_y: int,          # initial die y coordinate
    current_module: str, # initial module location, needed to locate initial location in die
    iterations=2,        # number of sweeps
    gpib_address="GPIB0::16::INSTR",
    data_folder="test/dec3",
):
    chip = f"x_{die_x}_y_{die_y}"

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
        "si_nmos_1t1r_3",
        "si_nmos_1t1r_4",
        "si_nmos_1t1r_5",
        "si_nmos_1t1r_6",
        "si_nmos_1t1r_7",
        "si_nmos_1t1r_8",
        "si_nmos_1t1r_9",
    ]:
        for row in range(1, 12):
            module = f"{module_column}_row_{row}"
            probe.move_to_module(module)
            
            with probe.start_measurement() as measurement:
                logging.info("Starting measurement")

                # Initialize NI system
                nisys = NIRRAM(chip, module, settings="settings/DEC3.json")

                print(nisys.read(record=True))
                #input("Dynamic Form")
                print(nisys.dynamic_form())
                for i in range(iterations):
                    print(nisys.dynamic_reset())
                    print(nisys.dynamic_set())
                nisys.close()

                logging.info(f"Save data to: {nisys.datafile_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Sweep rram form/reset/set for an array")

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
    parser.add_argument(
        "--n",
        type=int,
        dest="iterations",
        default=2,
        help="Number of reset/set iterations",
    )

    args = parser.parse_args()
    if args.die_x is None or args.die_y is None:
        parser.error("Must specify die x and y coordinates")

    run(**vars(args))