"""Script to perform a read voltage sweep on a chip"""
import argparse
import logging
import numpy as np
from digitalpattern import NIRRAM
from autoprobe import CascadeAutoProbe
import matplotlib.pyplot as plt
import time

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

    for module_column in [ # should be ~ 50 uA/um
        # "cnt_left_bottom_1t1r_1", # W = 5 um
        # "cnt_left_bottom_1t1r_2", # W = 10 um
        # "cnt_left_bottom_1t1r_3", # W = 20 um
        # "cnt_left_bottom_1t1r_4", # W = 52 um 
        # "cnt_left_bottom_1t1r_5", # W = 105 um, 5-8 are identical
        # "cnt_left_bottom_1t1r_6", # W = 105 um
        # "cnt_left_bottom_1t1r_7", # W = 105 um
        # "cnt_left_bottom_1t1r_8", # W = 105 um
        "cnt_left_top_1t1r_2", # W = 10 um
        "cnt_left_top_1t1r_3", # W = 20 um
        "cnt_left_top_1t1r_4", # W = 52 um 
        "cnt_left_top_1t1r_5", # W = 105 um, 5-8 are identical
        "cnt_left_top_1t1r_6", # W = 105 um
        "cnt_left_top_1t1r_7", # W = 105 um
        "cnt_left_top_1t1r_8", # W = 105 um
        "cnt_left_top_1t1r_1", # W = 5 um
    ]:
        for row in range(1, 16):
            module = f"{module_column}_row_{row}"
            probe.move_to_module(module)
            
            with probe.start_measurement() as measurement:
                logging.info("Starting measurement")

                #Initialize NI system
                nisys = NIRRAM(chip, module, settings="settings/DEC3.json", polarity="PMOS")
                
                nisys.read(record=True)
                # input("Dynamic Form")
                nisys.dynamic_form()
                for i in range(iterations):
                    nisys.dynamic_reset()
                    nisys.dynamic_set()
                nisys.close()

                logging.info(f"Save data to: {nisys.datafile_path}")

    # probe.move_to_module("cnt_left_bottom_1t1r_2_row_14")

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