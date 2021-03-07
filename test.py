"""Testing file"""
from nirram import NIRRAM

nisys = NIRRAM("Chip_9")
for i in range(500, 510):
    print(nisys.target(10000*i + 10000, 10000*i + 20000))
