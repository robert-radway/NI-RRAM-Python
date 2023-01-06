"""
Module for RRAM memory array masking.
Keep this separate from nirram so we can unit test this without requiring
importing all the ni digital system packages.
"""
import numpy as np
import pandas as pd
from BitVector import BitVector

class RRAMArrayMaskException(Exception):
    """Exception produced by the ArrayMask class"""
    def __init__(self, msg):
        super().__init__(f"ArrayMask: {msg}")

class RRAMArrayMask:
    """
    Class for masking specific WLs, BLs for programming pulses.
    Indicates mask of bits that need further programming.
    As we run a programming pulses, when specific WL/BL combinations
    hit their target resistance, we can mask them off to skip them and
    only continue to program cells that have not hit target yet.
    """
    def __init__(
        self,
        wls,
        bls,
        sls,
        all_wls,
        all_bls,
        all_sls,
        polarity,
        init_state=None,
    ):
        # 
        if init_state is None:
            self.mask = pd.DataFrame(np.array([[(bl in bls) and (wl in wls) for bl in all_bls] for wl in all_wls]), all_wls, all_bls)
        else:
            self.mask = init_state
        self.wls = wls
        self.bls = bls
        self.sls = sls
        self.polarity = polarity
        # else: raise RRAMArrayMaskException("1TNR Operations Not Supported")
    
    def get_pulse_masks(self):
        masks = []
        needed_wls = self.mask[self.mask.apply(np.sum,axis=1).ge(1)]
        for wl in needed_wls.index:
            wl_mask = self.mask.index == wl
            bl_mask = pd.Series.to_numpy(needed_wls.loc[wl])
            sl_mask = bl_mask & False
            masks.append((wl_mask, bl_mask, sl_mask))
        # print(f"pulse masks {masks}")
        return masks

    def update_mask(self, failing):
        self.mask = failing
