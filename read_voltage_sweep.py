"""Script to perform a read voltage sweep on a chip"""
import argparse
import numpy as np
from digitalpattern import NIRRAM

# Get arguments
parser = argparse.ArgumentParser(description="READ a chip.")
parser.add_argument("chipname", help="chip name for logging")
parser.add_argument("outfile", help="file to output to")
parser.add_argument("--start-addr", type=int, default=0, help="start address")
parser.add_argument("--end-addr", type=int, default=65536, help="end address")
parser.add_argument("--step-addr", type=int, default=1, help="address stride")
args = parser.parse_args()

# Open outfile
outfile = open(args.outfile, "a")

# Initialize NI system
nisys = NIRRAM(args.chipname)

# Do operation across cells
for addr in range(args.start_addr, args.end_addr, args.step_addr):
    nisys.set_addr(addr)
    for readvolt in np.arange(0, 0.36, 0.01):
        nisys.settings["READ"]["VBL"] = readvolt
        read = nisys.read()
        outfile.write(f"{addr}\t{readvolt}\t{read[2]}\n")
        print(f"{addr}\t{readvolt}\t{read[2]}")

# Shutdown
outfile.close()
nisys.close()
