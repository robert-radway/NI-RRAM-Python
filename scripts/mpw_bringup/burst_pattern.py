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
nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_ProbeCard.toml", polarity="PMOS") # FOR CNFET RRAM

digipat_file = "PULSE_MPW_ProbeCard"
nisys.digital.burst_pattern(digipat_file)
nisys.read(record=True)
#different pattern