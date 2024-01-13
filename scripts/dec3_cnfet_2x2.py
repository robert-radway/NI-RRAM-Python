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
nisys = NIRRAM(args.chip, args.device, settings="settings/DEC3_ProbeCard_CNFET_2x2.toml", polarity="PMOS") # FOR CNFET RRAM

nisys.read(record=True)

# nisys.close()
# exit()

# input("Dynamic Form")

for wl_idx in [0, 1]:
    nisys.wls = [f"A2_WL_{wl_idx}"]
    for blsl_idx in [0, 1]:
        nisys.bls = [f"A2_BL_{blsl_idx}"]
        nisys.sls = [f"A2_SL_{blsl_idx}"]
        nisys.dynamic_form()
        nisys.dynamic_reset()

# nisys.dynamic_set()
nisys.wls = nisys.all_wls
nisys.bls = nisys.all_bls
nisys.sls = nisys.all_sls
nisys.read(record=True)

# exit()
# input("Checkerboard")

### CHECKERBOARD
# NOTE: usually entire BL/SL is dead because one shorted cell causes entire
# BL/SL to now have the parallel shorted FET. Fo for testing we can try
# single BL/SL columns that did not short cells
cells = { # (WL, BL/SL) => "bit"
    (0, 0): 0,
    (1, 0): 1,

    (0, 1): 1,
    (1, 1): 0,
}

# first we want to reset all cells to avoid short paths
for (wl_idx, blsl_idx), bit in cells.items():
    nisys.wls = [f"A2_WL_{wl_idx}"]
    nisys.bls = [f"A2_BL_{blsl_idx}"]
    nisys.sls = [f"A2_SL_{blsl_idx}"]
    nisys.dynamic_reset()

# now set to multibit values
for (wl_idx, blsl_idx), bit in cells.items():
    nisys.wls = [f"A2_WL_{wl_idx}"]
    nisys.bls = [f"A2_BL_{blsl_idx}"]
    nisys.sls = [f"A2_SL_{blsl_idx}"]
    
    print(f"wl={wl_idx}, blsl={blsl_idx}, bit={bit}")

    if bit == 0:
        pass # already reset
    elif bit == 1:
        nisys.dynamic_set()
    else:
        raise ValueError(f"Invalid bit {bit}, must be 0, 1")

    ### RE-READ ALL WLS/BLS TO MAKE SURE OPERATION DID NOT DISTURB OTHER CELLS
    nisys.wls = nisys.all_wls
    nisys.bls = nisys.all_bls
    nisys.sls = nisys.all_sls
    nisys.read(record=True)

# for i in range(10):
#     nisys.dynamic_reset()
#     nisys.dynamic_set()
# #     pass

nisys.close()
