"""Script to perform a read voltage sweep on a chip"""
import argparse
import numpy as np
from digitalpattern.nirram import NIRRAM
import matplotlib.pyplot as plt
import arbitrary_cells

wl = ["WL_2"]
bl = ["BL_8"]
sl = ["SL_8"]

