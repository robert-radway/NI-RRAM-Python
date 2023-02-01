"""Script to perform a read voltage sweep on a chip"""
import argparse
import numpy as np
from digitalpattern.nirram import NIRRAM
import matplotlib.pyplot as plt


# Get arguments
parser = argparse.ArgumentParser(description="RESET a chip.")
parser.add_argument("chip", help="chip name for logging")
parser.add_argument("device", help="device name for logging")

args = parser.parse_args()

# Initialize NI system
# For CNFET: make sure polarity is PMOS
nisys = NIRRAM(args.chip, args.device, settings="settings/DEC3_ProbeCard_CNFET_4x4.toml", polarity="PMOS") # FOR CNFET RRAM

nisys.read(record=True)
# input("Dynamic Form")
# nisys.dynamic_form()
# nisys.dynamic_reset()
# nisys.read(record=True)

# nisys.dynamic_set()
# nisys.read(record=True)

# nisys.dynamic_reset()

# nisys.targeted_dynamic_set(mode="SET_TARGET_WINDOW_1", max_attempts=10, debug=False)
# nisys.targeted_dynamic_set(mode="SET_TARGET_WINDOW_2", max_attempts=10, debug=False)
# nisys.dynamic_reset()
# nisys.dynamic_set()

# for i in range(10):
#     nisys.dynamic_reset()
#     nisys.dynamic_set()

# for i in range(10000):
#     # nisys.targeted_dynamic_set(mode="SET_TARGET_WINDOW_1", max_attempts=1, debug=False)
#     # nisys.targeted_dynamic_set(mode="SET_TARGET_WINDOW_2", max_attempts=1, debug=False)
#     nisys.dynamic_reset()
#     nisys.dynamic_set()


### CODE FOR SEQUENTIAL FORM/RESET OF ALL WL/(BL,SL) COMBINATIONS
# for wl_idx in [0, 1, 2, 3]:
#     nisys.wls = [f"A4_WL_{wl_idx}"]
#     for blsl_idx in [0, 1, 2, 3]:
#         nisys.bls = [f"A4_BL_{blsl_idx}"]
#         nisys.sls = [f"A4_SL_{blsl_idx}"]
#         nisys.dynamic_form()
#         nisys.dynamic_reset()

# # nisys.dynamic_reset()

### RE-READ ALL WLS/BLS TO MAKE SURE OPERATION DID NOT DISTURB OTHER CELLS
nisys.wls = nisys.all_wls
nisys.bls = nisys.all_bls
nisys.sls = nisys.all_sls
nisys.read(record=True)

# nisys.close()
# exit()

### CHECKERBOARD ATTEMPT
# NOTE: usually entire BL/SL is dead because one shorted cell causes entire
# BL/SL to now have the parallel shorted FET. Fo for testing we can try
# single BL/SL columns that did not short cells
cells = { # (WL, BL/SL) => "bit"
    # (0, 0): 0,
    # (1, 0): 1,
    # (2, 0): 2,
    # (3, 0): 3,

    (0, 1): 1,
    (1, 1): 2,
    (2, 1): 3,
    (3, 1): 0,

    # (0, 2): 2,
    # (1, 2): 3,
    # (2, 2): 0,
    # (3, 2): 1,

    # (0, 3): 3,
    # (1, 3): 0,
    # (2, 3): 1,
    # (3, 3): 2,
}

# first we want to reset all cells to avoid short paths
for (wl_idx, blsl_idx), bit in cells.items():
    nisys.wls = [f"A4_WL_{wl_idx}"]
    nisys.bls = [f"A4_BL_{blsl_idx}"]
    nisys.sls = [f"A4_SL_{blsl_idx}"]
    nisys.dynamic_reset()

# now set to multibit values
for (wl_idx, blsl_idx), bit in cells.items():
    nisys.wls = [f"A4_WL_{wl_idx}"]
    nisys.bls = [f"A4_BL_{blsl_idx}"]
    nisys.sls = [f"A4_SL_{blsl_idx}"]
    if bit == 0:
        nisys.dynamic_reset()
    elif bit == 1:
        nisys.targeted_dynamic_set(mode="SET_TARGET_WINDOW_2", max_attempts=1, debug=True)
    elif bit == 2:
        nisys.targeted_dynamic_set(mode="SET_TARGET_WINDOW_1", max_attempts=1, debug=True)
    elif bit == 3:
        nisys.dynamic_set()
    else:
        raise ValueError(f"Invalid bit {bit}, must be 0, 1, 2, 3")

    ### RE-READ ALL WLS/BLS TO MAKE SURE OPERATION DID NOT DISTURB OTHER CELLS
    nisys.wls = nisys.all_wls
    nisys.bls = nisys.all_bls
    nisys.sls = nisys.all_sls
    nisys.read(record=True)

nisys.close()
