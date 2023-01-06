"""Script to perform a read voltage sweep on a chip"""
import argparse
import numpy as np
from digitalpattern.nirram import NIRRAM, RRAMArrayMask
import matplotlib.pyplot as plt


# Get arguments
parser = argparse.ArgumentParser(description="RESET a chip.")
parser.add_argument("chip", help="chip name for logging")
parser.add_argument("device", help="device name for logging")

args = parser.parse_args()

# Initialize NI system
nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_ProbeCard.json", polarity="PMOS") # FOR CNFET RRAM
# nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_silicon.json", polarity="NMOS") # FOR Si NMOS RRAM

nisys.read(record=True)
# input("Dynamic Form")
mask = RRAMArrayMask(nisys.wls, nisys.bls, nisys.sls, nisys.all_wls, nisys.all_bls, nisys.all_sls, nisys.polarity)
for i in range(10):
    nisys.form_pulse(mask, vbl =-2, vwl = -2, vsl=0.5, vwl_unsel=0.5, pulse_len=10000)
    nisys.read(record=True)
nisys.close()

# for autoprobing cnfet, addd polarity = pmos
