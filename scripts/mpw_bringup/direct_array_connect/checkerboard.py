"""Script to perform a read voltage sweep on a chip"""
import argparse
import numpy as np
from digitalpattern.nirram import NIRRAM
import matplotlib.pyplot as plt


### CHECKERBOARD
# NOTE: usually entire BL/SL is dead because one shorted cell causes entire
# BL/SL to now have the parallel shorted FET. Fo for testing we can try
# single BL/SL columns that did not short cells
    # 2x2 Example:
    #   1 0     set  reset
    #   0 1    reset  set

def checkerboard(width=1, height=1,odd=1):
    #Check that the array width and height are greater than 0
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be greater than 0")
    pattern = []
    #Determine pattern based on odd or even input
    if odd:
        for h in range(height):
            for w in range(width):
                if (h + w) % 2 == 0:
                    pattern.append("SET")
                else:
                    pattern.append("RESET")
    else:
        for h in range(height):
            for w in range(width):
                if (h + w) % 2 == 0:
                    pattern.append("RESET")
                else:
                    pattern.append("SET")
    print(pattern)
    return pattern

if __name__ == "__main__":
    # Get arguments
    parser = argparse.ArgumentParser(description="RESET a chip.")
    parser.add_argument("width", help="Give the width of the array")
    parser.add_argument("height", help="Give the height of the array")
    parser.add_argument("odd", help="Give 1 for odd checkerboard, 0 for even checkerboard")
    args = parser.parse_args()

    cells = checkerboard(int(args.width), int(args.height),odd=int(args.odd))
    print(cells)