"""Script to perform a read voltage sweep on a chip"""
import argparse
import numpy as np
from digitalpattern.nirram import NIRRAM
import matplotlib.pyplot as plt


r1 = 9_090
r2 = 11_110
r3 = 12_500
r4 = 14_280
r5 = 16_600
r6 = 20_000
r7 = 25_000
r8 = 33_300
r9 = 50_000
r10 = 100_000
r11 = 500_000

def multibit_set(nisys,lower_target_res,upper_target_res,repeats,name_run):
    for i in range(repeats):
        post_set_data=nisys.dynamic_set(mode="SET",target_res=upper_target_res)
        print(f"Resistance after SET {name_run}: {post_set_data[0][5]}")
        post_reset_data=nisys.dynamic_reset(mode="RESET",target_res=lower_target_res)
        print(f"Resistance after RESET {name_run}: {post_reset_data[0][5]}")
    return (post_reset_data[0][5]>lower_target_res) and (post_reset_data[0][5]<upper_target_res)


# Get arguments
parser = argparse.ArgumentParser(description="RESET a chip.")
parser.add_argument("chip", help="chip name for logging")
parser.add_argument("device", help="device name for logging")

args = parser.parse_args()

# Initialize NI system
nisys = NIRRAM(args.chip, args.device, settings="settings/MPW.toml", polarity="PMOS") # FOR CNFET RRAM
# nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_silicon.json", polarity="NMOS") # FOR Si NMOS RRAM

nisys.read(record=True)
# input("Dynamic Form")
# nisys.dynamic_form()

for i in range(30000):
    
    # multibit_set(nisys,r1,r2,10)
    # multibit_set(nisys,r2,r3,10)
    # multibit_set(nisys,r3,r4,10)
    # multibit_set(nisys,r4,r5,10)
    # multibit_set(nisys,r5,r6,10)
    multibit_set(nisys,r6,r7,3,1)
    multibit_set(nisys,r7,r8,3,2)
    multibit_set(nisys,r8,r9,3,3)
    multibit_set(nisys,r9,r10,3,4)
    multibit_set(nisys,r9,r11,3,5)

    # nisys.dynamic_reset(mode="RESET")
    # nisys.dynamic_set(mode="SET_0") # increasing soft reset levels, comment out as needed
    # nisys.dynamic_reset(mode="RESET")
    # nisys.dynamic_set(mode="SET_1")
    # nisys.dynamic_reset(mode="RESET")
    # nisys.dynamic_set(mode="SET_2")
    # nisys.dynamic_reset(mode="RESET")
    # nisys.dynamic_set(mode="SET_3")
    # nisys.dynamic_reset(mode="RESET")
    # nisys.dynamic_set(mode="SET_4") # increasing soft reset levels, comment out as needed
    # nisys.dynamic_reset(mode="RESET")
    # nisys.dynamic_set(mode="SET_5")
    # nisys.dynamic_reset(mode="RESET")
    # nisys.dynamic_set(mode="SET_6")
    # nisys.dynamic_reset(mode="RESET")
    # nisys.dynamic_set(mode="SET_7")
    # nisys.dynamic_reset(mode="RESET")
    # nisys.dynamic_set(mode="SET_8") # increasing soft reset levels, comment out as needed
    # nisys.dynamic_reset(mode="RESET")
    # nisys.dynamic_set(mode="SET_9")
    # nisys.dynamic_reset(mode="RESET")
    # nisys.dynamic_set(mode="SET_10")
    # nisys.dynamic_reset(mode="RESET")
    # nisys.dynamic_set(mode="SET_11")
    #  nisys.dynamic_set(mode="SET")
    # nisys.dynamic_reset(mode="RESET_0") # increasing soft reset levels, comment out as needed
    # nisys.dynamic_set(mode="SET")
    # nisys.dynamic_reset(mode="RESET_1")
    # nisys.dynamic_set(mode="SET")
    # nisys.dynamic_reset(mode="RESET_2")
    
    # nisys.dynamic_reset(mode="RESET_3")

    # IF YOU HAVE ENOUGH WINDOW, CAN TRY WITH MORE LEVELS!
    # nisys.dynamic_reset(mode="RESET_4")
    # nisys.dynamic_reset(mode="RESET_5")
    # nisys.dynamic_reset(mode="RESET_6")
    # nisys.dynamic_reset(mode="RESET_7")
nisys.close()

# for autoprobing cnfet, addd polarity = pmos
