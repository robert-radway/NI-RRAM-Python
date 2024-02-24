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
check = checker = Checkerbord = CHECKERBOARD = CHECK = "CHECKERBOARD"
invcheck = inverse__checkerboard = inverse_checkerboard = INVCHECK = INVERSE_CHECKERBOARD = "INVERSE_CHECKERBOARD"

awls = all_wls = ALL_WLS = [0,2,4,6,8,10,12,14,39,41,43,45,37,47,49,53,35,51,55,57,59,61,63,65,66,69,62,60,56,54,52,58,48,34,77,79]
abls = all_bls = ALL_BLS = [8,9,10,11,12,13,14,15]


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

    #Repeat cells for number of operations you want to do
    cells = cells * len(operations)

    # Repeat function for every cell in the cells list
    func_raw = [operation for operation in operations for _ in range(num_cells)]   
    func = []
    
    
    # Create a generator expression to iterate over the original list checking for checkerboard
    gen_expr = (
        checkerboard(width=width, height=height,odd=0) if func_raw[i:i+num_cells] == [CHECKERBOARD] * num_cells else [func_raw[i]]
        for i in range(len(func_raw))
    )

    func_raw = [item for sublist in gen_expr for item in sublist]
    func_raw = [element for element in func_raw if element != CHECKERBOARD]
    
    # Create a generator expression to iterate over the modified list checking for inverse checkerboard
    gen_expr = (
        checkerboard(width=width, height=height,odd=1) if func_raw[i:i+num_cells] == [INVERSE_CHECKERBOARD] * num_cells else [func_raw[i]]
        for i in range(len(func_raw))    
    )

    # Use list comprehension to flatten the generator expression into a list
    func = [item for sublist in gen_expr for item in sublist]  
    func = [element for element in func if element != INVERSE_CHECKERBOARD]
    
    # Return the cells and functions lists
    return cells, func

def bl_operation(nisys, bl, operations):
    ALL_WLS = [0,2,4,6,8,10,12,14,39,41,43,45,37,47,49,53,35,51,55,57,59,61,63,65,66,69,62,60,56,54,52,58,48,34,77,79]
    cells = []
    for wl in ALL_WLS:
        cells = cells + [("WL_"+str(wl),f"BL_{bl}")]
    cells,func = operation_setup(nisys, cells, operations)
    read_array = arb_cells(nisys, cells, funcs=func)
    return read_array

def reset_bl(nisys, bl):
    """
    reset_bl: A function to reset the entirety of a bitline given a bitline number (int). Works for all defined wordlines.
    This function takes in a NIRRAM object, and a bitline name (e.g. "BL_0") and returns a list of the resistance 
    values of the cells in that bitline.
    """
    operations = [RESET]
    read_array = bl_operation(nisys, bl, operations)
    return read_array

def read_bl(nisys, bl):
    """
    read_bl: A function to read the entirety of a bitline given a bitline name. Works for all defined wordlines.
    This function takes in a NIRRAM object, and a bitline name (e.g. "BL_0") and returns a list of the resistance 
    values of the cells in that bitline.
    """
    operations = [READ]
    read_array = bl_operation(nisys, bl, operations)
    return read_array

def set_bl(nisys, bl): 
    """
    set_bl: A function to set the entirety of a bitline given a bitline name. Works for all defined wordlines.
    This function takes in a NIRRAM object, and a bitline name (e.g. "BL_0") and returns a list of the resistance 
    values of the cells in that bitline.
    """
    operations = [SET]
    read_array = bl_operation(nisys, bl, operations)
    return read_array

def read_bls(nisys, bls):

    """
    read_bls: A function to read the entirety of a list of bitlines given a bitline name. 
    Works for all defined wordlines/bitlines
    """

    if isinstance(bls,int):
        bls = [bls]
    for bl in bls:
        print(f"BL_{bl}")
        read_array = read_bl(nisys, bl)
        print(" ")
    return read_array

def read_die(nisys):
    ALL_BLS = [8,9,10,11,12,13,14,15]
    read_array = read_bls(nisys, ALL_BLS)
    return read_array  


def arb_cells(nisys, cells, funcs,vwl_range=np.linspace(-2,4,25)):
    cellsave = [("WL_999", "BL_0")]
    read_array = []

    # Decrease relay switching by only switching when wl changes
    # Check if need to switch relays
    for cell, func in zip(cells, funcs):
        wl_name = cell[0]
        if cell != cellsave and cell[0] != cellsave[0]:
            cellsave = cell
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

        #Perform the function
        if func == "SET":
            result = nisys.dynamic_set(relayed=True)

        elif func == "FORM":
            result = nisys.dynamic_form(relayed=True)
        
        elif func == "RESET":
            result = nisys.dynamic_reset()
        
        elif func == "READ":
            res_array, cond_array, meas_i_array, meas_v_array = nisys.read(record=True, wl_name = wl_name)
            if not(bl in ["BL_MULTI_READ"]):
                read_array.append(res_array.loc[wl,bl])
            else:
                for res in res_array:
                    read_array.append(res)
        
        elif func == "DYNREAD":
            nisys.dynamic_read(vwls = vwl_range, record=True, wl_name = wl_name)
        
        elif func == "MULTI_BL_READ":
            nisys.multi_bl_read(record=True, wl_name = wl_name,wl=wl)
        elif func == "NONE":
            pass
        
        else:
            raise ValueError(f"Invalid function {func}")
        
        #restore original wls, bls, sls
        nisys.wls, nisys.bls, nisys.sls = wls, bls, sls
    # if func == "READ":
        # if not(cond_array is None):
            # print("Cell states:")
            # print_cells(dict(zip(cells, read_array)))
    
    return read_array



def print_cells(read_dict):
    sorted_dict = sorted(read_dict.items(), key=lambda x: x[1], reverse=True)
    for cell, r in sorted_dict:
        print(f"{cell}: {r/1e3:.3f} kohms")


if __name__ == "__main__":
    
    cells = None
    # Get arguments
    parser = argparse.ArgumentParser(description="RESET a chip.")
    parser.add_argument("chip", help="chip name for logging")
    parser.add_argument("device", help="device name for logging")
    args = parser.parse_args()
    polarity = "PMOS"
    # Initialize NI system
    # For CNFET: make sure polarity is 
    nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_ProbeCard.toml", polarity=polarity,slow=False)
    nisys.digital.channels["WL_UNSEL"].ppmu_current_limit_range = 2e-6

    bl_sl_idxs = range(8,16)
    nisys.bls = [f"BL_{i}" for i in bl_sl_idxs]
    nisys.sls = [f"SL_{i}" for i in bl_sl_idxs]
    wl = "WL_0"
    wl_signal_name = relay_switch(wl=wl, bl=nisys.bls[0], sl=nisys.bls[0], nisys=nisys)[0]
    nisys.wls = [wl_signal_name]
#
    nisys.multi_set(vbl=2, vsl=-0.5, vwl=-1.5, pw=1000)

    """
    cells = []
    bl_idxs = [8,9,10,11]
    wl_idxs = [0]
    operations =[READ]
    for wl_idx in wl_idxs:
        for bl_idx in bl_idxs:
            cells.append((f"WL_{wl_idx}", f"BL_{bl_idx}"))    
    cells, func = operation_setup(nisys, cells, operations)

    read_array = arb_cells(nisys, cells, funcs=func)
    """
    
    
    # # # reset_bl(nisys,10)
    # operations =[READ]
    # # cells = [("WL_2", "BL_14")]
    # # cells=[('WL_2',"BL_MULTI_READ")]
    
    # cells = []
    # wl_idxs = ALL_WLS
    # for wl_idx in wl_idxs:
    #     cells.append((f"WL_{wl_idx}", f"BL_MULTI_READ"))    
    # cells, func = operation_setup(nisys, cells, operations)



    # if cells is not None:
    #     if cells[0][1] == "BL_MULTI_READ":
    #         assert(polarity == "PMOS"), "BL_MULTI_READ only works for PMOS"
    #         assert FORM not in operations, "BL_MULTI_READ does not support FORM"
    #         cells, func = operation_setup(nisys, cells, operations)
    #         print("---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------")
    #         read_array=arb_cells(nisys, cells, funcs=func)
    #         print("---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------")
        
    #     else:
    #         cells, func = operation_setup(nisys, cells, operations)
    #         read_array = arb_cells(nisys, cells, funcs=func)
    # # read_bl(nisys,8)
    # # read_die(nisys)

    nisys.close()

