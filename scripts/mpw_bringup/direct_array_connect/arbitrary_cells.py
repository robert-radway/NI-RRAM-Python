from relay_switch import relay_switch
import argparse
from digitalpattern.nirram import NIRRAM
from time import sleep
import numpy as np

RESET = "RESET"
SET = "SET"
NONE = "NONE"
READ = "READ"
FORM = "FORM"
DYNREAD = "DYNREAD"
def arb_cells(nisys, cells, funcs=["SET"]):

    for cell, func in zip(cells, funcs):
        #cells is a list of tuples (wl, bl, sl)
        #save original wls, bls, sls
        wls, bls, sls = (nisys.wls, nisys.bls, nisys.sls)
        read_array = []
        #Set the correct realy to NO-COM, get signals for wl, bl, sl
        wl, bl, sl = relay_switch(cell[0], cell[1], "SL"+cell[1][2:], nisys)
        nisys.wls = [wl]
        nisys.bls = [bl]
        nisys.sls = [sl]
        print(f"wl: {wl}, bl: {bl}, sl: {sl}")
        if func == "SET":
            result = nisys.dynamic_set()
        if func == "FORM":
            result = nisys.dynamic_form(relayed=True)
        elif func == "RESET":
            result = nisys.dynamic_reset()
        elif func == "READ":
            res_array, cond_array, meas_i_array, meas_v_array = nisys.read(record=True)
            read_array.append(res_array.loc[wl,bl])
        elif func == "DYNREAD":
            #vwls = np.linspace(-2,4,50)
            nisys.dynamic_read(record=True)
        elif func == "NONE":
            pass
        else:
            raise ValueError(f"Invalid function {func}")
        if func =="SET" or func == "RESET" and not result[0][-1]:
            print(f"Failed to {func} cell at ({wl},{bl},{sl})")
        #restore original wls, bls, sls
        nisys.wls, nisys.bls, nisys.sls = wls, bls, sls
    return read_array
if __name__ == "__main__":
    # Get arguments
    parser = argparse.ArgumentParser(description="RESET a chip.")
    parser.add_argument("chip", help="chip name for logging")
    parser.add_argument("device", help="device name for logging")

    args = parser.parse_args()
    # Initialize NI system
    # For CNFET: make sure polarity is 
    nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_ProbeCard.toml", polarity="NMOS",slow=False) # FOR CNET + RRAM
    cells = [("WL_45", "BL_12"),("WL_2", "BL_10"), ("WL_12", "BL_10"),("WL_43", "BL_10"),("WL_45", "BL_10")]
    cells = cells + [("WL_45", "BL_12")] + cells
    # cells = cells+cells+cells
    # cells = cells+cells
    #Single Cell Stress Test
    # WL = "WL_9"
    # BL = "BL_10"
    #cells = [(WL, BL),(WL,BL),(WL,BL),(WL, BL),(WL,BL),(WL,BL),(WL, BL),(WL,BL),(WL,BL),(WL, BL),(WL,BL)]
    #cells = [("WL_9", "BL_10"),("WL_9", "BL_10"),("WL_9", "BL_10"),("WL_9", "BL_10"),("WL_9", "BL_10"),("WL_9", "BL_10"),("WL_9", "BL_10"),("WL_9", "BL_10")]

    # cells = cells + cells
    # arb_cells(nisys, cells, funcs=[READ, READ, READ, READ, READ,READ,READ,READ,READ,READ, READ, READ, READ, READ,READ,READ,READ,READ,READ, READ, READ, READ, READ,READ,READ,READ,READ,READ, READ, READ, READ, READ,READ,READ,READ,READ])
    # arb_cells(nisys, cells, funcs=[READ,
    #  READ, READ, READ, READ,READ,READ,READ,READ,READ, READ, READ, READ, READ,READ,READ,READ,READ])
    # arb_cells(nisys, cells, funcs=[FORM])

    # arb_cells(nisys, cells, funcs=[READ, READ, READ, READ, RESET,RESET,RESET,RESET,READ,READ,READ,READ])

    arb_cells(nisys, cells, funcs=[FORM, READ, READ, READ, READ, RESET,READ,READ,READ,READ])
    # arb_cells(nisys, cells, funcs=[READ])#, READ, READ, READ, READ,READ,READ,READ,READ])
    nisys.close()