"""Tony's SLC experiment"""
import argparse
import numpy as np
from nirram import NIRRAM

# Get arguments
parser = argparse.ArgumentParser(description="Program a bitstream to a chip.")
parser.add_argument("chipname", help="chip name for logging")
parser.add_argument("outfile", help="file to output to")

# Expect to receive two arg numbers when specifying a LRS (or HRS) range
parser.add_argument("--hrs-range", nargs='+', type=float, default=[62.5e3, 1e9], help="target HRS")
parser.add_argument("--lrs-targ", type=float, default=19.23e3, help="target LRS")

parser.add_argument("--start-addr", type=int, default=0, help="start addr")
parser.add_argument("--end-addr", type=int, default=32768, help="end addr")
parser.add_argument("--step-addr", type=int, default=2, help="addr step")
args = parser.parse_args()

# Open outfile
outfile = open(args.outfile, "a")

# Initialize NI system
nisys = NIRRAM(args.chipname)

# RESET cells and then pulse
for vwl_set in np.arange(1.6, 0.5, -0.1):
    nisys.settings["SET"]["VWL"] = vwl_set
    for addr in range(args.start_addr, args.end_addr, args.step_addr):
        nisys.set_addr(addr)
        # Retry until finished (up to 4x)
        for i in range(1,5):
            target = nisys.target(args.hrs_range[0], args.hrs_range[1], debug=False)
            nisys.set_pulse()
            final = nisys.read()
            if final[0] <= args.lrs_targ:
                break
        outfile.write(f"{addr}\t{target[0]}\t{final[0]}\t{vwl_set}\t{i}\n")
        #print(f"{addr}\t{target[0]}\t{final[0]}\t{vwl_set}\t{i}\n")

# Shutdown
outfile.close()
nisys.close()
