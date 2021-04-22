"""Testing file"""
import time
import numpy as np
from nirram import NIRRAM

# Initialize NI system
nisys = NIRRAM("C4")

# Address range
ADDR_LO = 18433
ADDR_HI = 20480
ADDR_STEP = 2

# Define conductances
CONDS = np.arange(0, 129e-6, 4e-6)
CONDS[0] = 1e-9
print(CONDS)

# Read file
# readfile = open("data/readfile.tsv", "w")

# Do operation across cells
for i, addr in enumerate(range(ADDR_LO, ADDR_HI, ADDR_STEP)):
    nisys.set_addr(addr)
    print("TARGET G:", CONDS[i % 32], CONDS[i % 32 + 1])
    print("TARGET R:", 1/CONDS[i % 32 + 1], 1/CONDS[i % 32])
    nisys.target_g(CONDS[i % 32], CONDS[i % 32 + 1], max_attempts=15)
    # for j in range(100):
    #     read = nisys.read()
    #     readfile.write(f"{addr}\t{time.time()}\t{read[0]}\t{read[1]}\n")

# # Read it
# while True:
#     try:
#         for i, addr in enumerate(range(ADDR_LO, ADDR_HI, ADDR_STEP)):
#             nisys.set_addr(addr)
#             read = nisys.read()
#             readfile.write(f"{addr}\t{time.time()}\t{read[0]}\t{read[1]}\n")
#     except KeyboardInterrupt:
#         break

# Shutdown
# readfile.close()
nisys.close()
