"""Script to perform a read voltage sweep on a chip"""
import argparse
import numpy as np
from digitalpattern.nirram import NIRRAM, RRAMArrayMask
import matplotlib.pyplot as plt
import pdb

# Get arguments
parser = argparse.ArgumentParser(description="RESET a chip.")
parser.add_argument("chip", help="chip name for logging")
parser.add_argument("device", help="device name for logging")

args = parser.parse_args()

# Initialize NI system
nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_ProbeCard.toml", polarity="PMOS") # FOR CNFET RRAM
#nisys.read(record=True)

mask = RRAMArrayMask(nisys.wls, nisys.bls, nisys.sls, nisys.all_wls, nisys.all_bls, nisys.all_sls, nisys.polarity)
#nisys.reset_pulse(mask,vbl=2.5,vsl=2,vwl=0.5,pulse_len=10)
nisys.dynamic_reset()
nisys.ppmu_all_pins_to_zero()

"""
for i in range(10):
    nisys.set_pulse(mask, vbl =-2, vwl = -2, vsl=0.5, vwl_unsel=0.5, pulse_len=10000)
    nisys.read(record=True)
"""
nisys.close()

# for autoprobing cnfet, addd polarity = pmos
