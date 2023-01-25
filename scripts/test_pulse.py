"""Script to perform a read voltage sweep on a chip"""
import argparse
import numpy as np
from digitalpattern.nirram import NIRRAM
from digitalpattern.mask import RRAMArrayMask
import matplotlib.pyplot as plt


# Get arguments
parser = argparse.ArgumentParser(description="RESET a chip.")
parser.add_argument("chip", help="chip name for logging")
parser.add_argument("device", help="device name for logging")

args = parser.parse_args()

# Initialize NI system (use this for both Si and CNFET)
nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_GAX1_CNFET_1T1R.toml", polarity="PMOS")

mask = RRAMArrayMask(nisys.wls, nisys.bls, nisys.sls, nisys.all_wls, nisys.all_bls, nisys.all_sls, nisys.polarity)

# nisys.set_pulse(
#     mask,
#     bl_selected=None, # specific selected BL for 1TNR
#     vbl=-1.5,
#     vsl=0,
#     vwl=-1.5,
#     pulse_len=1,
# )


nisys.reset_pulse(
    mask,
    bl_selected=None, # specific selected BL for 1TNR
    vbl=0.5,
    vsl=-1.5,
    vwl=-1.5,
    pulse_len=1,
)

nisys.reset_all_pins_to_zero()

# nisys.read(record=True)
# input("Dynamic Form")
# nisys.dynamic_form()
# nisys.dynamic_reset()
# for i in range(20):
#     nisys.dynamic_reset()
#     nisys.dynamic_set()
#     pass
nisys.close()

# for autoprobing cnfet, addd polarity = pmos
