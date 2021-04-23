"""Script to RESET a chip"""
import argparse
from nirram import NIRRAM

# Get arguments
parser = argparse.ArgumentParser(description="RESET a chip.")
parser.add_argument("chipname", help="chip name for logging")
parser.add_argument("--start-addr", type=int, default=0, help="start address")
parser.add_argument("--end-addr", type=int, default=65536, help="end address")
parser.add_argument("--step-addr", type=int, default=1, help="address stride")
parser.add_argument("--target-res", type=int, default=86666.666, help="target resistance")
args = parser.parse_args()

# Initialize NI system
nisys = NIRRAM(args.chipname)
nisys.settings["PINGPONG"]["VWL_RESET_START"] = 3

# Do operation across cells
for addr in range(args.start_addr, args.end_addr, args.step_addr):
    nisys.set_addr(addr)
    reset = nisys.dynamic_reset(args.target_res)
    print(f"Address {addr}: {reset}")

# Shutdown
nisys.close()
