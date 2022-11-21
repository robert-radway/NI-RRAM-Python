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
nisys.dynamic_form()
for i in range(1000000):
    nisys.dynamic_set(mode="SET")
    nisys.dynamic_reset(mode="RESET_0") # increasing soft reset levels, comment out as needed
    nisys.dynamic_reset(mode="RESET_1")
    nisys.dynamic_reset(mode="RESET_2")
    # nisys.dynamic_reset(mode="RESET_3")

    # IF YOU HAVE ENOUGH WINDOW, CAN TRY WITH MORE LEVELS!
    # nisys.dynamic_reset(mode="RESET_4")
    # nisys.dynamic_reset(mode="RESET_5")
    # nisys.dynamic_reset(mode="RESET_6")
    # nisys.dynamic_reset(mode="RESET_7")
nisys.close()

# for autoprobing cnfet, addd polarity = pmos
