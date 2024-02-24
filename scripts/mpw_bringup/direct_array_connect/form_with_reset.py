from digitalpattern.nirram import NIRRAM
import argparse
from digitalpattern.mask import RRAMArrayMask
import pdb
import arbitrary_cells
from relay_switch import relay_switch
from time import sleep


ALL_WLS = [0,2,4,6,8,10,12,14,39,41,43,45,37,47,49,53,35,51,55,57,59,61,63,65,66,69,62,60,56,54,52,58,48,34,77,79]

def reset_then_form(nisys, bl, wls, wl_to_set, form_pulse, do_form=True, do_read=True, do_reset=True):
    nisys.ppmu_all_pins_to_zero()
    if do_reset: assert(do_read)
    # assert(not wl_to_set in wls)
    
    #read cells before reset
    cells_to_reset = []
    for wl in wls:
        if wl != wl_to_set:
            cells_to_reset.append((wl, bl))
    cell_to_set = (wl_to_set, bl)
    all_cells = cells_to_reset+[cell_to_set]
    # pdb.set_trace()
    if do_read:
        read_array=arbitrary_cells.arb_cells(nisys, all_cells, funcs=["READ"]*len(all_cells))
        read_dict = dict(zip(all_cells, read_array))
        print("\nINITIAL CELL STATE")
        arbitrary_cells.print_cells(read_dict)
        r_before_form = read_dict[cell_to_set]
    
        #reset all cells below threshold
        if do_reset:
            init_reset(nisys, cells_to_reset, read_dict)
    else:
        r_before_form = 0
# 
    #form cell in wl_to_set
    if do_form:
        wl, bl, sl = relay_switch(wl_to_set, bl, "SL"+bl[2:], nisys)
        nisys.wls = [wl]
        nisys.bls = [bl]
        nisys.sls = [sl]
        mask = RRAMArrayMask(nisys.wls, nisys.bls, nisys.sls, nisys.all_wls, nisys.all_bls, nisys.all_sls, nisys.polarity)
        nisys.set_pulse(mask,vbl=form_pulse['vbl'],vsl=form_pulse['vsl'],vwl=form_pulse['vwl'],pulse_len=int(form_pulse['pw']))
        read_array=arbitrary_cells.arb_cells(nisys, all_cells, funcs=["READ"]*len(all_cells))
        read_dict = dict(zip(all_cells, read_array))
        print("\nAFTER FORM")
        arbitrary_cells.print_cells(read_dict)
        print(f"{cell_to_set} was formed to {read_dict[cell_to_set]/1e3} kOhms")
        r_after_form = read_dict[cell_to_set]
    else:
        r_after_form = r_before_form
    return read_dict, r_before_form, r_after_form


def init_reset(nisys, cells_to_reset, read_dict, threshold = 28e3):
    target_cells = []
    for cell in cells_to_reset:
        if read_dict[cell] < threshold:
            target_cells.append(cell)
    if target_cells:
        arbitrary_cells.arb_cells(nisys, target_cells, funcs=["RESET"]*len(target_cells))
        read_array=arbitrary_cells.arb_cells(nisys, cells_to_reset, funcs=["READ"]*len(cells_to_reset))
        read_dict = dict(zip(cells_to_reset, read_array))
        print("\nAFTER RESET")
        arbitrary_cells.print_cells(read_dict)
    else:
        print("No cells to reset")
    return read_dict

def multi_reset_and_form(nisys, bl, wls_under_test, wls_to_form, form_pulse):
    for wl_to_form in wls_to_form:
        print(f"\nForming {wl_to_form}")
        read_dict, r_before_form, r_after_form = reset_then_form(nisys, bl, wls_under_test, wl_to_form, form_pulse, do_form=True, do_read=True, do_reset=True)
        nisys.ppmu_all_pins_to_zero()
        
        if r_after_form < 20e3:
            print(f"Forming {wl_to_form} succeeded")
            return 0
        for cell in read_dict:
            if not wl_to_form in cell:
                if read_dict[cell] < 20e3:
                    print(f"Cell {cell} was set while trying to form {wl_to_form}")
                    return 0
        print("No cells were formed or set, accidentally or on purpose")
    

def idxs_to_wl_name(idxs):
    return [f"WL_{idx}" for idx in idxs]

if __name__=="__main__":
    parser = argparse.ArgumentParser(description="Form a cell while keeping cells on the same BL in HRS")
    parser.add_argument("chip", help="chip name for logging")
    parser.add_argument("device", help="device name for logging")
    args = parser.parse_args()
    nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_ProbeCard.toml", polarity="PMOS",slow=False) # FOR CNET + RRAM

    form_pulse = {
        "vbl": -1.5,
        "vsl": 0.5,
        "vwl": -1.5,
        "pw": 1000
    }
    
    bl = "BL_8"
    wls_under_test = idxs_to_wl_name(ALL_WLS)
    wl_to_form = "WL_2"
    reset_then_form(nisys, bl, wls_under_test, wl_to_form, form_pulse, do_form = True, do_read = True, do_reset = True)
    
    # wls_to_form = idxs_to_wl_name([669,8,56])
    # multi_reset_and_form(nisys, bl, wls_under_test, wls_to_form, form_pulse)

    
    nisys.close()
