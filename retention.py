"""Testing file"""
import time
import numpy as np
from nirram import NIRRAM

# Initialize NI system
nisys = NIRRAM("C4")

# Address range
ADDR_LO = 16984
ADDR_HI = ADDR_LO + 1
ADDR_STEP = 1

# Define conductances
RES_RANGE = (10416.666666666666,10167.830132110183)

# Open output file
outfile = open("data/badcellret.csv", "w")

# Do operation across cells
for i, addr in enumerate(range(ADDR_LO, ADDR_HI, ADDR_STEP)):
    nisys.set_addr(addr)
    print(nisys.target(*RES_RANGE, max_attempts=10))
    for j in range(10000):
        outfile.write(f"{addr},{time.time()},{nisys.read()}\n")
        if j % 100 == 0:
            print(j)

# Shutdown
outfile.close()
nisys.close()
