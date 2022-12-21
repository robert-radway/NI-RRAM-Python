"""Script to perform a read voltage sweep on a chip"""
import argparse
import numpy as np
from digitalpattern import NIRRAM
import nidigital
import matplotlib.pyplot as plt

# Get arguments
parser = argparse.ArgumentParser(description="RESET a chip.")
parser.add_argument("device_no", help="chip name for logging")
parser.add_argument("--start-vds", type=float, default=0, help="start vds")
parser.add_argument("--end-vds", type=float, default=-0.5, help="end vds")
parser.add_argument("--step-vds", type=float, default=20, help="step vds")
parser.add_argument("--start-vgs", type=float, default=0, help="start vgs")
parser.add_argument("--end-vgs", type=float, default=-1.5, help="end vgs")
parser.add_argument("--step-vgs", type=float, default=40, help="step vgs")
args = parser.parse_args()

def iv_curve(wl_ind,bl_sl_ind,args):
    wl = f"A2_WL_{wl_ind}"
    bl = f"A2_BL_{bl_sl_ind}"
    sl = f"A2_SL_{bl_sl_ind}"
    # Initialize NI system
    nisys = NIRRAM(args.device_no, args.device_no, settings="settings/DEC3_ProbeCard_2x2.json")
    # nisys.digital.channels["Body"].selected_function = nidigital.SelectedFunction.PPMU
    # nisys.digital.channels["Body"].ppmu_voltage_level = 1.8
    # nisys.digital.channels["Body"].ppmu_source()
    for bl_i in nisys.all_bls: nisys.ppmu_set_vbl(bl_i,0)
    for sl_i in nisys.all_sls: nisys.ppmu_set_vsl(sl_i,0)
    for wl_i in nisys.all_wls: nisys.ppmu_set_vwl(wl_i,0)
    nisys.ppmu_set_vbody("A2_PMOS_BODY",1.5)
    nisys.ppmu_set_vbody("A2_NMOS_BODY",0)

    results_bl=[]
    results_wl=[]
    results_vbl=[]
    results_vwl=[]
    labels = np.linspace(args.start_vds, args.end_vds, args.step_vds)
    x = np.linspace(args.start_vgs, args.end_vgs, args.step_vgs)
    # Do operation across cells
    i=0
    nisys.digital.channels[bl].ppmu_aperture_time = nisys.settings["READ"]["aperture_time"]
    nisys.digital.channels[bl].ppmu_aperture_time_units = nidigital.PPMUApertureTimeUnits.SECONDS
    nisys.digital.channels[bl].ppmu_output_function = nidigital.PPMUOutputFunction.VOLTAGE
    nisys.digital.channels[bl].ppmu_current_limit_range = 32e-6

    nisys.digital.channels[sl].ppmu_aperture_time = nisys.settings["READ"]["aperture_time"]
    nisys.digital.channels[sl].ppmu_aperture_time_units = nidigital.PPMUApertureTimeUnits.SECONDS
    nisys.digital.channels[sl].ppmu_output_function = nidigital.PPMUOutputFunction.VOLTAGE
    nisys.digital.channels[sl].ppmu_current_limit_range = 32e-6

    nisys.digital.channels[wl].ppmu_aperture_time = nisys.settings["READ"]["aperture_time"]
    nisys.digital.channels[wl].ppmu_aperture_time_units = nidigital.PPMUApertureTimeUnits.SECONDS
    nisys.digital.channels[wl].ppmu_output_function = nidigital.PPMUOutputFunction.VOLTAGE
    nisys.digital.channels[wl].ppmu_current_limit_range = 2e-6

    for vds in labels:
        results_bl.append([])
        results_wl.append([])
        results_vbl.append([])
        results_vwl.append([])
        for vgs in x:
            nisys.ppmu_set_vwl(wl, vgs)
            nisys.ppmu_set_vbl(bl, vds)
            meas_v = nisys.digital.channels[bl].ppmu_measure(nidigital.PPMUMeasurementType.VOLTAGE)[0]
            meas_i = nisys.digital.channels[bl].ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)[0]
            meas_v_gate = nisys.digital.channels[wl].ppmu_measure(nidigital.PPMUMeasurementType.VOLTAGE)[0]
            meas_i_gate = nisys.digital.channels[wl].ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)[0]
            results_bl[i].append(meas_i)
            results_wl[i].append(meas_i_gate)
            results_vbl[i].append(meas_v)
            results_vwl[i].append(meas_v_gate)
        i += 1

    for bl in nisys.all_bls: nisys.ppmu_set_vbl(bl,0)
    for sl in nisys.all_sls: nisys.ppmu_set_vsl(sl,0)
    for wl in nisys.all_wls: nisys.ppmu_set_vwl(wl,0)
    for body in nisys.body: nisys.ppmu_set_vbody(body,0)
    
    results_bl = np.abs(np.array(results_bl))
    results_wl = np.abs(np.array(results_wl))
    results_vbl = np.array(results_vbl)
    results_vwl = np.array(results_vwl)

    fig, axes = plt.subplots(nrows = 2, ncols = 3)


    # id-vgs 
    ax_idvg = axes[0][0]
    ax_idvg.set_xlabel("VGS")
    ax_idvg.set_yscale("log")
    ax_idvg.set_ylabel("ID")
    ax_idvg.plot(x, results_bl.T)

    # id-vds 
    ax_idvd = axes[0][2]
    ax_idvd.set_xlabel("VDS")
    ax_idvd.set_ylabel("ID")
    ax_idvd.plot(labels, results_bl)

    # ig-vg
    ax_igvg = axes[1][0]
    ax_igvg.set_xlabel("VGS")
    ax_igvg.set_yscale("log")
    ax_igvg.set_ylabel("IG")
    ax_igvg.plot(x, results_wl.T)

    # vbl vs. vgs
    ax_vblvgs = axes[0][1]
    ax_vblvgs.set_xlabel("VGS")
    ax_vblvgs.set_ylabel("VBL")
    ax_vblvgs.plot(x, results_vbl.T)

    # vwl vs. vgs
    ax_vwlvgs = axes[1][1]
    ax_vwlvgs.set_xlabel("VGS")
    ax_vwlvgs.set_ylabel("VWL")
    ax_vwlvgs.plot(x, results_vwl.T)

    # plt.figure(1)
    # plt.subplot(211)
    # plt.show()
    # plt.semilogy(x, results.T, xlabel="Vgs", ylabel)
    # plt.subplot(212)
    # plt.semilogy(x, results.T,)

    fig.tight_layout()
    fig.savefig(f"C:/Users/acyu/Documents/cnfet rram iv/WL_{wl_ind}-BL_{bl_sl_ind}.png")
    #plt.show()
    plt.close()

    nisys.close()

#iv_curve(wl_ind=0,bl_sl_ind=0,args=args)
for wl_ind in [0,1]:
    for bl_sl_ind in [0,1]:
        iv_curve(wl_ind,bl_sl_ind,args)
        pass
