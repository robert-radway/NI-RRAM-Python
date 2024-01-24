from relay_switch import relay_switch
import argparse
from digitalpattern.nirram import NIRRAM
from time import sleep
import numpy as np
from checkerboard import checkerboard
import pdb
import probecard_transistor_iv

res = reset = Reset = RESET = "RESET"
Set = SET = "SET"
nn = none = NONE = "NONE"
rea = read = Read = READ = "READ"
fo = form = Form = FORM = "FORM"
Dynread = dynread = DYNREAD = "DYNREAD"
checker = Checkerbord = CHECKERBOARD = "CHECKERBOARD"
invcheck = inverse__checkerboard = inverse_checkerboard = INVERSE_CHECKERBOARD = "INVERSE_CHECKERBOARD"
all_wls = ALL_WLS = [0,2,4,6,8,10,12,14,39,41,43,45,37,47,49,53,35,51,55,57,59,61,63,65,66,69,62,60,56,54,52,58,48,34,77,79]



def operation_setup(nisys, cells, operations):
    """
    operation_setup: A function designed to take keywords and generate a pattern of cells for given functions
    Current kewords are: CHECKERBOARD,  INVERSE_CHECKERBOARD which generate a checkerboard pattern of cells
    """
    
    # Check for checkerboard
    if CHECKERBOARD in operations or INVERSE_CHECKERBOARD in operations:
        rows = set([tpl[0] for tpl in cells])
        cols = set([tpl[1] for tpl in cells])
        height = len(set(rows))
        width = len(set(cols))

    # Get number of cells operated on
    num_cells = len(cells)

    #Repeat cells for number of operations and operations for number of cells
    cells = cells * len(operations)
    func_raw = [operation for operation in operations for _ in range(num_cells)]   
    func = []
    #Check for and replace checkerboard
    
    # Create a generator expression to iterate over the original list
    gen_expr = (
        checkerboard(width=width, height=height,odd=0) if func_raw[i:i+num_cells] == [CHECKERBOARD] * num_cells else [func_raw[i]]
        for i in range(len(func_raw))
    )

    func_raw = [item for sublist in gen_expr for item in sublist]
    func_raw = [element for element in func_raw if element != CHECKERBOARD]
    gen_expr = (
        checkerboard(width=width, height=height,odd=1) if func_raw[i:i+num_cells] == [INVERSE_CHECKERBOARD] * num_cells else [func_raw[i]]
        for i in range(len(func_raw))    
    )

    # Use list comprehension to flatten the generator expression into a list
    func = [item for sublist in gen_expr for item in sublist]  
    func = [element for element in func if element != INVERSE_CHECKERBOARD]
    return cells, func

def reset_bl(nisys, bl):
    """
    reset_bl: A function to reset the entirety of a bitline given a bitline name. Works for all defined wordlines.
    This function takes in a NIRRAM object, and a bitline name (e.g. "BL_0") and returns a list of the resistance 
    values of the cells in that bitline.
    """
    cells = []
    # ALL_WLS = [0,2,4,6,8,10,12,14,39,41,43,45,37,47,49,53,35,51,55,57,59,61,63,65,66,69,62,60,56,54,52,58,48,34,77,79]
    ALL_WLS = [0,2,4,6,8,10,12,14,39,41,43,45,47,49,53,35,51,55,57,59,61,63,65,66,69,62,60,56,54,52,58,48,34,77,79]
    for wl in ALL_WLS:
        cells = cells + [("WL_"+str(wl),f"BL_{bl}")]
    operations = [RESET]*2
    cells,func = operation_setup(nisys, cells, operations)
    read_array = arb_cells(nisys, cells, funcs=func)
    return read_array

    
def read_bl(nisys, bl):
    """
    read_bl: A function to read the entirety of a bitline given a bitline name. Works for all defined wordlines.
    This function takes in a NIRRAM object, and a bitline name (e.g. "BL_0") and returns a list of the resistance 
    values of the cells in that bitline.

    TODO: Make this work for all wordlines.
    """
    cells = []
    ALL_WLS = [0,2,4,6,8,10,12,14,39,41,43,45,37,47,49,53,35,51,55,57,59,61,63,65,66,69,62,60,56,54,52,58,48,34,77,79]
    # ALL_WLS = [0,2,4,6,8,10,12,14,39,41,43,45,47,49,53,35,51,55,57,59,61,63,65,66,69,62,60,56,54,52,58,48,34,77,79]
    for wl in ALL_WLS:
        cells = cells + [("WL_"+str(wl),f"BL_{bl}")]
    operations = [READ]
    cells,func = operation_setup(nisys, cells, operations)
    read_array = arb_cells(nisys, cells, funcs=func)
    print_cells(dict(zip(cells, read_array)))
    return read_array

def arb_cells(nisys, cells, funcs=["SET"]):
    cellsave = [("WL_999", "BL_0")]
    read_array = []

    # Decrease relay switching by only switching when wl changes
    # Check if need to switch relays
    for cell, func in zip(cells, funcs):
        if cell != cellsave and cell[0] != cellsave[0]:
            cellsave = cell
            wl_name = cell[0]
            wl, bl, sl = relay_switch(cell[0], cell[1], "SL"+cell[1][2:], nisys)

        #Check if it needs to switch bl and sl
        elif cell[0] == cellsave[0] and cell[1] != cellsave[1]:
            cellsave = cell
            bl = cell[1]
            sl = "SL"+cell[1][2:]

        #cells is a list of tuples (wl, bl, sl)
        #save original wls, bls, sls
        wls, bls, sls = (nisys.wls, nisys.bls, nisys.sls)

        #Set the correct realy to NO-COM, get signals for wl, bl, sl
        nisys.wls = [wl]
        nisys.bls = [bl]
        nisys.sls = [sl]

        #print(f"wl: {wl}, bl: {bl}, sl: {sl}")
        if func == "SET":
            result = nisys.dynamic_set(relayed=True)
        elif func == "FORM":
            result = nisys.dynamic_form(relayed=True)
        elif func == "RESET":
            result = nisys.dynamic_reset()
        elif func == "READ":
            res_array, cond_array, meas_i_array, meas_v_array = nisys.read(record=True, wl_name = wl_name)
            read_array.append(res_array.loc[wl,bl])
        elif func == "DYNREAD":
            vwls = np.linspace(-2,4,25)
            nisys.dynamic_read(vwls = vwls, record=True, wl_name = wl_name)
        elif func == "NONE":
            pass
        else:
            raise ValueError(f"Invalid function {func}")
        #restore original wls, bls, sls
        nisys.wls, nisys.bls, nisys.sls = wls, bls, sls
    if func == "READ":
        print("Cell states:")
        print_cells(dict(zip(cells, read_array)))
    return read_array

def print_cells(read_dict):
    sorted_dict = sorted(read_dict.items(), key=lambda x: x[1], reverse=True)
    for cell, r in sorted_dict:
        print(f"{cell}: {r/1e3:.3f} kohms")

if __name__ == "__main__":
    # Get arguments
    parser = argparse.ArgumentParser(description="RESET a chip.")
    parser.add_argument("chip", help="chip name for logging")
    parser.add_argument("device", help="device name for logging")
    
    args = parser.parse_args()
    # Initialize NI system
    # For CNFET: make sure polarity is 
    nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_ProbeCard.toml", polarity="PMOS",slow=False) # FOR CNET + RRAM

    
    # Read all cells in a single bitline
    # read_bl(nisys, 8)
# "BL_8", ["WL_2","WL_6","WL_10"]
# []
    cells = []
    bl_idxs = [11]
    wl_idxs = [0,8,41,37]
    # wl_idxs = [10]

    for wl_idx in wl_idxs:
        for bl_idx in bl_idxs:
            cells.append((f"WL_{wl_idx}", f"BL_{bl_idx}"))
    
    operations =[RESET,INVERSE_CHECKERBOARD,READ]
    cells, func = operation_setup(nisys, cells, operations)

    # print(cells,func)
    read_array = arb_cells(nisys, cells, funcs=func)
    
    # for Bitline in [11]:
    #     print(f"BL_{Bitline}")
    #     read_bl(nisys, Bitline)
    #     print(" ")

    nisys.close()

    # probecard_transistor_iv.run_iv_curve()