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
nisys = NIRRAM(args.chip, args.device, settings="settings/MPW.json", polarity="PMOS") # FOR CNFET RRAM
# nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_silicon.json", polarity="NMOS") # FOR Si NMOS RRAM

nisys.read(record=True)
# input("Dynamic Form")
# nisys.dynamic_form()
for i in range(10000):
    nisys.sweep_gradual_reset_in_range(mode="RESET_SWEEP", res_low=24000, res_high=200000)
    nisys.sweep_gradual_set_in_range(mode="SET_SWEEP", res_low=24000, res_high=200000)

nisys.close()

# for autoprobing cnfet, addd polarity = pmos
