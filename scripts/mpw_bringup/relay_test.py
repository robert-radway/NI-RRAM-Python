import niswitch
import argparse
import numpy as np, pdb
from digitalpattern.nirram import NIRRAM, RRAMArrayMask
import matplotlib.pyplot as plt
from time import sleep

# Get arguments
parser = argparse.ArgumentParser(description="RESET a chip.")
parser.add_argument("chip", help="chip name for logging")
parser.add_argument("device", help="device name for logging")

args = parser.parse_args()
# Initialize NI system
# For CNFET: make sure polarity is PMOS
nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_ProbeCard.toml", polarity="PMOS") # FOR CNFET RRAM
mask = RRAMArrayMask(nisys.wls, nisys.bls, nisys.sls, nisys.all_wls, nisys.all_bls, nisys.all_sls, nisys.polarity)




#can do a whole-array read if relays dict contains all 32 entries (and everything is wired/set up in pattern editor)
relays_slot4 = {
    "WL_0_2_4_6": [7,6,5,4],
    "WL_8_10_12_14": [3,2,1,0],
    "WL_39_41_43_45": [14,15,12,13],
    "WL_37_47_49_53": [8,10,11,9],
    "WL_35_51_55_57": [16,17,19,18],
    "WL_59_61_63_65":[21,20,22,23],
    "WL_67_69_71_73":[50,24,52,21],
    "WL_68_70_72_75":[55,56,53,54],
    "WL_1_3_5_7":[57,58,59,60],
}

# relays_slot5 = {
#     "WL_0_2_4_6": [7,6,5,4],
#     "WL_8_10_12_14": [3,2,1,0],
# }

# for device,relays in zip(["PXI1Slot4","PXI1Slot5"],[relays_slot4,relays_slot5]):

# given_wls = ["WL_2", "WL_0", "WL_37", "WL_49"]

# for wl_num in given_wls: 
#     if wl_num [2:] in 
#     relays_slot4



for device,relays in zip(["PXI1Slot4"],[relays_slot4]):
    with niswitch.Session(device) as session:
        for relay_idx in [1]: #for each index in the list of relays. to run a smaller test, use a subset of this list
            #switch relays to correct position
            session.disconnect_all()
            for wl_set in nisys.wls:
                for test_relay_idx, relay_position in enumerate(relays[wl_set]):
                    if test_relay_idx == relay_idx:
                        print(f'connecting WL_{wl_set.split("_")[1:][test_relay_idx]}')
                        session.connect(f'com{relay_position}', f'no{relay_position}')
            #pdb.set_trace()
            sleep(1)
            #performing the read
            nisys.read(record=True)
