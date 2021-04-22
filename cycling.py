"""Perform SET-RESET cycles on RRAM cells"""
import argparse
from nirram import NIRRAM

# Get arguments
parser = argparse.ArgumentParser(description="Perform SET-RESET cycles on cells.")
parser.add_argument("chipname", help="chip name for logging")
parser.add_argument("outfile", help="file to output to")

# Expect to receive two arg numbers when specifying a LRS (or HRS) range
parser.add_argument("--start-addr", type=int, default=0, help="start addr")
parser.add_argument("--end-addr", type=int, default=128, help="end addr")
parser.add_argument("--step-addr", type=int, default=1, help="addr step")
parser.add_argument("--iterations", type=int, default=50, help="number of cycles to iterate")
parser.add_argument("--readiter", type=int, default=25, help="number of cycles to read after")
args = parser.parse_args()

# Open outfile
outfile = open(args.outfile, "a")

# Initialize NI system
nisys = NIRRAM(args.chipname, "settings/slc.json")

# RESET cells
for addr in range(args.start_addr, args.end_addr, args.step_addr):
    print(addr)
    for i in range(args.iterations):
        nisys.set_addr(addr)
        nisys.set_pulse()
        if i % args.readiter == (args.readiter-1):
            initial = nisys.read()
        nisys.reset_pulse()
        if i % args.readiter == (args.readiter-1):
            final = nisys.read()
            print(f"{addr}\t{initial[0]}\t{final[0]}\t{i+1}\n")
            outfile.write(f"{addr}\t{initial[0]}\t{final[0]}\t{i+1}\n")

# Shutdown
outfile.close()
nisys.close()
