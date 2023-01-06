"""
Test for debugging RRAM array WL/BL selection masks
"""

from digitalpattern.mask import RRAMArrayMask

# define all WLs, BLs, SLs names
# NOTE: 4 exist for all WLs, SLs and BLs so that interface is identical for
# single 1T1R, 1T4R, 2x2 array, and 4x4 array. So that we can re-use same
# pinout for all these devices. 
ALL_WLS = [ "WL_0", "WL_1", "WL_2", "WL_3",]
ALL_SLS = [ "SL_0", "SL_1", "SL_2", "SL_3",]
ALL_BLS = [ "BL_0", "BL_1", "BL_2", "BL_3",]

# subset of WL, BL, SL that will be pulsed for measurement
WLS = [ "WL_0", ]
SLS = [ "SL_0", ]
BLS = [ "BL_0", "BL_1", "BL_2", "BL_3", ]


mask_4x4 = RRAMArrayMask(
    wls=ALL_WLS,
    bls=ALL_BLS,
    sls=ALL_SLS,
    all_wls=ALL_WLS,
    all_bls=ALL_BLS,
    all_sls=ALL_SLS,
    polarity="PMOS",
)

mask_1tnr = RRAMArrayMask(
    wls=WLS,
    bls=BLS,
    sls=SLS,
    all_wls=ALL_WLS,
    all_bls=ALL_BLS,
    all_sls=ALL_SLS,
    polarity="PMOS",
)

for mask_name, mask in [
    ("4x4", mask_4x4),
    ("1TNR", mask_1tnr),
]:
    print(f"Mask: {mask_name}")
    print(mask.mask)
    for (wl_mask, bl_mask, sl_mask) in mask.get_pulse_masks():
        print(f"wl_mask = {wl_mask}")
        print(f"bl_mask = {bl_mask}")
        print(f"sl_mask = {sl_mask}")
        print()