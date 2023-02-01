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
import nidigital
import numpy as np
import time

# Get arguments
parser = argparse.ArgumentParser(description="NBTI measurement")
parser.add_argument("settings", help="settings filename")
parser.add_argument("chip", help="chip name for logging")
parser.add_argument("device", help="device name for logging")
parser.add_argument("--polarity", type=str, nargs="?", default="PMOS", help="polarity of device (PMOS or NMOS)")
parser.add_argument("--tstart", type=float, nargs="?", default=1e-1, help="when to start reading iv after applying dc gate bias")
parser.add_argument("--tend", type=float, nargs="?", default=1e4, help="when to stop reading")
parser.add_argument("--samples", type=int, nargs="?", default=100, help="number of samples to read during the time range")
parser.add_argument("--read_bias", type=float, nargs="?", default=-0.1, help="read drain bias in volts")
parser.add_argument("--read_gate_bias", type=float, nargs="?", default=-1.2, help="constant gate bias in volts")
parser.add_argument("--gate_bias", type=float, nargs="?", default=-1.8, help="constant gate bias in volts")

args = parser.parse_args()

# unpack args for convenience
tstart = args.tstart
tend = args.tend
samples = args.samples
v_read = args.read_bias
v_gate = args.gate_bias
v_read_gate_bias = args.read_gate_bias

# create time points when device should be measured
print(f"Creating log sampling points from {tstart} to {tend} with {samples} samples")

t_measure_points = np.logspace(np.log10(tstart), np.log10(tend), samples)

print(f"Time sampling points: {t_measure_points}")

timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
data_foldername = f"{timestamp}_{str(args.chip)}_{str(args.device)}"
path_data_folder = os.path.join("data", data_foldername)
os.makedirs(path_data_folder, exist_ok=True)
path_data_measurement = os.path.join(path_data_folder, "nbti_id_vs_time.json")

# save config that will be run
config = {
    "settings": args.settings,
    "chip": args.chip,
    "device": args.device,
    "polarity": args.polarity,
    "tstart": tstart,
    "tend": tend,
    "samples": samples,
    "v_read": v_read,
    "v_gate": v_gate,
    "v_read_gate_bias": v_read_gate_bias,
}
with open(os.path.join(path_data_folder, "config.json"), "w+") as f:
    json.dump(config, f, indent=4)

# Initialize NI system
# For CNFET: make sure polarity is PMOS
nisys = NIRRAM(args.chip, args.device, settings=args.settings, polarity=args.polarity)
# nisys.close()
# exit()

# ==============================================================================
# DO INITIAL COARSE I-V curve
# ==============================================================================
# used for fitting I-V to find VT shift
# run spot measurement to get current at some voltage
initial_iv = []
# for v_wl in [0.0]:
# for v_wl in [0.2, 0.1, 0.0, -0.1, -0.2, -0.3, -0.4, -0.6]:
# for v_wl in [0.0]: # for 1 V bias
# for v_wl in [0.2, 0.0, -0.2, -0.4, -0.6, -0.8, -1.0, -1.2]: # for 1 V bias
# for v_wl in [0.0, -0.4, -0.8, -1.2]: # for 1 V bias
for v_wl in [0.2, 0.0, -0.2, -0.4, -0.6, -0.8, -1.0, -1.2, -1.4]: # for 1 V bias
# for v_wl in [1.2, 1.0, 0.8, 0.6, 0.4, 0.2, 0.0, -0.2, -0.4, -0.6, -0.8, -1.0, -1.2]: # i-v curve
# for v_wl in [-1.2, -1.0, -0.8, -0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2]: # i-v curve
# for v_wl in np.linspace(-2.0, 2.0, 41): # i-v curve
    iv_data = nisys.cnfet_spot_iv(
        v_wl=v_wl,
        v_bl=v_read,
        v_sl=0.0,
    )
    print(iv_data)
    initial_iv.append(iv_data)
    # give some relaxation time
    # time.sleep(0.5)
    time.sleep(10.0)

# nisys.close()
# exit()

# save in json format
path_initial_iv_json = os.path.join(path_data_folder, f"initial_iv.json")
with open(path_initial_iv_json, "w+") as f:
    json.dump(initial_iv, f, indent=2)

# also write into csv
path_initial_iv_csv = os.path.join(path_data_folder, f"initial_iv.csv")
with open(path_initial_iv_csv, "w+") as f:
    f.write("v_bl,i_bl,v_sl,i_sl,v_wl,i_wl\n")
    for iv in initial_iv:
        f.write(f"{iv['v_bl']},{iv['i_bl']},{iv['v_sl']},{iv['i_sl']},{iv['v_wl']},{iv['i_wl']}\n")

# uncomment to close after iv
# nisys.close()
# exit()

# ==============================================================================
# DO NBTI TIME GATE VOLTAGE STRESS MEASUREMENT
# ==============================================================================
# choose BL to read from, for now just use first bl
bl = nisys.bls[0]
wl = nisys.wls[0]

# data that will be saved
data_measurement = {
    "t": [],   # time in seconds when measurement is taken
    "v_d": [], # drain voltage read
    "i_d": [], # drain current read
}

# turn on DC gate bias
nisys.ppmu_set_vwl(wl, v_gate)

# take initial timestamp when measurement begins
# NOTE: need to guess or measure roughly how long it takes
# from turning on DC bias to when this timestamp is taken
# do this on oscilloscope by measuring delay between setting ppmu
# and when pulse appears
t0 = time.perf_counter_ns() # make sure to use perf_counter, includes time during sleeps

# wait for each measurement point
for t_next_measure in t_measure_points:
    # wait until next measurement time
    dt = t_next_measure - ((time.perf_counter_ns() - t0) * 1e-9)
    if dt > 0:
        time.sleep(dt)
    
    t_measure = (time.perf_counter_ns() - t0) * 1e-9

    # turn on drain bias and do measurement, then turn off drain bias
    nisys.ppmu_set_vbl(bl, v_read)
    nisys.ppmu_set_vwl(wl, v_read_gate_bias)
    nisys.digital.channels[bl].selected_function = nidigital.SelectedFunction.PPMU
    meas_v = nisys.digital.channels[bl].ppmu_measure(nidigital.PPMUMeasurementType.VOLTAGE)[0]
    meas_i = nisys.digital.channels[bl].ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)[0]
    nisys.ppmu_set_vwl(wl, v_gate)
    nisys.ppmu_set_vbl(bl, 0.0)

    # print measurement
    print(f"t={t_measure}, v_d={meas_v}, i_d={meas_i}")

    # save measurement and time
    data_measurement["t"].append(t_measure)
    data_measurement["v_d"].append(meas_v)
    data_measurement["i_d"].append(meas_i)

    # save measurement to file
    with open(path_data_measurement, "w+") as f:
        json.dump(data_measurement, f, indent=2)

# also save as csv
path_data_measurement_csv = os.path.join(path_data_folder, "nbti_id_vs_time.csv")
with open(path_data_measurement_csv, "w+") as f:
    f.write("t,v_d,i_d\n")
    for t, v_d, i_d in zip(data_measurement["t"], data_measurement["v_d"], data_measurement["i_d"]):
        f.write(f"{t},{v_d},{i_d}\n")

nisys.ppmu_all_pins_to_zero()
nisys.close()