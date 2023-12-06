"""
11/2023
Andrew Yu

Script for CNFET PMOS DC and AC NBTI for SkyWater MPW wafer.
This measures accumulated delta ID and interpolated VT over a 
stress period, measured at logarithmically spaced time points.

FOR AC NBTI:
This measured accumulated delta ID and interpolated VT like DC NBTI
except the stress is a square pulsed AC signal with configurable
duty cycle. This allows relaxation between stress intervals. This mimics
more realistic circuit operations.

NOTE: NI system I/V measurement is DC, but based on
measurements, dc bias around the measurement voltage levels
does not really shift device as much...the 4 V bias and 1e6
accumulated cycling has more impact than DC sweep at
lower biases.

NOTE: boosting voltages
NI system only goes from -2 V to 6 V.
For NBTI, if we want to do biases more than -2 V we need to "boost"
the voltages to a higher initial value.
E.g. for a -3 V bias:
VSL = VBL = 1 V
VWL = -2 V

So the "boost" voltage is the initial reference voltage we set the lines.
Make sure to do control tests to ensure that VSL,VBL,VWL = 0,0,-2
gives the sam results as VSL,VBL,VWL = 1,1,-1 !! 
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
parser.add_argument("--tstart", type=float, nargs="?", default=10e-3, help="when to start reading iv after applying dc gate bias")
parser.add_argument("--tend", type=float, nargs="?", default=2e3, help="when to stop reading")
parser.add_argument("--tstart-relax", type=float, nargs="?", default=10e-3, help="when to start reading iv after stopping bias stress")
parser.add_argument("--tend-relax", type=float, nargs="?", default=2e3, help="when to stop reading relaxation")
parser.add_argument("--samples", type=int, nargs="?", default=100, help="number of samples to read during the time range")
parser.add_argument("--samples-relax", type=int, nargs="?", default=100, help="number of samples to read during the time range")
parser.add_argument("--relax", action=argparse.BooleanOptionalAction, default=True, help="Do relaxation measurement")
parser.add_argument("--relax-iv", action=argparse.BooleanOptionalAction, default=False, help="Do relaxation IV measurement")
parser.add_argument("--read-bias", type=float, nargs="?", default=-0.1, help="read drain bias in volts")
parser.add_argument("--read-gate-bias", type=float, nargs="?", default=-1.2, help="read gate bias in volts")
parser.add_argument("--gate-bias", type=float, nargs="?", default=-2.0, help="stress constant gate bias in volts")
parser.add_argument("--boost-voltage", type=float, nargs="?", default=0, help="boost all lines by this value")
parser.add_argument("--boost-sleep", type=float, nargs="?", default=10.0, help="seconds to wait after boosting")
parser.add_argument("--efield", type=float, nargs="?", default=0.0, help="if >0, targets an efield instead of gate bias (units are MV/cm)")
parser.add_argument("--eot", type=float, nargs="?", default=0.0, help="oxide eot in nm, needed if specifying an efield")
parser.add_argument("--clamp-vt", type=bool, nargs="?", default=False, help="if VT not within a range, exit")
parser.add_argument("--vt-min", type=float, nargs="?", default=-0.1, help="vt min for clamp vt")
parser.add_argument("--vt-max", type=float, nargs="?", default=0.2, help="vt max for clamp vt")
parser.add_argument("--initial-sweep", type=float, nargs="+", default=[0.4, -1.4, 0.2], help="pre-stress IDVG gate voltage initial sweep range [start, stop, step]")
parser.add_argument("--initial-sweep-sleep", type=float, nargs="?", default=10.0, help="time to sleep between each initial IDVG sweep spot measurement point")

# AC NBTI arguments
parser.add_argument("--ac", action="store_true", default=False, help="Do AC pulsed stress")
parser.add_argument("--ac-freq", type=float, nargs="?", default=100e3, help="AC frequency for stress")
parser.add_argument("--dutycycle", type=float, nargs="?", default=0.1, help="AC pulse duty cycle for stress time (0.2 = 20 percent on, 80 percent off)")
parser.add_argument("--pattern", type=str, nargs="?", default="settings/patterns/nbti_ac.digipat", help="ni digital pattern for ac nbti pulsing")
parser.add_argument("--t-unit", type=float, nargs="?", default=50e-9, help="ni digital pattern unit cycle time interval")

args = parser.parse_args()

# unpack args for convenience
tstart = args.tstart
tend = args.tend
samples = args.samples
tstart_relax = args.tstart_relax
tend_relax = args.tend_relax
samples_relax = args.samples_relax
do_relax = args.relax
do_relax_iv = args.relax_iv
v_read = args.read_bias
v_read_gate_bias = args.read_gate_bias
v_gate = args.gate_bias
v0 = args.boost_voltage
boost_sleep = args.boost_sleep
efield_ox = args.efield
eot = args.eot
clamp_vt = args.clamp_vt
VT_MIN = args.vt_min
VT_MAX = args.vt_max
v_wl_initial_sweep = args.initial_sweep
initial_sweep_sleep = args.initial_sweep_sleep
ac_stress = args.ac
ac_freq = args.ac_freq
ac_dutycycle = args.dutycycle
ac_period = 1.0 / ac_freq
ac_t_stress = ac_dutycycle * ac_period
ac_t_relax = (1.0 - ac_dutycycle) * ac_period
ac_stress_pattern = args.pattern
t_nbti_ac_unit = args.t_unit

# print info using AC stress
if ac_stress:
    print(f"Using AC stress signal with frequency {ac_freq:.2e} duty cycle {ac_dutycycle:.2f} (t_stress = {ac_t_stress:2e}, t_relax={ac_t_relax:.2e})")

# require eot if using efield as input
if efield_ox != 0 and eot == 0:
    raise ValueError("EOT must be specified if targetted a Eox field for stress")

# make sure polarity right (TODO: manual override this)
if args.polarity.lower() == "pmos" and efield_ox > 0:
    raise ValueError("For PMOS NBTI, efield must be <0")
elif args.polarity.lower() == "nmos" and efield_ox < 0:
    raise ValueError("For NMOS PBTI, efield must be >0")

def into_sweep_range(v) -> list:
    """Convert different initial-sweep input formats into
    list of sweep values. Conversions are:
    - single num -> [x]: single number to a list with 1 value
    - 3 value list [x0, x1, dx]: make a sweep range:
        [x0, x0 + dx, ..., x1]
    - >3 value list [x0, x1, x2, ...] -> list: keep as list
    """
    if isinstance(v, float) or isinstance(v, int):
        return [v]
    elif isinstance(v, list):
        if len(v) == 3:
            v_start = v[0]
            v_stop = v[1]
            v_step = v[2]
            # abs required to ensure no negative points if stop < start
            # round required due to float precision errors, avoids .9999 npoint values
            npoints = 1 + int(abs(round((v_stop - v_start)/v_step)))
            v_range = np.linspace(v_start, v_stop, npoints, dtype=np.float64)
            # floating point errors can cause 0 to instead be small value like
            # 2.77555756e-17, do a pass to round any of these near-zero
            # floating point errors to zero
            for i in range(0, len(v_range)):
                if np.abs(v_range[i]) < 1e-12:
                    v_range[i] = 0.0
            return v_range.tolist()
        else:
            return v
    else:
        raise ValueError(f"Sweep range is an invalid format: {v}")

# convert initial idvg sweep vwl (vg) input format into sweep range
v_wl_initial_sweep = into_sweep_range(v_wl_initial_sweep)
print(f"vwl initial sweep: {v_wl_initial_sweep}")

# create time points when device should be measured
print(f"STRESS: Creating log sampling points from {tstart} to {tend} with {samples} samples")
print(f"RELAX: Creating log sampling points from {tstart_relax} to {tend_relax} with {samples_relax} samples")

t_measure_points_stress = np.logspace(np.log10(tstart), np.log10(tend), samples)
t_measure_points_relax = np.logspace(np.log10(tstart_relax), np.log10(tend_relax), samples_relax)

print(f"Time sampling points STRESS: {t_measure_points_stress}")
print(f"Time sampling points RELAX: {t_measure_points_relax}")

timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
data_foldername = f"{timestamp}_{str(args.chip)}_{str(args.device)}"
path_data_folder = os.path.join("data", data_foldername)
os.makedirs(path_data_folder, exist_ok=True)
path_data_stress = os.path.join(path_data_folder, "nbti_id_vs_time_stress")
path_data_relax = os.path.join(path_data_folder, "nbti_id_vs_time_relax")


def idvg_vt_extrapolation(
    v_gs: np.ndarray,
    i_d: np.ndarray,
    v_ds: float,
    v_ds_v_t_factor: float = 0.5,
    v_gs_window: (float, float) = None,
    polarity: str = "pmos",
    return_gm: bool = False,
):
    """VT extraction for a single ID-VG curve vector.
    Determine threshold VT from largest gm slope extrapolated to x-axis.
    
    i_d = gm_max * v_gs_max + y0
    0 = gm_max * v_t + y0
    v_t = -y0/gm_max = -(i_d - gm_max * v_gs_max) / gm_max = v_gs_max - i_d/gm_max
    
    Also add drain bias correction, assuming linear model
      Id = W/L * Cox * mu * (Vgs - Vt - m*Vds) * Vds
      Id ~ a * (Vgs - Vt - m*Vds)
    Normally m = 1/2
    
    Since devices can be ambipolar, window to > or < Vmin depending on
    whether this is declared as NMOS or PMOS.
    """
    assert v_gs.shape == i_d.shape # must be same shape
    num_points = v_gs.shape[0]

    # absolute value id
    i_d_abs = np.abs(i_d)

    # gm = gradient (take abs)
    gm = np.abs(np.gradient(i_d, v_gs))
    
    # true = forward sweep (-V to +V)
    # false = reverse sweep (+V to -V)
    sweep_direction = (v_gs[1] - v_gs[0]) > 0

    # index of minimum current
    idx_i_min = np.argmin(i_d_abs)

    # default index range to search for peak gm for VT extraction
    if polarity.lower() == "nmos":
        if sweep_direction == True: # forward (vgs = 0...VDD)
            idx_gm_max_search_start = idx_i_min
            idx_gm_max_search_end = -1
        else: # backward (vgs = VDD...0)
            idx_gm_max_search_start = 0
            idx_gm_max_search_end = idx_i_min
    else: # pmos
        if sweep_direction == True: # forward (vgs = 0..VDD)
            idx_gm_max_search_start = 0
            idx_gm_max_search_end = idx_i_min + 1
        else: # backward (vgs = VDD...0)
            idx_gm_max_search_start = idx_i_min
            idx_gm_max_search_end = -1
    
    # refine gm vgs index search range using window
    if v_gs_window is not None:
        v_gs_window_sorted = np.sort(v_gs_window)
        v_start = v_gs_window_sorted[0]
        v_end = v_gs_window_sorted[1]
        
        v_gs_range = v_gs

        idx_search_max = len(v_gs_range) - 1
        idx_search_min = -len(v_gs_range)

        # clamp idx_gm_max_search_end, since it may be > length of array
        if idx_gm_max_search_end > idx_search_max:
            idx_gm_max_search_end = idx_search_max

        if sweep_direction == True: # forward (vgs = 0...VDD)
            while v_gs_range[idx_gm_max_search_start] < v_start:
                if idx_gm_max_search_start >= idx_search_max:
                    print(f"gm: gm_max search window reached end: {idx_gm_max_search_start}")
                    break
                idx_gm_max_search_start += 1
            while v_gs_range[idx_gm_max_search_end] > v_end:
                if idx_gm_max_search_end <= idx_search_min:
                    print(f"gm: gm_max search window reached end: {idx_gm_max_search_end}")
                    break
                idx_gm_max_search_end -= 1
        else: # backward (vgs = VDD...0)
            while v_gs_range[idx_gm_max_search_start] > v_end:
                if idx_gm_max_search_start >= idx_search_max:
                    print(f"gm: gm_max search window reached end: {idx_gm_max_search_start}")
                    break
                idx_gm_max_search_start += 1
            while v_gs_range[idx_gm_max_search_end] < v_start:
                if idx_gm_max_search_end <= idx_search_min:
                    print(f"gm: gm_max search window reached end: {idx_gm_max_search_end}")
                    break
                idx_gm_max_search_end -= 1
    
    # same variable, easier to read
    idx_start = idx_gm_max_search_start
    idx_end = idx_gm_max_search_end
    if idx_end < 0:
        idx_end = num_points - idx_end + 1 # convert to normal indexing
    
    if idx_end > idx_start: # normal case
        gm_window = np.abs(gm[idx_start:idx_end])
        idx_gm_max = idx_start + np.argmax(gm_window)
    else: # degenerate case, somehow idx start <= idx_end
        print(f"gm: Invalid vt gm_max search window: {idx_start} : {idx_end}")
        idx_gm_max = idx_start
    
    # print(f"v_ds = {v_ds}")
    # print("idx_i_min = ", idx_i_min)
    # print("idx_start = ", idx_start)
    # print("idx_end = ", idx_end)
    # print("idx_gm_max = ", idx_gm_max)
    gm_max = gm[idx_gm_max]
    v_gs_gm_max = v_gs[idx_gm_max]
    i_d_gm_max = i_d[idx_gm_max]
    v_t = v_gs_gm_max - i_d_gm_max / gm_max - (v_ds_v_t_factor * v_ds)
    
    if return_gm is True:
        return v_t, gm
    else:
        return v_t


# ==============================================================================
# DO INITIAL COARSE I-V curve
# ==============================================================================
# Initialize NI system
# For CNFET: make sure polarity is PMOS
nisys = NIRRAM(args.chip, args.device, settings=args.settings, polarity=args.polarity)
# nisys.close()
# exit()

# used for fitting I-V to find VT shift
# run spot measurement to get current at some voltage

### TODO: abstract initial sweep range into an input
# V_WL_INITIAL_SWEEP = [0.0]
# V_WL_INITIAL_SWEEP = [0.0] # for 1 V bias
# V_WL_INITIAL_SWEEP = [0.2, 0.0, -0.2, -0.4, -0.6, -0.8, -1.0, -1.2] # for 1 V bias
# V_WL_INITIAL_SWEEP = [0.0, -0.4, -0.8, -1.2]
# V_WL_INITIAL_SWEEP = [0.3, 0.2, 0.1, 0.0, -0.1, -0.2, -0.3, -0.4] # 2 MV/cm
# V_WL_INITIAL_SWEEP = [0.4, 0.2, 0.0, -0.2, -0.4, -0.6] # 2 MV/cm
# V_WL_INITIAL_SWEEP = [0.4, 0.2, 0.0, -0.2, -0.4, -0.6, -0.8] # 4 MV/cm
# V_WL_INITIAL_SWEEP = [0.6, 0.4, 0.2, 0.0, -0.2, -0.4, -0.6, -0.8, -1.0] # 6-8 MV/cm
# V_WL_INITIAL_SWEEP = [0.6, 0.4, 0.2, 0.0, -0.2, -0.4, -0.6, -0.8, -1.0, -1.2] # 8 - 10 MV/cm
# V_WL_INITIAL_SWEEP = [0.6, 0.4, 0.2, 0.0, -0.2, -0.4, -0.6, -0.8, -1.0, -1.2, -1.4] # 10 - 12 MV/cm
# V_WL_INITIAL_SWEEP = [0.6, 0.4, 0.2, 0.0, -0.2, -0.4, -0.6, -0.8, -1.0, -1.2, -1.4, -1.6] # 10 - 12 MV/cm
# V_WL_INITIAL_SWEEP = [1.0, 0.8, 0.6, 0.4, 0.2, 0.0, -0.2, -0.4, -0.6, -0.8, -1.0, -1.2, -1.4] # 10 - 12 MV/cm
# V_WL_INITIAL_SWEEP = [1.2, 1.0, 0.8, 0.6, 0.4, 0.2, 0.0, -0.2, -0.4, -0.6, -0.8, -1.0, -1.2]
# V_WL_INITIAL_SWEEP = [-1.2, -1.0, -0.8, -0.6, -0.4, -0.2, 0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2]
# V_WL_INITIAL_SWEEP = np.linspace(-2.0, 2.0, 41)

# V_WL_INITIAL_SWEEP = [0.2, 0.1, 0.0, -0.1, -0.2, -0.3, -0.4] # for 0.6 V stress
# V_WL_INITIAL_SWEEP = [0.4, 0.2, 0.0, -0.2, -0.4, -0.6, -0.8, -1.0, -1.2, -1.4] # 10 MV/cm

# TODO: need to turn this into an arg
V_WL_POST_SWEEP = [0.4, 0.2, 0.0, -0.2, -0.4, -0.6, -0.8, -1.0, -1.2, -1.4, -1.6, -1.8, -2.0] # 10 MV/cm

initial_iv = []

# v_wl_initial_sweep = []

for v_wl in v_wl_initial_sweep:
    iv_data = nisys.cnfet_spot_iv(
        v_wl=v_wl,
        v_bl=v_read,
        v_sl=0.0,
    )
    print(iv_data)
    initial_iv.append(iv_data)
    if initial_sweep_sleep > 0:
        # give some relaxation time
        # time.sleep(10e-3)
        # time.sleep(10.0)
        time.sleep(initial_sweep_sleep)

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
# DETERMINE STRESS CONFIG
# If we do stress at an input electric field, we need to do initial VT
# extraction from initial IV first, to estimate "effective" oxide field
# So for an input field, we will determine boosting, stress, and read biases
# here.
# ==============================================================================

VG_MIN = -2 # minimum NI voltage allowed
VG_MAX = 6  # maximum NI voltage allowed
VG_BOOST = [-1, -0.5, 0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0] # boosting voltages to try

def vg_for_efield(efield_ox_MV_cm: float, vt: float, eot: float) -> float:
    """Return vg needed to produce given oxide field, given vt.
    Using approximation formula:
        Efield_ox_eff = (VG - VT) / EOT 
    where:
        - efield_ox_MV_cm [MV/cm]: target oxide electric field
        - vt [V]: threshold voltage
        - eot [nm]: effective oxide thickness
    """
    efield_ox_V_nm = efield_ox_MV_cm * 1e6 * 1e-7
    return vt + eot * efield_ox_V_nm

# initial sweep VT
v_gs_initial = np.array(v_wl_initial_sweep)
i_d_initial = np.array([iv['i_bl'] for iv in initial_iv])
try:
    v_t_initial, gm_initial = idvg_vt_extrapolation(
        v_gs = v_gs_initial,
        i_d = i_d_initial,
        v_ds = v_read,
        return_gm = True,
        polarity = args.polarity,
    )
    print(f"vt = {v_t_initial} V")
except Exception:
    import traceback
    print(traceback.format_exc())
    print(f"setting initial v_t as None")
    v_t_initial = None
    gm_initial = None

if efield_ox is not None and efield_ox != 0:
    vg_stress = vg_for_efield(efield_ox, v_t_initial, eot)
    print(f"eot = {eot} nm, vt = {v_t_initial} V, vg_required = {vg_stress} V (Eox check = {(vg_stress - v_t_initial) / eot * 10})")
    # deciding boosting voltage
    vg_boost = None
    if vg_stress < VG_MIN:
        for vb in VG_BOOST:
            if vg_stress + vb > VG_MIN:
                print(f"vg_boost = {vb} V needed to boost vg_stress to VG_MIN")
                vg_boost = vb
                break
    elif vg_stress > VG_MAX:
        for vb in reversed(VG_BOOST):
            if vg_stress + vb < VG_MAX:
                print(f"vg_boost = {vb} V needed to boost vg_stress to VG_MIN")
                vg_boost = vb
                break
    else:
        vg_boost = 0
    
    if vg_boost is None:
        raise ValueError(f"Could not find vg_boost for eot = {eot} nm, vg_stress = {vg_stress} V")
    
    print(f"Using: vg_boost = {vg_boost} V")

    # determine bias to do read at:
    # find first vg in vg_initial_sweep[:-1] (dont look at last point)
    # that is less than vg_stress
    vg_read = None
    for vg in reversed(v_wl_initial_sweep[:-1]):
        if np.abs(vg) < np.abs(vg_stress):
            vg_read = vg
            break
    
    if vg_read is None:
        raise ValueError(f"Could not find vg_read for eot = {eot} nm, vg_stress = {vg_stress} V")
    
    print(f"Using: vg_read = {vg_read} V")

    # set new params
    v0 = vg_boost
    v_gate = vg_stress
    v_read_gate_bias = vg_read

# save config that will be run
config = {
    "timestamp": timestamp,
    "settings": args.settings,
    "chip": args.chip,
    "device": args.device,
    "polarity": args.polarity,
    "tstart": tstart,
    "tend": tend,
    "samples": samples,
    "efield_ox": efield_ox,
    "eot": eot,
    "v_read": v_read,
    "v_gate": v_gate,
    "v_read_gate_bias": v_read_gate_bias,
    "v_boost": v0,
    "v_wl_initial_sweep": v_wl_initial_sweep,
    "v_t_initial": v_t_initial,
    # actual written voltages
    "v_s": v0,
    "v_d": v0 + v_read,
    "v_g_read": v0 + v_read_gate_bias,
    "v_g_stress": v0 + v_gate,
    "v_g_relax": v0,
    # save ac parameters
    "ac": ac_stress,
    "ac_freq": ac_freq,
    "ac_dutycycle": ac_dutycycle,
    "ac_period": ac_period,
    "ac_t_stress": ac_t_stress,
    "ac_t_relax": ac_t_relax,
    "t_unit": t_nbti_ac_unit,
}

with open(os.path.join(path_data_folder, "config.json"), "w+") as f:
    json.dump(config, f, indent=4)

### uncomment to close after sampling iv and saving config
# nisys.close()
# exit()

### TEMPORARY:
# clamp VT within range or exit
if clamp_vt:
    if v_t_initial < VT_MIN or v_t_initial > VT_MAX:
        print(f"VT = {v_t_initial} not within range ({VT_MIN}, {VT_MAX})")
        exit()

# ==============================================================================
# DO NBTI TIME GATE VOLTAGE STRESS MEASUREMENT
# ==============================================================================
# choose BL to read from, for now just use first bl
sl = nisys.sls[0]
bl = nisys.bls[0]
wl = nisys.wls[0]

def run_bias_stress_measurement_dc(
    v0: float, # reference zero voltage level
    v_stress: float,
    t_measure_points: list[float],
    path_data: str,
    t_save_threshold: float = 10.0, # time before saving to json during measurement
):
    """Common routine for stress and relaxation NBTI current measurement.
    Implements a "on-the-fly" method of holding an initial stressing
    """
    # turn on DC gate bias
    nisys.ppmu_set_vwl(wl, v0 + v_stress)

    # take initial timestamp when measurement begins
    # NOTE: need to guess or measure roughly how long it takes
    # from turning on DC bias to when this timestamp is taken
    # do this on oscilloscope by measuring delay between setting ppmu
    # and when pulse appears
    t0 = time.perf_counter_ns() # make sure to use perf_counter, includes time during sleeps

    # data that will be saved
    data_measurement = {
        "t": [],   # time in seconds when measurement is taken
        # "v_d": [], # drain voltage read # dont need
        "i_d": [], # drain current read
    }

    # set to ppmu to measure
    nisys.digital.channels[bl].selected_function = nidigital.SelectedFunction.PPMU

    # wait for each measurement point
    for n, t_next_measure in enumerate(t_measure_points):
        # wait until next measurement time
        dt = t_next_measure - ((time.perf_counter_ns() - t0) * 1e-9)
        if dt > 0:
            time.sleep(dt)
        
        t_measure = (time.perf_counter_ns() - t0) * 1e-9

        nisys.ppmu_set_vbl(bl, v0 + v_read)
        nisys.ppmu_set_vwl(wl, v0 + v_read_gate_bias)
        # meas_v = nisys.digital.channels[bl].ppmu_measure(nidigital.PPMUMeasurementType.VOLTAGE)[0] # takes ~1 ms
        meas_i = nisys.digital.channels[bl].ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)[0] # takes ~1 ms
        nisys.ppmu_set_vwl(wl, v0 + v_stress)
        nisys.ppmu_set_vbl(bl, v0)

        # print measurement
        # THIS CAUSES UNPREDICTABLE DELAY IN CODE, BUT IS OKAY BECAUSE
        # STRESS IS ON BEFORE WE PRINT. JUST MAKE SURE DO NOT PRINT BEFORE STRESS ON
        # print(f"t={t_measure}, v_d={meas_v}, i_d={meas_i}")
        print(f"t={t_measure}, i_d={meas_i}")

        # save measurement and time
        data_measurement["t"].append(t_measure)
        # data_measurement["v_d"].append(meas_v)
        data_measurement["i_d"].append(meas_i)

        # save measurement to file
        # (only do after ~10 seconds to reduce effect of delay from saving to file
        # during early fast measurements)
        if t_measure > t_save_threshold or n >= (len(t_measure_points) - 1):
            with open(path_data, "w+") as f:
                json.dump(data_measurement, f, indent=2)
    
    return data_measurement



def run_bias_stress_measurement_iv_sweep(
    v0: float, # reference zero voltage level
    v_stress: float,
    t_measure_points: list[float],
    path_data: str,
):
    """Common routine for stress and relaxation NBTI current measurement.
    Implements a "on-the-fly" method of holding an initial stressing
    """
    # turn on DC gate bias
    nisys.ppmu_set_vwl(wl, v0 + v_stress)

    # take initial timestamp when measurement begins
    # NOTE: need to guess or measure roughly how long it takes
    # from turning on DC bias to when this timestamp is taken
    # do this on oscilloscope by measuring delay between setting ppmu
    # and when pulse appears
    t0 = time.perf_counter_ns() # make sure to use perf_counter, includes time during sleeps

    # set to ppmu to measure
    nisys.digital.channels[bl].selected_function = nidigital.SelectedFunction.PPMU

    # wait for each measurement point
    for t_next_measure in t_measure_points:
        # wait until next measurement time
        dt = t_next_measure - ((time.perf_counter_ns() - t0) * 1e-9)
        if dt > 0:
            time.sleep(dt)
        
        t_measure = (time.perf_counter_ns() - t0) * 1e-9

        iv_sweep = nisys.cnfet_iv_sweep(
            v_wl=v_wl_initial_sweep,
            v_bl=v_read,
            v_sl=0.0,
            v_0=v0,
            v_wl_0=v0,
            measure_i_bl = True,
            measure_v_bl = False,
            measure_i_sl = False,
            measure_v_sl = False,
            measure_i_wl = False,
            measure_v_wl = False,
        )

        # print measurement
        # THIS CAUSES UNPREDICTABLE DELAY IN CODE, BUT IS OKAY BECAUSE
        # STRESS IS ON BEFORE WE PRINT. JUST MAKE SURE DO NOT PRINT BEFORE STRESS ON
        print(f"t={t_measure}")

        # save measurement to file
        # (only do after ~10 seconds to reduce effect of delay from saving to file
        # during early fast measurements)
        with open(f"{path_data}_t_{t_measure}.json", "w+") as f:
            json.dump(iv_sweep, f, indent=2)
    
    return


def run_bias_stress_measurement_ac(
    v0: float, # reference zero voltage level
    v_stress: float,
    t_measure_points: list[float],
    path_data: str,
    t_save_threshold: float = 10.0, # time before saving to json during measurement
    # t_nbti_ac_unit: float = 1e-5,   # 1e-5 ns base unit time interval
    # t_nbti_ac_unit: float = 100e-9,   # 10 ns base unit time interval
    pattern: str = "nbti_ac",       # this is "Pattern Name: ____" in NI digital pattern editor, not the pattern path
):
    """Routine for ac stress NBTI measurement.
    Technique with NI system looks like following:

       STRESS:           MEASURE:
       burst_pattern()   manually setting pins to fixed voltage values and
                         reading (can have ~1 ms order time delays)
                         |
       _   _   _   _     v    _   _   _   _   _   _  
      | | | | | | | |        | | | | | | | | | | | | 
      | | | | | | | |  ____  | | | | | | | | | | | |  ____
    __| |_| |_| |_| |_|    |_| |_| |_| |_| |_| |_| |_|    |_
    """
    from os.path import abspath
    from math import sqrt

    # NI RRAM PULSE SETUP
    # this time "t_nbti_ac" is hardcoded inside the .digitpat file as "Time Set"
    nisys.digital.create_time_set("t_nbti_ac")
    nisys.digital.configure_time_set_period("t_nbti_ac", t_nbti_ac_unit)

    # load pattern
    nisys.digital.load_pattern(abspath(ac_stress_pattern))

    # ni digital registers to set cycles and pulse widths
    reg_pw_stress = nidigital.SequencerRegister.REGISTER0    # stress pulse width
    reg_pw_relax = nidigital.SequencerRegister.REGISTER1     # rela pulse width
    reg_cycles_loop0 = nidigital.SequencerRegister.REGISTER2 # number of cycles loop 0
    reg_cycles_loop1 = nidigital.SequencerRegister.REGISTER3 # number of cycles loop 1
    reg_cycles_loop2 = nidigital.SequencerRegister.REGISTER4 # number of cycles loop 2

    # 16 bit register sizes, so for longer cycle counts, need to split 
    MAX_REG_INT = 65535 # max register integer, need to split cycles into 2 for loops
    MAX_2LOOP = MAX_REG_INT * MAX_REG_INT
    MAX_3LOOP = MAX_REG_INT * MAX_REG_INT * MAX_REG_INT

    # number of pulse width "units" for stress and relax
    # `t_nbti_ac_unit` sets base time unit in nidigital system
    # real pulse time is number of base time unit * pw
    # THERES SOME WEIRD EXTRA CYCLES APPEARING FROM PATTERN SOMEHOW... WTF
    # I ADJUSTED THESE PULSE WIDTHS TO MATCH, OTHERWISE FREQUENCY LOWER THAN DESIRED
    # I OSCILLOSCOPE TUNED UNTIL FREQUENCY MATCHED TO WITHIN 0.1%
    pw_set = int(ac_t_stress / t_nbti_ac_unit) - 1
    pw_relax = int(ac_t_relax / t_nbti_ac_unit) - 2

    # print(f"pw_set = {pw_set}, pw_relax = {pw_relax}")

    nisys.digital.write_sequencer_register(reg_pw_stress, pw_set)
    nisys.digital.write_sequencer_register(reg_pw_relax, pw_relax)

    # set ppmu hi/lo voltages
    body = list(nisys.body)[0]
    bl = nisys.bls[0]
    sl = nisys.sls[0]
    wl = nisys.wls[0]

    v_body_lo = v0
    v_body_hi = v0
    v_bl_lo = v0
    v_bl_hi = v0
    v_bl_x = v0 + v_read
    v_sl_lo = v0
    v_sl_hi = v0
    v_wl_lo = v0
    v_wl_hi = v0 + v_stress
    v_wl_x = v0 + v_read_gate_bias

    nisys.digital.channels[body].configure_voltage_levels(v_body_lo, v_body_hi, v_body_lo, v_body_hi, v0)
    nisys.digital.channels[bl].configure_voltage_levels(v_bl_lo, v_bl_hi, v_bl_lo, v_bl_hi, v_bl_x)
    nisys.digital.channels[sl].configure_voltage_levels(v_sl_lo, v_sl_hi, v_sl_lo, v_sl_hi, v0)
    nisys.digital.channels[wl].configure_voltage_levels(v_wl_lo, v_wl_hi, v_wl_lo, v_wl_hi, v_wl_x)
    nisys.digital.ppmu_source()

    # make pattern X states high Z
    for pin in (body, bl, sl, wl):
        nisys.digital.channels[pin].termination_mode = nidigital.TerminationMode.VTERM
    
    # set SL to ppmu to measure
    nisys.digital.channels[bl].selected_function = nidigital.SelectedFunction.PPMU

    # data to save
    result_t = []  # accumulated total stress time
    result_t_meas = [] # time measurement is occuring
    result_i_d = [] # drain current read

    # data that will be saved
    data_measurement = {
        "t": result_t,
        "t_meas":result_t_meas,
        "i_d": result_i_d,
    }

    print(f"STARTING AC NBTI...")

    # time when measurement started, for tracking
    t0 = time.perf_counter_ns() # make sure to use perf_counter, includes time during sleeps

    # calculated accumulated stress time
    t_accum_stress = 0
    
    # wait for each measurement point
    for i, t_next_measure in enumerate(t_measure_points):        
        # calculate stress cycles needed to reach next measure time as close as possible
        dt = t_next_measure - t_accum_stress

        # MAX REGISTER INTEGER VALUE IS 65535
        # SO WE NEED TO SPLIT CYCLES INTO MULTIPLE CHUNKS FOR LARGE CYCLE COUNT
        cycles = max(1, int(dt / ac_t_stress))
        if cycles < MAX_REG_INT:
            cycles_loop0 = 1
            cycles_loop1 = 1
            cycles_loop2 = cycles # most inner loop
        elif cycles < MAX_2LOOP: # try 2 loops
            sqrt_cycles = sqrt(cycles)
            cycles_loop0 = 1
            cycles_loop1 = int(sqrt_cycles)
            cycles_loop2 = cycles_loop1 + 1
            cycles = cycles_loop1 * cycles_loop2
        else: # try 3 loops
            cbrt_cycles = np.cbrt(cycles)
            # produces good pos/neg balanced error plot,
            # see CNT reliability documentation slides
            # (or plot: error = cycles_approx - cycles)
            cycles_loop0 = int(np.round(cbrt_cycles))
            cycles_loop1 = cycles_loop0 + 1
            cycles_loop2 = cycles_loop0 - 1
            cycles = cycles_loop0 * cycles_loop1 * cycles_loop2

        # DEBUGGING
        # print(f"cycles_loop0={cycles_loop0}, cycles_loop1={cycles_loop1}, cycles_loop2={cycles_loop2}")
        nisys.digital.write_sequencer_register(reg_cycles_loop0, cycles_loop0)
        nisys.digital.write_sequencer_register(reg_cycles_loop1, cycles_loop1)
        nisys.digital.write_sequencer_register(reg_cycles_loop2, cycles_loop2)

        # actual change in accumulated stress time
        t_accum_stress += cycles * ac_t_stress

        # run stress pattern
        nisys.digital.burst_pattern(
            pattern, # cnfet_pmos_pulse_cycling.digipat
            wait_until_done=False,
        )

        # print previous cycle result here while pattern is bursting
        # and save data to file
        # (takes random 1-5 ms so dont want to disturb measurement)
        if i > 0 and dt > 1.0: # only print when >1s delta time steps to make sure no issues
            print(f"[{i}] t={result_t[i-1]:.2f}, t_meas={result_t_meas[i-1]:.2f}, i_d={result_i_d[i-1]:.3e}")
            with open(path_data, "w+") as f:
                json.dump(data_measurement, f, indent=2)
        
        nisys.digital.wait_until_done(timeout=80000.0)

        # time pattern finished and measurement is occuring
        t_measure = (time.perf_counter_ns() - t0) * 1e-9

        # MEASURE DRAIN CURRENT ~2 ms
        # turns on drain for measurement
        nisys.ppmu_set_vbl(bl, v0 + v_read)
        # meas_v = nisys.digital.channels[bl].ppmu_measure(nidigital.PPMUMeasurementType.VOLTAGE)[0] # takes ~1 ms
        meas_i = nisys.digital.channels[bl].ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)[0] # takes ~1 ms
        # nisys.ppmu_set_vbl(bl, v0) # unnecessary, pattern will set

        ### ALTERNATIVELY measure source current ~1 ms
        # but source current weirder and doesnt fit old data
        # maybe in future use this for less error from delays
        # meas_i = nisys.digital.channels[sl].ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)[0] # takes ~1 ms

        # save measurement and time
        result_t.append(t_accum_stress)
        result_t_meas.append(t_measure)
        # data_measurement["v_d"].append(meas_v)
        result_i_d.append(meas_i)

    # only do at end for AC stress to avoid file saving delay
    # TODO: if ambitious, u can do file saving during loop while waiting
    # for the burst sequence to finish (set burst_pattern wait if u r certain the file saving time
    # (up to few ms) will finish before burst is done, and u will need to
    # spinlock check if the burst pattern has finished
    with open(path_data, "w+") as f:
        json.dump(data_measurement, f, indent=2)
    
    return data_measurement

### STRESS MEASUREMENT

# boost voltages
if v0 != 0:
    print(f"boosting wl/sl/bl voltage to {v0} V")
    nisys.ppmu_set_all_to_voltage(
        val=v0,
        vwl_chan=wl,
        vsl_chan=sl,
        vbl_chan=bl,
    )
    print(f"sleeping for {boost_sleep} s")
    time.sleep(boost_sleep)

if ac_stress:
    run_stress = run_bias_stress_measurement_ac
else: # dc
    run_stress = run_bias_stress_measurement_dc

data_stress = run_stress(
    v0=v0,
    v_stress=v_gate,
    t_measure_points=t_measure_points_stress,
    path_data=path_data_stress + ".json",
)

### POST STRESS IV
if do_relax_iv:
    post_iv = nisys.cnfet_iv_sweep(
        v_wl=list(reversed(V_WL_POST_SWEEP)),
        v_bl=v_read,
        v_sl=0.0,
        v_0=v0,
        v_wl_0=v0 + v_gate,
        measure_i_bl = True,
        measure_v_bl = False,
        measure_i_sl = False,
        measure_v_sl = False,
        measure_i_wl = False,
        measure_v_wl = False,
    )
    print(iv_data)

    ### save in json format
    path_post_iv_json = os.path.join(path_data_folder, f"post_iv.json")
    with open(path_post_iv_json, "w+") as f:
        json.dump(post_iv, f, indent=2)

# nisys.close()
# exit()


### RELAXATION (reset all to zero)
if do_relax:
    if v0 != 0:
        nisys.ppmu_all_pins_to_zero()
    data_relax = run_bias_stress_measurement_dc(v0=0, v_stress=0, t_measure_points=t_measure_points_relax, path_data=path_data_relax + ".json")
elif do_relax_iv:
    run_bias_stress_measurement_iv_sweep(v0=0, v_stress=0, t_measure_points=t_measure_points_relax, path_data=path_data_relax)
    data_relax = None
else:
    data_relax = None

# close ni system connection
nisys.ppmu_all_pins_to_zero()
nisys.close()

# also results as csv
for path_data, data in [
    (path_data_stress, data_stress),
    (path_data_relax, data_relax),
]:
    if data is None:
        continue
    
    path_data_csv = path_data + ".csv"
    with open(path_data_csv, "w+") as f:
        f.write("t,i_d\n")
        for t, i_d in zip(data["t"], data["i_d"]):
            f.write(f"{t},{i_d}\n")
        # f.write("t,v_d,i_d\n")
        # for t, v_d, i_d in zip(data_measurement["t"], data_measurement["v_d"], data_measurement["i_d"]):
        #     f.write(f"{t},{v_d},{i_d}\n")
