"""Script to perform a read voltage sweep on a chip"""
import argparse
import numpy as np
from digitalpattern.nirram import NIRRAM
import matplotlib.pyplot as plt
import arbitrary_cells
import pdb
import itertools
import datetime
import csv
# Get arguments
parser = argparse.ArgumentParser(description="RESET a chip.")
parser.add_argument("chip", help="chip name for logging")
parser.add_argument("device", help="device name for logging")

# args = parser.parse_args()
# # Initialize NI system
# # For CNFET: make sure polarity is PMOS
# nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_ProbeCard.toml", polarity="PMOS") # FOR CNFET RRAM


#read_aray = arbitrary_cells.arb_cells(nisys, cells, funcs=actions)

#check for shorts
def check_for_shorts(res_array, cell, threshold=50e3):
    """Check for shorts in the array. If there are shorts, the resistance will
be low. The threshold is set to 50kOhm by default, but can be changed."""
    shorts_array = res_array < threshold
    # shorts_array = res_array < threshold
    if np.any(shorts_array):
        print(f"short detected at {cell[0:2]}")
    return shorts_array

# shorted_array = check_for_shorts(res_array)
#switch relays
# nisys.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RESET a chip.")
    parser.add_argument("chip", help="chip name for logging")
    parser.add_argument("device", help="device name for logging")
    args = parser.parse_args()

    nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_ProbeCard.toml", polarity="PMOS") # FOR CNFET RRAM
    if nisys.polarity == "NMOS":
        MOS = "Si"
    else:
        MOS = "CNT"
        
    wls = []
    cells = []
    wl_s = nisys.settings["device"]["wl_signals"]
    for wl in wl_s:
        for num in wl[1]:
            wls.append("WL_" + num)
    for wl in wls:
        for bl in nisys.all_bls:
            cells.append((wl,bl,"SL_"+bl.split("_")[1]))
    print(cells)
    
    actions = ["READ"]*len(cells)
    shorts_array = []
    for cell,action in zip(cells,actions):
        read_array = arbitrary_cells.arb_cells(nisys, [cell], funcs=[action])
        print(read_array)
        shorts_array.append((cell,"Short" if check_for_shorts(np.array(read_array),cell)[0] else "No Short"))

    unique_wl = sorted(set(item[0][0] for item in shorts_array))
    unique_bl = sorted(set(item[0][1] for item in shorts_array))
    n = len(unique_wl)

    # Create an empty array
    array = np.empty((n, n), dtype=object)

    # Fill the array with "Short" or "No_Short" based on the last tuple entry
    for item in shorts_array:
        wl, bl, sl = item[0]
        status = item[1]
        row_idx = unique_wl.index(wl)
        col_idx = unique_bl.index(bl)
        array[row_idx, col_idx] = status
    shorts_array = array

    print(shorts_array)

    now = datetime.datetime.now()
    csv_filename = f"D:/nirram/data/MPW_Test/Shorts_Check_{now.strftime('%Y-%m-%d_%H-%M-%S')}_{MOS}.csv"

    # Create a CSV file and write the shorts_array to it
    with open(csv_filename, mode='w', newline='') as csv_file:
        writer = csv.writer(csv_file)

        # Write the header row with BL labels
        writer.writerow(["WL/BL"] + unique_bl)

        # Write the data rows with WL labels and shorts_array values
        for wl, row in zip(unique_wl, shorts_array):
            writer.writerow([wl] + list(row))

    print(f"Shorts check results saved to: {csv_filename}")

    nisys.close()
    quit()