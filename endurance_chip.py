"""Script to sweep test endurance of a chip"""
import argparse
from digitalpattern import NIRRAM

# Get arguments
parser = argparse.ArgumentParser(description="Endurance cycle a chip.")
parser.add_argument("chipname", help="chip name for logging")
parser.add_argument("outfile", help="file to output to")
parser.add_argument("--cycles", type=int, default=1e10, help="number of cycles to perform")
parser.add_argument("--read-cycles", type=int, default=5e4, help="number of cycles to read after")
parser.add_argument("--start-addr", type=int, default=0, help="start address")
parser.add_argument("--end-addr", type=int, default=1, help="end address")
parser.add_argument("--step-addr", type=int, default=1, help="address stride")
parser.add_argument("--no-print", action="store_true", help="do not print anything")
args = parser.parse_args()

# Open outfile
outfile = open(args.outfile, "a")

# Initialize NI system
nisys = NIRRAM(args.chipname)

# Do operation across cells
for addr in range(args.start_addr, args.end_addr, args.step_addr):
    print(addr)
    nisys.set_addr(addr)

    # for i in range(int(args.cycles)):
    #     nisys.set_pulse()
    #     if i % args.read_cycles == args.read_cycles - 1:
    #         read = nisys.read()
    #         outfile.write(f"{addr}\t{read[0]}\t{i}\n")
    #         print(f"{addr}\t{read[0]}\t{i}\n")
    #     nisys.reset_pulse()
    #     if i % args.read_cycles == args.read_cycles - 1:
    #         read = nisys.read()
    #         outfile.write(f"{addr}\t{read[0]}\t{i}\n")
    #         print(f"{addr}\t{read[0]}\t{i}\n")

    nisys.endurance(read_cycs=args.read_cycles, cycs=args.cycles)

# Shutdown
outfile.close()
nisys.close()
