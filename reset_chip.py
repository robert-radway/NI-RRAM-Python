"""Script to RESET a chip"""
import argparse
from digitalpattern.nirram import NIRRAM

# Get arguments
parser = argparse.ArgumentParser(description="RESET a chip.")
parser.add_argument("device_no", help="chip name for logging")
parser.add_argument("--start-vds", type=int, default=0, help="start vds")
parser.add_argument("--end-vds", type=int, default=1.8, help="end vds")
parser.add_argument("--step-vds", type=int, default=0.1, help="address vds")
parser.add_argument("--start-vgs", type=int, default=0, help="start vgs")
parser.add_argument("--end-vgs", type=int, default=1.8, help="end vgs")
parser.add_argument("--step-vgs", type=int, default=0.1, help="address vgs")
args = parser.parse_args()

# Initialize NI system
nisys = NIRRAM(args.chipname)

results = []
# Do operation across cells
for vds in range(args.start_vds, args.end_vds, args.step_vds):
    for vgs in range(args.start_vds, args.end_vds, args.step_vds):
        # 0 --> Body
        # 1 --> Source
        # 2 --> Drain
        # 3 --> Gate
        nisys.set_ppmu({"3": vgs, "1":vds, "2":0, "0":0})
        nisys.read_ppmu([0,1,2,3])

# Shutdown
nisys.close()
