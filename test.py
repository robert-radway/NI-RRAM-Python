"""Testing file"""
import numpy as np
from nirram import NIRRAM

# Initialize NI system
nisys = NIRRAM("Chip_9")

# Address range
ADDR_LO = 0
ADDR_HI = 65536
ADDR_STEP = 1

# Define conductances
CONDS = np.arange(0, 129e-6, 4e-6)
CONDS[0] = 1e-9
print(CONDS)

# Define the operation
def operation(i):
    # print("TARGET G:", CONDS[i % 32], CONDS[i % 32 + 1])
    # print("TARGET R:", 1/CONDS[i % 32 + 1], 1/CONDS[i % 32])
    # return nisys.target_g(CONDS[i % 32], CONDS[i % 32 + 1])
    return nisys.dynamic_form()

# Do operation across cells
for i, addr in enumerate(range(ADDR_LO, ADDR_HI, ADDR_STEP)):
    nisys.set_addr(addr)
    print(operation(i))

# Shutdown
nisys.close()
