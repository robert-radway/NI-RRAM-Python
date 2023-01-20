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

# nisys.targeted_dynamic_set(mode="SET_TARGET_WINDOW_1", max_attempts=10, debug=False)
# nisys.targeted_dynamic_set(mode="SET_TARGET_WINDOW_2", max_attempts=10, debug=False)
# nisys.dynamic_reset()
# nisys.dynamic_set()

# for i in range(10):
#     nisys.dynamic_reset()
#     nisys.dynamic_set()

for i in range(4):
    # nisys.targeted_dynamic_set(mode="SET_TARGET_WINDOW_1", max_attempts=50, debug=False)
    # nisys.targeted_dynamic_set(mode="SET_TARGET_WINDOW_2", max_attempts=50, debug=False)
    nisys.dynamic_reset()
    nisys.dynamic_set()

nisys.close()
