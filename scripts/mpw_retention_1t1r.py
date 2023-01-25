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
nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_GAX1_CNFET_1T1R_RETENTION.toml", polarity="PMOS") # FOR CNFET RRAM

nisys.read(record=True)
## input("Dynamic Form")

### CALL THIS TO FORM
nisys.dynamic_form()
#nisys.dynamic_reset()

### CALL THIS TO CHECK IF CELL WORKS
for i in range(100):
    nisys.dynamic_reset()
    nisys.dynamic_set()

# ### CALL THIS FOR HRS
# nisys.dynamic_reset()

# ### CALL THIS FOR LRS
# nisys.dynamic_set()

# ### CALL THIS FOR MULTIBIT STATE NEAR HRS
# nisys.targeted_dynamic_set(mode="SET_TARGET_WINDOW_1", max_attempts=50, debug=False)

# ### CALL THIS FOR MULTIBIT STATE NEAR LRS
# nisys.targeted_dynamic_set(mode="SET_TARGET_WINDOW_2", max_attempts=50, debug=False)


# nisys.dynamic_reset()

nisys.close()
