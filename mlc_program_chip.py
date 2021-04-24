"""MLC test programming"""
import argparse
import time
import numpy as np
from nirram import NIRRAM

# Get arguments
parser = argparse.ArgumentParser(description="Program multiple levels to RRAM cells in a chip.")
parser.add_argument("chipname", help="chip name for logging")
parser.add_argument("--retention-outfile", help="file to put retention data in (default: no data)")
parser.add_argument("--ret-reads", type=int, default=1000, help="how many retention reads to do")
parser.add_argument("--num-levels", type=int, default=32, help="number of MLC levels")
parser.add_argument("--min-conductance", type=float, default=0, help="lower end of dyn range")
parser.add_argument("--max-conductance", type=float, default=128e-6, help="upper end of dyn range")
parser.add_argument("--max-attempts", type=float, default=25, help="max programming attempts")
parser.add_argument("--start-addr", type=int, default=0, help="start address")
parser.add_argument("--end-addr", type=int, default=65536, help="end address")
parser.add_argument("--step-addr", type=int, default=1, help="address stride")
parser.add_argument("--use-settings-ranges", action="store_true", help="use ranges in json file")
args = parser.parse_args()

# Initialize NI system
nisys = NIRRAM(args.chipname)

# Define conductances
CONDS = np.linspace(args.min_conductance, args.max_conductance, args.num_levels + 1)
CONDS[0] += 1e-12 # to prevent divide by 0 error
print(CONDS)

# Read file
if args.retention_outfile is not None:
    readfile = open(args.retention_outfile, "w")

# Do operation across cells
for i, addr in enumerate(range(args.start_addr, args.end_addr, args.step_addr)):
    nisys.set_addr(addr)
    print(addr)
    glo, ghi = (CONDS[i % args.num_levels], CONDS[i % args.num_levels + 1]) if 
    nisys.target_g(glo, ghi, max_attempts=args.max_attempts, debug=False)
    if args.retention_outfile is not None:
        for j in range(args.ret_reads):
            read = nisys.read()
            readfile.write(f"{addr}\t{time.time()}\t{read[0]}\t{read[1]}\n")

# Read continuously after all cells are programmed
if args.retention_outfile is not None:
    while True:
        try:
            for addr in range(args.start_addr, args.end_addr, args.step_addr):
                nisys.set_addr(addr)
                read = nisys.read()
                readfile.write(f"{addr}\t{time.time()}\t{read[0]}\t{read[1]}\n")
        except KeyboardInterrupt:
            break

# Shutdown
if args.retention_outfile is not None:
    readfile.close()
nisys.close()
