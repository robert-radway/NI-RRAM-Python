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
nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_1TNR.json", polarity="PMOS") # FOR CNFET RRAM
# nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_silicon.json", polarity="NMOS") # FOR Si NMOS RRAM


# DEBUGGING READ
print("OLD READ:")
nisys.read(record=True)
print("1TNR READ:")
nisys.read_1tnr(record=True)


# nisys.read_1tnr(record=True)
# input("Dynamic Form")
# nisys.dynamic_form(is_1tnr=True)
# # nisys.dynamic_set(mode="SET")
# nisys.dynamic_reset(mode="RESET", is_1tnr=True)
# for i in range(4):
#     nisys.dynamic_set(mode="SET", is_1tnr=True)
#     nisys.dynamic_reset(mode="RESET", is_1tnr=True)

nisys.close()
