"""Script to perform a read voltage sweep on a chip"""
import argparse
from digitalpattern.nirram import NIRRAM
from relay_switch import relay_switch
import pdb
import nidigital
import time
import numpy as np

def print_waveform(results_dict, bl_idxs, si_selectors=False):
    if si_selectors:
        n_csas = 2
    else:
        n_csas = 8
    assert(len(bl_idxs) == n_csas)
    for wl_name in results_dict:
        print(wl_name)
        for idx,bl in enumerate(bl_idxs):
            sa_rdy_waveform = [int(x[f"SA_RDY_{idx}"]) for x in results_dict[wl_name]]
            do_waveform = [int(x[f"DO_{idx}"]) for x in results_dict[wl_name]]
            print(f"SA_RDY_{idx}:\t{sum(sa_rdy_waveform)}")
            print(f"DO_{idx}:\t\t{sum(do_waveform)}")

def col_sel_idx_bls(col_sel_idx,si_selectors):
    if si_selectors:
        n_csas = 2
    else:
        n_csas = 8
    return [f"BL_{32-int(32/n_csas)*(i+1)+col_sel_idx}" for i in range(n_csas)] #from rram_csa_3d_readout_full_tb: The first CSA is connected to RRAM cells <31> to <28>, the second is connected to RRAM cells <27> to <24>, and so on.

def set_and_source_voltage(nisys, voltages, scalar=1):
    for channel in voltages:
        nisys.digital.channels[channel].ppmu_voltage_level = voltages[channel]*scalar
        if channel in ['VDD','VSA','VSS']:
            nisys.digital.channels[channel].ppmu_current_limit_range = 32e-3
        else:
            nisys.digital.channels[channel].ppmu_current_limit_range = 32e-3
        nisys.digital.channels[channel].ppmu_source()
    time.sleep(0.01)

def measure_iv(nisys, sources, channels_to_measure):
    all_channels = list(sources.keys()) + channels_to_measure
    for channel in all_channels:
        nisys.digital.channels[channel].ppmu_aperture_time_units = nidigital.PPMUApertureTimeUnits.SECONDS
        nisys.digital.channels[channel].ppmu_aperture_time = nisys.op["READ"]["aperture_time"]
        print(f"{channel}: {nisys.digital.channels[channel].ppmu_measure(measurement_type=nidigital.PPMUMeasurementType.VOLTAGE)[0]:.1f}V, {nisys.digital.channels[channel].ppmu_measure(measurement_type=nidigital.PPMUMeasurementType.CURRENT)[0]:.2E}A")


# Get arguments
if __name__ == "__main__":
    # Get arguments
    parser = argparse.ArgumentParser(description="RESET a chip.")
    parser.add_argument("chip", help="chip name for logging")
    parser.add_argument("device", help="device name for logging")
    args = parser.parse_args()
    nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_ProbeCard.toml", polarity="NMOS",slow=False) # FOR CNET + RRAM

    #ensure high Z for non-driving pins
    nisys.digital.termination_mode = nidigital.TerminationMode.VTERM
    for line in ['SA_RDY_0','SA_RDY_1','DO_0','DO_1']:
        nisys.digital.channels[line].termination_mode = nidigital.TerminationMode.VTERM
    for line in nisys.sls:
        nisys.digital.channels[line].termination_mode = nidigital.TerminationMode.VTERM
    for line in nisys.bls:
        nisys.digital.channels[line].termination_mode = nidigital.TerminationMode.VTERM
    
    si_selectors=False
    #if si_selectors, col_sel_idx is hardwired
    col_sel_idx=0
    bls = col_sel_idx_bls(col_sel_idx, si_selectors=si_selectors)    
    
    #WL_0, BL_8 thru BL_15 is formed. so COL_SEL must be 8 thru 15 (group of 8 on the right)
    wl, bl, sl = relay_switch("WL_0", "BL_11", "SL_11", nisys)

    #get IV of voltage sources
    #if 

    sources = {
        "VDD": 5,
        "VSA": 5,
        "VSS": 0,
        "MUX_SEL_CONV_CLK": 0,
        "MUX_SEL_WT": 0,
    }
    
    run_measure_iv=True
    if run_measure_iv:
        test_sources = {
            "RMUX_EN": 5,
            "VREAD": 0.3,
            "SA_EN": 5,
            "WL_UNSEL": 0,
            wl: 0.3,
            "SA_CLK": 5,
            "COL_SEL": 5,
        }
        sources = {**sources, **test_sources}

        sweep=False
        if not sweep:
            set_and_source_voltage(nisys, sources)
            time.sleep(1)
            measure_iv(nisys, sources, channels_to_measure=['SA_RDY_0','SA_RDY_1','DO_0','DO_1'])
        else:
            channel = 'VSA'
            measure_channel = "SA_RDY_1"
            nisys.digital.channels[channel].ppmu_aperture_time_units = nidigital.PPMUApertureTimeUnits.SECONDS
            nisys.digital.channels[channel].ppmu_aperture_time = 0.001
            print(f'{channel}_set,  {channel},  {channel}_I,    {measure_channel}_V,    {measure_channel}_I')
            results={channel:{'V':[],'A':[]},measure_channel:{'V':[],'A':[]}}
            for v in np.arange(0,5.01,0.2):
                sources[channel] = v
                set_and_source_voltage(nisys, sources)
                for chan in [channel, measure_channel]:
                    results[chan]['V']=nisys.digital.channels[chan].ppmu_measure(measurement_type=nidigital.PPMUMeasurementType.VOLTAGE)[0]
                    results[chan]['A']=nisys.digital.channels[chan].ppmu_measure(measurement_type=nidigital.PPMUMeasurementType.CURRENT)[0]
                print(f"{v:.1f},    {results[channel]['V']:.1f}V,   {results[channel]['A']:.2E}A,   {results[measure_channel]['V']:.1f}V,   {results[measure_channel]['A']:.2E}A")
            
    else:
        set_and_source_voltage(nisys, sources)

        #pw max: 65535 cycles
        results_dict = nisys.csa_read(wls=[wl],vread=0.1,vwl=2.2,pw=65535,col_sel_idx=col_sel_idx,vwl_unsel=0,si_selectors=si_selectors)

        #boundary resistor is currently 12.546 kohms (5.646+6.9) at COL_SEL_5 (BL_8+col_sel_idx)
        print_waveform(results_dict,bls,si_selectors=si_selectors)
    set_and_source_voltage(nisys, sources, scalar=0)
    time.sleep(1)

    

    nisys.close()