"""Script to perform a read voltage sweep on a chip"""
import argparse
import numpy as np
from nirram import NIRRAM
import matplotlib.pyplot as plt


# Get arguments
parser = argparse.ArgumentParser(description="RESET a chip.")
parser.add_argument("device_no", help="chip name for logging")
parser.add_argument("--start-vds", type=int, default=0, help="start vds")
parser.add_argument("--end-vds", type=int, default=1.8, help="end vds")
parser.add_argument("--step-vds", type=int, default=6, help="step vds")
parser.add_argument("--start-vgs", type=int, default=-1.8, help="start vgs")
parser.add_argument("--end-vgs", type=int, default=1.8, help="end vgs")
parser.add_argument("--step-vgs", type=int, default=36, help="step vgs")
args = parser.parse_args()

# Initialize NI system
nisys = NIRRAM(args.device_no,settings="settings/DEC3.json")

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
        nisys.set_ppmu({3: vgs, 1:vds, 2:0, 0:0})
        voltages, currents = nisys.read_ppmu(pins=[0,1,2,3])
        results[i].append(currents[1])
    i += 1
results = np.array(results)
plt.semilogy(x, results.T)
plt.show()
nisys.close()
