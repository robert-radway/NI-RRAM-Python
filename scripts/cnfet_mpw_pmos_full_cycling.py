"""
Script for CNFET PMOS cycling on SkyWater MPW wafer.
This contains settings for pulsed cycling cnfet with voltage
levels that mimic the biases during 1T1R operation.
Used for "endurance" measurement of CNFET, e.g. see the accumulated
NBTI/PBTI effects during pulsed operation.

Unlike other script, this does hard coded log-spaced cycling
sweep and only spot I/V measurements using NI system.

I/V Measure (initial cycle 0)
Pulse Cycle 100
I/V Measure (1e2)
Pulse Cycle 900
I/V Measure (1e3)
Pulse Cycle 9000
I/V Measure (1e4)
... 


NOTE: NI system I/V measurement is DC, but based on
measurements, dc bias around the measurement voltage levels
does not really shift device as much...the 4 V bias and 1e6
accumulated cycling has more impact than DC sweep at
lower biases.
"""
import argparse
from datetime import datetime
import json
import os
from digitalpattern.nirram import NIRRAM


# Get arguments
parser = argparse.ArgumentParser(description="RESET a chip.")
parser.add_argument("chip", help="chip name for logging")
parser.add_argument("device", help="device name for logging")
parser.add_argument("--read", type=int, nargs="?", default=1, help="number of times to read cnfet iv output after cycling")
parser.add_argument("--pattern", type=str, nargs="?", default="set_reset", help="pattern name in config .toml to run")

args = parser.parse_args()

# unpack args for convenience
nread = args.read
pattern = args.pattern

# Initialize NI system
# For CNFET: make sure polarity is PMOS
nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_CNFET_PMOS_cycling.toml", polarity="PMOS")

timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
data_foldername = f"{timestamp}_{str(args.chip)}_{str(args.device)}"
path_data_folder = os.path.join("data", data_foldername)
os.makedirs(path_data_folder, exist_ok=True)

# save config that will be run
with open(os.path.join(path_data_folder, "config.json"), "w+") as f:
    json.dump(nisys.settings["cnfet"][args.pattern], f, indent=4)

# do initial coarse voltage I-V curve
# used for fitting I-V to find VT shift
# run spot measurement to get current at some voltage
initial_iv = []
for v_wl in [0.0, -0.4, -0.8, -1.2, -1.6]:
    iv_data = nisys.cnfet_spot_iv(
        v_wl=v_wl,
        v_bl=-0.05,
        v_sl=0.0,
    )
    print(iv_data)
    initial_iv.append(iv_data)
path_initial_iv = os.path.join(path_data_folder, f"initial_iv.json")
with open(path_initial_iv, "w+") as f:
    json.dump(initial_iv, f, indent=2)

# load spot IV read sampling voltage conditions
read_v_wl = nisys.settings["cnfet"][args.pattern]["read_v_wl"]
read_v_bl = nisys.settings["cnfet"][args.pattern]["read_v_bl"]
read_v_sl = nisys.settings["cnfet"][args.pattern]["read_v_sl"]

# accumulator for total cycles run
total_cycles = 0

# data storage map, cycle count => data array
data_after_cycles = {} 

for repeat, cycles in [ # (repeat, cycles)
    ( 0, 0),     # initial measurement
    ( 1, 1),     # 1e0
    ( 1, 9),     # 1e1
    ( 1, 90),    # 1e2
    ( 1, 900),   # 1e3
    ( 1, 9000),  # 1e4 
    # ( 9, 10000), # 1e5
    # (18, 50000), # 1e6
]:
    total_cycles += (repeat * cycles)

    for n in range(repeat):
        print(f"Step {n+1}/{repeat}: Running {cycles} pulses")

        # runs pulsed cycling pattern (looping done by an ni digital pattern)
        nisys.cnfet_pulse_cycling(
            pattern=pattern,
            cycles=cycles,
        )

    # run spot measurement to get current at some voltage
    all_data = []
    for n in range(nread):
        iv_data = nisys.cnfet_spot_iv( # TODO: make this input arg
            v_wl=read_v_wl,
            v_bl=read_v_bl,
            v_sl=read_v_sl,
        )
        print(iv_data)
        all_data.append(iv_data)
    data_after_cycles[total_cycles] = all_data

# save data after finishing all cycles
# DO HERE NOT INSIDE LOOP!!! because file io is slow and
# we want to continuously pulse while minimizing relaxation
# time caused by running other code
for ncycles, data in data_after_cycles.items():
    path_data = os.path.join(path_data_folder, f"iv_{ncycles}.json")
    with open(path_data, "w+") as f:
        json.dump(all_data, f, indent=2)

nisys.close()