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
nisys = NIRRAM(args.chip, args.device, settings="settings/DEC3_ProbeCard_2x2.json", polarity="PMOS")
nisys.ppmu_set_vbody("A2_PMOS_BODY",1.5)
nisys.ppmu_set_vbody("A2_NMOS_BODY",0)
nisys.read(record=True)
# input("Dynamic Form")
nisys.dynamic_form()
nisys.dynamic_reset()
# for i in range(1):
#     nisys.dynamic_reset()
#     nisys.dynamic_set()
#     pass
nisys.ppmu_set_vbody("A2_PMOS_BODY",0)
nisys.close()

# for autoprobing cnfet, addd polarity = pmos
