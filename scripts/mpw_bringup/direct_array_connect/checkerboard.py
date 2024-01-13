"""Script to perform a read voltage sweep on a chip"""
import argparse
import numpy as np
from digitalpattern.nirram import NIRRAM
import matplotlib.pyplot as plt
import arbitrary_cells


### CHECKERBOARD
# NOTE: usually entire BL/SL is dead because one shorted cell causes entire
# BL/SL to now have the parallel shorted FET. Fo for testing we can try
# single BL/SL columns that did not short cells
    # 2x2 Example:
    #   1 0     set  reset
    #   0 1    reset  set
def create_checkerboard(nisys, width=1, height=1, odd=1):
    """Create a checkerboard pattern of cells (on odd squares if odd is 1, even squares if odd is 0)."""
    cells = []
    for wl_idx, wl in enumerate(nisys.wls): #WL
        for bl_idx, (bl,sl) in enumerate(zip(nisys.bls, nisys.sls)): #BL
            if (wl_idx + bl_idx) % 2 == odd: # If (WL + BL)%2 = 1  (WL,BL) <- 1
                cells.append((wl,bl,sl)) # Set (WL, BL) if their sum is odd
    return cells

def checkerboard(nisys, width=1, height=1,odd=1):
    cells = create_checkerboard(nisys, width, height, odd)
    # if needed, reset all cells to avoid short paths
    nisys.dynamic_reset()
    arbitrary_cells.arb_cells(nisys, cells, func="SET")

if __name__ == "__main__":
    # Get arguments
    parser = argparse.ArgumentParser(description="RESET a chip.")
    parser.add_argument("chip", help="chip name for logging")
    parser.add_argument("device", help="device name for logging")

    args = parser.parse_args()
    # Initialize NI system
    # For CNFET: make sure polarity is PMOS
    nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_ProbeCard.toml", polarity="NMOS") # FOR CNFET RRAM

    cells = checkerboard(nisys)
    print(cells)