from ni_rram import NIRRAM
from time import sleep
nisys = NIRRAM("Chip_9")
nisys.set_addr(348)
print(nisys.read())
nisys.set_pulse()
print(nisys.read())
