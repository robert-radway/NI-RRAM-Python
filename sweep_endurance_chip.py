"""Script to test endurance of a chip"""
import argparse
import itertools
import numpy as np
from digitalpattern.nirram import NIRRAM

PWS = [20e-9, 40e-9, 100e-9, 200e-9, 400e-9, 1e-6] # 6
SET_VWLS = np.arange(1, 3.1, 0.1) # 21

# Get arguments
parser = argparse.ArgumentParser(description="Endurance cycle a chip.")
parser.add_argument("chipname", help="chip name for logging")
parser.add_argument("--cycles", type=int, default=1e7, help="number of cycles to perform")
parser.add_argument("--read-cycles", type=int, default=5e4, help="number of cycles to read after")
parser.add_argument("--start-addr", type=int, default=768, help="start address")
parser.add_argument("--end-addr", type=int, default=1020, help="end address")
parser.add_argument("--step-addr", type=int, default=2, help="address stride")
parser.add_argument("--pw-list", type=float, nargs="+", default=PWS, help="PWs")
parser.add_argument("--set-vwl-list", type=float, nargs="+", default=SET_VWLS, help="SET VWLs")
parser.add_argument("--no-print", action="store_true", help="do not print anything")
args = parser.parse_args()

# Initialize NI system
nisys = NIRRAM(args.chipname)

# Do operation across cells
addrs = range(args.start_addr, args.end_addr, args.step_addr)
params = itertools.cycle(itertools.product(args.pw_list, args.set_vwl_list))
for addr, (pw, vwl_set) in zip(addrs, params):
    nisys.settings["SET"]["VWL"] = vwl_set
    nisys.set_addr(addr)
    nisys.endurance(read_cycs=args.read_cycles, cycs=args.cycles, pulse_width=pw)

# Shutdown
nisys.close()
