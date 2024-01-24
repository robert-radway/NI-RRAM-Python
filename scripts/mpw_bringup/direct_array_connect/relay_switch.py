import niswitch
import argparse
import numpy as np, pdb
from digitalpattern.nirram import NIRRAM, RRAMArrayMask
import matplotlib.pyplot as plt
from time import sleep


def relay_switch(wl,bl,sl, nisys,multi_wl=False):
    # Check Position of Program

    try:
        wl_signals = nisys.wl_signals
    except AttributeError:
        print("Define WL Signals in TOML File")
        quit()

    # Check Position of Program

    with niswitch.Session("PXI1Slot4") as session:
        wl_value = wl.split("_")[1]
        for wl_signal in wl_signals:
            if wl_value in wl_signal[1]:
                relay_position = wl_signal[0][wl_signal[1].index(wl_value)]
                wl_return = nisys.all_wls[wl_signals.index(wl_signal)]
                #print(f'connecting WL_{wl_value}')
                session.disconnect_all()
                for relay_set in wl_signal[0]:
                    if relay_set == relay_position:
                        #print(relay_position) # Check it is the right postion
                        #print(f"Connecting COM_{relay_position} to NO_{wl_signal[0][wl_signal[1].index(wl_value)]}")
                        
                        if multi_wl:
                            print("Multi WL Selectd: connecting all relays to NO")

                            # For the entire wordline, connect relays to NO
                            for wl_signal_connection in wl_signal[0]:
                                print(f"Connecting COM_{wl_signal_connection} to NO_{wl_signal_connection}")
                                session.connect(f'com{wl_signal_connection}', f'no{wl_signal_connection}')
                        else:
                            session.connect(f'com{relay_position}', f'no{relay_position}')
                break
            else:
                #print(f"wl_value {wl_value} not in {wl_signal[1]}")
                pass
        return wl_return, bl, sl

if __name__ == "__main__":
            # Check Position of Program

            # Get arguments
            parser = argparse.ArgumentParser(description="RESET a chip.")
            parser.add_argument("chip", help="chip name for logging")
            parser.add_argument("device", help="device name for logging")

            args = parser.parse_args()
            # Initialize NI system
            # For CNFET: make sure polarity is PMOS


            # Open NIRRAM session
            nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_ProbeCard.toml", polarity="PMOS") # FOR CNFET RRAM

            # Check Position of Program
            
            relay_switch("WL_12", "BL_0", "SL_0", nisys = nisys)