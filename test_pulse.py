"""Script to perform a read voltage sweep on a chip"""
import argparse
import numpy as np
from nirram import NIRRAM
import matplotlib.pyplot as plt


# Get arguments
parser = argparse.ArgumentParser(description="RESET a chip.")
parser.add_argument("device_no", help="chip name for logging")

args = parser.parse_args()

# Initialize NI system
nisys = NIRRAM(args.device_no,settings="settings/DEC3.json")

print(nisys.read())
#input("Dynamic Form")
#print(nisys.dynamic_form())
for i in range(10000):
    # nisys.set_pulse()
    # print(nisys.read())
    # nisys.reset_pulse()
    #print(nisys.read())
    print(nisys.dynamic_reset())
    print(nisys.dynamic_set())

# print(nisys.read())
# #input("Reset")
# nisys.dynamic_reset()
# print(nisys.read())
nisys.close()
