"""Script to perform a read voltage sweep on a chip"""
import argparse
import numpy as np
from digitalpattern import NIRRAM
import matplotlib.pyplot as plt


# Get arguments
parser = argparse.ArgumentParser(description="RESET a chip.")
parser.add_argument("chip", help="chip name for logging")
parser.add_argument("device", help="device name for logging")

args = parser.parse_args()

# Initialize NI system
# For CNFET: make sure polarity is PMOS
nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_1TNR.toml", polarity="PMOS") # FOR CNFET RRAM
# nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_silicon.toml", polarity="NMOS") # FOR Si NMOS RRAM


# DEBUGGING READ
print("OLD READ:")
nisys.read(record=True)
print("1TNR READ:")
nisys.read_1tnr(record=True)

# for selecting specific bitlines
BLS = ["BL_0", "BL_1",] # 1T2R
# BLS = ["BL_0", "BL_1", "BL_2", "BL_3"] # 1T4R


### 1TNR DYNAMIC FORM BLOCK
### for each selected, form then reset
### internal script will set non-selected bitlines to V/4
for bl in BLS:
    nisys.dynamic_form(bl=bl, is_1tnr=True)
    nisys.dynamic_reset(bl=bl, is_1tnr=True)

nisys.read_1tnr(record=True)


### 1TNR DYNAMIC SET/RESET BLOCK: TEST SET 1 AT A TIME
### This block will reset then set each cell sequentially
# for i in range(4):
#     for bl in BLS:
#         nisys.dynamic_reset(mode="RESET", bl=bl, is_1tnr=True)
#         nisys.dynamic_set(mode="SET", bl=bl, is_1tnr=True)

### 1TNR DYNAMIC SET/RESET BLOCK: TEST SET ALL THEN RESET ALL
### This block will reset all cells then set all cells
# for i in range(4):
#     for bl in BLS:
#         nisys.dynamic_reset(mode="RESET", bl=bl, is_1tnr=True)
#     for bl in BLS:
#         nisys.dynamic_set(mode="SET", bl=bl, is_1tnr=True)

nisys.close()
