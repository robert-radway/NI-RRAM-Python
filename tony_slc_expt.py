"""Tony's experiment"""
import argparse, time
import numpy as np
from nirram import NIRRAM

# Get arguments
parser = argparse.ArgumentParser(description="Program a bitstream to a chip.")
parser.add_argument("chipname", help="chip name for logging")
parser.add_argument("outfile", help="file to output to")

# Expect to receive two arg numbers when specifying a LRS (or HRS) range
parser.add_argument("--hrs-range", nargs='+', type=float, default=[100e3, 1e9], help="target HRS")

parser.add_argument("--start-addr", type=int, default=0, help="start addr")
parser.add_argument("--end-addr", type=int, default=128, help="end addr")
parser.add_argument("--step-addr", type=int, default=1, help="addr step")
parser.add_argument("--iterations", type=int, default=3, help="number of programming iterations")
args = parser.parse_args()

# Open outfile
outfile = open(args.outfile, "a")

# Initialize NI system
nisys = NIRRAM(args.chipname, "settings/tony_slc.json")

# RESET cells
for vwl_set in np.arange(1.7, 0.5, -0.1):
    nisys.settings["SET"]["VWL"] = vwl_set
    for addr in range(args.start_addr, args.end_addr, args.step_addr):
        nisys.set_addr(addr)
        target = nisys.target(args.hrs_range[0], args.hrs_range[1], debug=False)
        nisys.set_pulse()
        outfile.write(f"{addr}\t{target[0]}\t{vwl_set}\t")
        for _ in range(100):
            
        print(f"Address {addr}: {target[0]}, {final[0]}")

# Shutdown
outfile.close()
nisys.close()
