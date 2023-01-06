"""Script to FORM a chip"""
import argparse
from digitalpattern.nirram import NIRRAM

# Get arguments
parser = argparse.ArgumentParser(description="FORM a chip.")
parser.add_argument("chipname", help="chip name for logging")
parser.add_argument("--outfile", type=str, default=None, help="file to output to")
parser.add_argument("--start-addr", type=int, default=0, help="start address")
parser.add_argument("--end-addr", type=int, default=65536, help="end address")
parser.add_argument("--step-addr", type=int, default=1, help="address stride")
args = parser.parse_args()

# Open outfile
if args.outfile is not None:
    outfile = open(args.outfile, "a")

# Initialize NI system
nisys = NIRRAM(args.chipname)

# Do operation across cells
for addr in range(args.start_addr, args.end_addr, args.step_addr):
    nisys.set_addr(addr)
    form = nisys.dynamic_form()
    if addr % 10 == 0:
        print(f"Address {addr}: {form}")
    if args.outfile is not None:
        tab = '\t'
        outfile.write(f"{addr}\t{tab.join(list(map(str, form)))}\n")
        
# Close outfile
if args.outfile is not None:
    outfile.close()

# Shutdown
nisys.close()
