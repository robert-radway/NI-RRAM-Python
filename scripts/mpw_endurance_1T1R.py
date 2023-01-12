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

# generate logarithmic spaced sweep counts
# define sweep read schedule, each tuple format is:
# (cycle number, step size after that cycle)
sweep_schedule = [
    (   0, 10),
    ( 100, 100),
    (1000, 3000),
]
max_cycles = 1e7
next_read_cycles = NIRRAM.get_read_cycles(max_cycles, sweep_schedule)
print(next_read_cycles)

# Initialize NI system
# For CNFET: make sure polarity is PMOS
nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_1T1R.toml", polarity="PMOS") # FOR CNFET RRAM PMOS & Si RRAM NMOS

# DO FORM PART MANUALLY, COMMENT OUT AS NEEDED
nisys.read(record=True)
# input("Dynamic Form")
# nisys.dynamic_form()
# nisys.dynamic_reset()

# main endurance sweep
nisys.endurance_dynamic_set_reset(
    max_cycles=max_cycles,
    sweep_schedule=sweep_schedule,
    max_failures = 100, # failures in row before stopping
    record = True,
    print_data = True,
)

nisys.close()
