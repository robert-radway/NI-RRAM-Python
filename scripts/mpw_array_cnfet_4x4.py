"""Script to perform a read voltage sweep on a chip"""
import argparse
import numpy as np
from digitalpattern.nirram import NIRRAM
import matplotlib.pyplot as plt
import time

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

for wl_idx in [0, 1, 2, 3]:
    nisys.wls = [f"A4_WL_{wl_idx}"]
    for blsl_idx in [0, 1, 2, 3]:
        nisys.bls = [f"A4_BL_{blsl_idx}"]
        nisys.sls = [f"A4_SL_{blsl_idx}"]
        nisys.dynamic_form()
        nisys.dynamic_reset()

nisys.wls = nisys.all_wls
nisys.bls = nisys.all_bls
nisys.sls = nisys.all_sls
nisys.read(record=True)



### CHECKERBOARD
# NOTE: usually entire BL/SL is dead because one shorted cell causes entire
# BL/SL to now have the parallel shorted FET. Fo for testing we can try
# single BL/SL columns that did not short cells
    # 2x2 Example:
    #   1 0     set  reset
    #   0 1    reset  set
def create_checkerboard(width, height):
    cells = {}
    for x in range(width): #WL
        for y in range(height): #BL
            value = (x + y) % 2 # If (WL + BL)%2 = 1  (WL,BL) <- 1
            cells[(x, y)] = value # Set (WL, BL) if their sum is odd
            
            #print(f"set: ({x},{y}) <- {value}") #Debug correct cells being set
    return cells

cells = create_checkerboard(4,4)

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

### final read
time.sleep(1.0)
print("FINAL READ")
nisys.wls = nisys.all_wls
nisys.bls = nisys.all_bls
nisys.sls = nisys.all_sls
nisys.read(record=True)

nisys.close()
