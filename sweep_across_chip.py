"""Script to perform a sweep across a chip"""
import argparse
import itertools
import numpy as np
from nirram import NIRRAM

# Default arguments
PWS = [20e-9, 40e-9, 100e-9, 200e-9, 400e-9, 1e-6, 2e-6] # 7
VWLS = np.arange(0.5, 3.5, 0.1) # 30
VBSLS = np.arange(0.5, 3.5, 0.5) # 6


# Get arguments
parser = argparse.ArgumentParser(description="Sweep pulse parameters across a chip.")
parser.add_argument("chipname", help="chip name for logging")
parser.add_argument("outfile", help="file to output sweep data to")
parser.add_argument("--start-addr", type=int, default=0, help="start address")
parser.add_argument("--end-addr", type=int, default=65536, help="end address")
parser.add_argument("--step-addr", type=int, default=1, help="address stride")
parser.add_argument("--pw-list", type=float, nargs="+", default=PWS, help="PWs")
parser.add_argument("--vwl-list", type=float, nargs="+", default=VWLS, help="VWLs")
parser.add_argument("--vbsl-list", type=float, nargs="+", default=VBSLS, help="VBLs or VSLs")
parser.add_argument("--no-print", action="store_true", help="do not print anything")
group = parser.add_mutually_exclusive_group()
group.add_argument("--set", action="store_true")
group.add_argument("--reset", action="store_false")
args = parser.parse_args()

# Open outfile
outfile = open(args.outfile, "a")

# Initialize NI system
nisys = NIRRAM(args.chipname)

# Do operation across cells
addrs = range(args.start_addr, args.end_addr, args.step_addr)
params = itertools.cycle(itertools.product(args.pw_list, args.vwl_list, args.vbsl_list))
for addr, (pw, vwl, vbsl) in zip(addrs, params):
    nisys.set_addr(addr)
    preread = nisys.read()
    if args.set:
        nisys.set_pulse(vwl, vbsl, pw)
    else:
        nisys.reset_pulse(vwl, vbsl, pw)
    postread = nisys.read()

    # Record
    outfile.write(f"{addr}\t{pw}\t{vwl}\t{vbsl}\t{preread[0]}\t{postread[0]}\n")
    if not args.no_print:
        print(f"{addr}\t{pw}\t{vwl}\t{vbsl}\t{preread[0]}\t{postread[0]}")

# Shutdown
outfile.close()
nisys.close()
