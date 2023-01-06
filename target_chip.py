"""Script to target a chip"""
import argparse
from digitalpattern.nirram import NIRRAM

# Get arguments
parser = argparse.ArgumentParser(description="Target a chip.")
parser.add_argument("chipname", help="chip name for logging")
parser.add_argument("--start-addr", type=int, default=0, help="start address")
parser.add_argument("--end-addr", type=int, default=65536, help="end address")
parser.add_argument("--step-addr", type=int, default=1, help="address stride")
parser.add_argument("--target-low-res", type=int, default=10000, help="target lo resistance")
parser.add_argument("--target-hi-res", type=int, default=11000, help="target hi resistance")
args = parser.parse_args()

# Initialize NI system
nisys = NIRRAM(args.chipname)

# Do operation across cells
for addr in range(args.start_addr, args.end_addr, args.step_addr):
    nisys.set_addr(addr)
    target = nisys.target(args.target_low_res, args.target_hi_res)
    print(f"Address {addr}: {target}")

# Shutdown
nisys.close()
