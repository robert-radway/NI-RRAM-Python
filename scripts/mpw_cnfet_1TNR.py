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
nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_GAX1_CNFET_1TNR_LCH160.toml", polarity="PMOS") # FOR CNFET RRAM
# nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_silicon.toml", polarity="NMOS") # FOR Si NMOS RRAM


# DEBUGGING READ
# print("OLD READ:")
# nisys.read(record=True)
print("1TNR READ:")
nisys.read_1tnr(record=True)

# for selecting specific bitlines
BLS = ["BL_0", "BL_1",] # 1T2R
# BLS = ["BL_0", "BL_1", "BL_2", "BL_3"] # 1T4R
# BLS = ["BL_0", "BL_2", "BL_3"] # 1T4R

nisys.dynamic_reset(bl_selected="BL_1", is_1tnr=True)
nisys.dynamic_form(bl_selected="BL_1", is_1tnr=True)
nisys.dynamic_reset(bl_selected="BL_1", is_1tnr=True)
nisys.dynamic_form(bl_selected="BL_1", is_1tnr=True)

print("00")
nisys.dynamic_reset(bl_selected="BL_1", is_1tnr=True)
nisys.dynamic_reset(bl_selected="BL_0", is_1tnr=True)
nisys.dynamic_reset(bl_selected="BL_1", is_1tnr=True)

#nisys.read_1tnr(record=True)
print("01")
nisys.dynamic_set(bl_selected="BL_0", is_1tnr=True)

print("00")
nisys.dynamic_reset(bl_selected="BL_0", is_1tnr=True)

print("10")
nisys.dynamic_set(bl_selected="BL_1", is_1tnr=True)

print("11")
nisys.dynamic_set(bl_selected="BL_0", is_1tnr=True)

print("01")
nisys.dynamic_reset(bl_selected="BL_1", is_1tnr=True)

print("11")
nisys.dynamic_set(bl_selected="BL_1", is_1tnr=True)

print("10")
nisys.dynamic_reset(bl_selected="BL_0", is_1tnr=True)

print("00")
nisys.dynamic_reset(bl_selected="BL_1", is_1tnr=True)
nisys.dynamic_reset(bl_selected="BL_0", is_1tnr=True)

# nisys.read_1tnr(record=True)

## 1TNR DYNAMIC SET/RESET BLOCK: TEST SET 1 AT A TIME
## This block will reset then set each cell sequentially
# for i in range(4):
#     for bl in BLS:
#         nisys.dynamic_reset(mode="RESET", bl_selected=bl, is_1tnr=True)
#         nisys.dynamic_set(mode="SET", bl_selected=bl, is_1tnr=True)

### 1TNR DYNAMIC SET/RESET BLOCK: TEST SET ALL THEN RESET ALL
### This block will reset all cells then set all cells
# for i in range(4):
#     for bl in BLS:
#         nisys.dynamic_reset(mode="RESET", bl_selected=bl, is_1tnr=True)
#     for bl in BLS:
#         nisys.dynamic_set(mode="SET", bl_selected=bl, is_1tnr=True)

nisys.close()