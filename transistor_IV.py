"""Script to perform a read voltage sweep on a chip"""
import argparse
import numpy as np
from digitalpattern import NIRRAM
import nidigital
import matplotlib.pyplot as plt


# Get arguments
parser = argparse.ArgumentParser(description="RESET a chip.")
parser.add_argument("device_no", help="chip name for logging")
parser.add_argument("--start-vds", type=int, default=-1.8, help="start vds")
parser.add_argument("--end-vds", type=int, default=-1.8, help="end vds")
parser.add_argument("--step-vds", type=int, default=1, help="step vds")
parser.add_argument("--start-vgs", type=int, default=-1.8, help="start vgs")
parser.add_argument("--end-vgs", type=int, default=1.8, help="end vgs")
parser.add_argument("--step-vgs", type=int, default=100, help="step vgs")
args = parser.parse_args()

# Initialize NI system
nisys = NIRRAM(args.device_no, args.device_no, settings="settings/DEC3.json")
# nisys.digital.channels["Body"].selected_function = nidigital.SelectedFunction.PPMU
# nisys.digital.channels["Body"].ppmu_voltage_level = 1.8
# nisys.digital.channels["Body"].ppmu_source()
results=[]
labels = np.linspace(args.start_vds, args.end_vds, args.step_vds)
x = np.linspace(args.start_vgs, args.end_vgs, args.step_vgs)
# Do operation across cells
i=0
for vds in labels:
    results.append([])
    for vgs in x:
        # 0 --> Body
        # 1 --> Source
        # 2 --> Drain
        # 3 --> Gate
        res_array, cond_array, meas_i_array, meas_v_array = nisys.read(vbl=vds, vsl=0, vwl=vgs)
        results[i].append(-meas_i_array.loc["WL_0", "BL_0"])
    i += 1
results = np.array(results)
plt.semilogy(x, results.T)
plt.show()
nisys.close()
