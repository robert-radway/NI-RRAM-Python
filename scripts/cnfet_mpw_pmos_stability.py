"""
11/2023
DEPRECATED (ancient old script)
- Andrew

Script for CNFET PMOS cycling on SkyWater MPW wafer.
This contains settings for pulsed cycling cnfet with voltage
levels that mimic the biases during 1T1R operation.
Used for "endurance" measurement of CNFET, e.g. see the accumulated
NBTI/PBTI effects during pulsed operation.
"""
import argparse
import numpy as np
from digitalpattern.nirram import NIRRAM
import matplotlib.pyplot as plt


# Get arguments
parser = argparse.ArgumentParser(description="RESET a chip.")
parser.add_argument("chip", help="chip name for logging")
parser.add_argument("device", help="device name for logging")
parser.add_argument("cycles", type=int, help="number of pulse cycles")
parser.add_argument("--repeat", type=int, nargs="?", default=1, help="number of times to repeat pulse cycles (to split up total cycle count)")
parser.add_argument("--read", type=int, nargs="?", default=7, help="number of times to read cnfet iv output after cycling")

args = parser.parse_args()

# unpack args for convenience
repeat = args.repeat
cycles = args.cycles
nread = args.read
print(f"repeat={repeat}, cycles={cycles}, nread={nread}")

# Initialize NI system
# For CNFET: make sure polarity is PMOS
nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_CNFET_PMOS_cycling.toml", polarity="PMOS")

for n in range(repeat):
    print(f"Step {n+1}/{repeat}: Running {cycles} SET/RESET pulses")

    # runs pulsed cycling pattern (looping done by an ni digital pattern)
    nisys.cnfet_pulse_cycling(
        cycles=cycles,
    )

# run spot measurement to get current at some voltage
for n in range(nread):
    iv_data = nisys.cnfet_spot_iv(
        v_wl=-1.0,
        v_bl=-0.05,
        v_sl=0.0,
    )
    print(iv_data)

nisys.close()