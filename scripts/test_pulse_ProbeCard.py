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
nisys = NIRRAM(args.chip, args.device, settings="settings/DEC3_ProbeCard.json", polarity="NMOS")

nisys.read(record=True)
# input("Dynamic Form")
nisys.dynamic_form()
for i in range(1):
    nisys.dynamic_reset()
    nisys.dynamic_set()
# nisys.close()

# for autoprobing cnfet, addd polarity = pmos
