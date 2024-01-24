"""Script to perform a read voltage sweep on a chip.

Typical usage:
python scripts/transistor_iv.py settings/DEC3_ProbeCard_2x2.json die_cnfet_4
python scripts/transistor_iv.py settings/DEC3_ProbeCard_CNFET_2x2.json die_cnfet_0

"""
import argparse
import os
import numpy as np
from digitalpattern.nirram import NIRRAM
from digitalpattern import env
import nidigital
import matplotlib.pyplot as plt
from relay_switch import relay_switch

# Get arguments
parser = argparse.ArgumentParser(description="RESET a chip.")
parser.add_argument("settings", help="path to settings file")
parser.add_argument("device_no", help="chip name for logging")
parser.add_argument("--start-vds", type=float, default=0.1, help="start vds")
parser.add_argument("--end-vds", type=float, default=-0.1, help="end vds")
parser.add_argument("--step-vds", type=float, default=5, help="step vds")
parser.add_argument("--start-vgs", type=float, default=4.0, help="start vgs")
parser.add_argument("--end-vgs", type=float, default=-2.0, help="end vgs")
parser.add_argument("--step-vgs", type=float, default=20, help="step vgs")
parser.add_argument("--array", type=int, default=0, help="input for array size, changes pins used")
args = parser.parse_args()

def iv_curve(
    args,
    wl: str, # wl pin name 
    bl: str, # bl pin name
    sl: str, # sl pin name
):
    # Initialize NI system
    nisys = NIRRAM(args.device_no, args.device_no, settings=args.settings,polarity="PMOS")
    wls, bls, sls = (nisys.wls, nisys.bls, nisys.sls)
    wl_name = wl
    wl, bl, sl = relay_switch(wl, bl, sl, nisys)
    nisys.wls = [wl]
    nisys.bls = [bl]
    nisys.sls = [sl]
    
    # nisys.digital.channels["Body"].selected_function = nidigital.SelectedFunction.PPMU
    # nisys.digital.channels["Body"].ppmu_voltage_level = 1.8
    # nisys.digital.channels["Body"].ppmu_source()
    for body_i, vbody_i in nisys.body.items():
        print(f"body_i: {body_i} {vbody_i}")
        nisys.ppmu_set_vbody(body_i, vbody_i)
    
    for bl_i in nisys.bls: nisys.ppmu_set_vbl(bl_i, 0)
    for sl_i in nisys.sls: nisys.ppmu_set_vsl(sl_i, 0)
    for wl_i in nisys.wls: nisys.ppmu_set_vwl(wl_i, 0)

    results_bl=[]
    results_wl=[]
    results_vbl=[]
    results_vwl=[]
    results_wl_unsel=[]
    vds_sweep = np.linspace(args.start_vds, args.end_vds, args.step_vds)
    vgs_sweep = np.linspace(args.start_vgs, args.end_vgs, args.step_vgs)

    # Do operation across cells
    i=0
    nisys.digital.channels[bl].ppmu_aperture_time = nisys.op["READ"]["aperture_time"]
    nisys.digital.channels[bl].ppmu_aperture_time_units = nidigital.PPMUApertureTimeUnits.SECONDS
    nisys.digital.channels[bl].ppmu_output_function = nidigital.PPMUOutputFunction.VOLTAGE
    nisys.digital.channels[bl].ppmu_current_limit_range = 128e-6

    nisys.digital.channels[sl].ppmu_aperture_time = nisys.op["READ"]["aperture_time"]
    nisys.digital.channels[sl].ppmu_aperture_time_units = nidigital.PPMUApertureTimeUnits.SECONDS
    nisys.digital.channels[sl].ppmu_output_function = nidigital.PPMUOutputFunction.VOLTAGE
    nisys.digital.channels[sl].ppmu_current_limit_range = 128e-6

    nisys.digital.channels[wl].ppmu_aperture_time = nisys.op["READ"]["aperture_time"]
    nisys.digital.channels[wl].ppmu_aperture_time_units = nidigital.PPMUApertureTimeUnits.SECONDS
    nisys.digital.channels[wl].ppmu_output_function = nidigital.PPMUOutputFunction.VOLTAGE
    nisys.digital.channels[wl].ppmu_current_limit_range = 2e-6

    for vds in vds_sweep:
        results_bl.append([])
        results_wl.append([])
        results_vbl.append([])
        results_vwl.append([])
        results_wl_unsel.append([])
        for vgs in vgs_sweep:
            nisys.ppmu_set_vwl(wl, vgs)
            nisys.ppmu_set_vwl("WL_UNSEL", 4)
            nisys.ppmu_set_vbl(bl, vds)
            meas_v = nisys.digital.channels[bl].ppmu_measure(nidigital.PPMUMeasurementType.VOLTAGE)
            meas_i = nisys.digital.channels[bl].ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)
            meas_v_gate = nisys.digital.channels[wl].ppmu_measure(nidigital.PPMUMeasurementType.VOLTAGE)
            meas_i_gate = nisys.digital.channels[wl].ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)
            meas_i_gate_unsel = nisys.digital.channels["WL_UNSEL"].ppmu_measure(nidigital.PPMUMeasurementType.CURRENT)

            # print(nisys.digital.get_pin_results_pin_information())
            results_bl[i].append(meas_i[0])
            results_wl[i].append(meas_i_gate[0])
            results_wl_unsel[i].append(meas_i_gate_unsel[0])
            results_vbl[i].append(meas_v[0])
            results_vwl[i].append(meas_v_gate[0])
        i += 1

    for bl_i in nisys.bls: nisys.ppmu_set_vbl(bl_i,0)
    for sl_i in nisys.sls: nisys.ppmu_set_vsl(sl_i,0)
    for wl_i in nisys.wls: nisys.ppmu_set_vwl(wl_i,0)
    nisys.ppmu_set_vwl("WL_UNSEL", 0)
    for body in nisys.body: nisys.ppmu_set_vbody(body,0)
    
    results_bl = np.abs(np.array(results_bl))
    results_wl = np.abs(np.array(results_wl))
    results_vbl = np.array(results_vbl)
    results_vwl = np.array(results_vwl)
    results_wl_unsel = np.abs(np.array(results_wl_unsel))

    fig, axes = plt.subplots(nrows = 3, ncols = 2, figsize=(6,8))

    # # (0,0) id-vds 
    # ax_idvd = axes[0][0]
    # ax_idvd.set_xlabel("VDS")
    # ax_idvd.set_ylabel("ID")
    # ax_idvd.plot(vds_sweep, results_bl)

    # # (0,1) vbl vs. vds
    # ax_vblvds = axes[0][1]
    # ax_vblvds.set_xlabel("VDS")
    # ax_vblvds.set_ylabel("VBL")
    # ax_vblvds.plot(vds_sweep, results_vbl)


    # # (1,0) id-vgs 
    # ax_idvg = axes[1][0]
    # ax_idvg.set_yscale("log")
    # ax_idvg.set_xlabel("VGS")
    # ax_idvg.set_ylabel("ID")
    # ax_idvg.plot(vgs_sweep, results_bl.T)

    # # (1,1) vbl vs. vgs
    # ax_vblvgs = axes[1][1]
    # ax_vblvgs.set_xlabel("VGS")
    # ax_vblvgs.set_ylabel("VBL")
    # ax_vblvgs.plot(vgs_sweep, results_vbl.T)


    # (0,0) ig-vg
    ax_igvg = axes[0][0]
    ax_igvg.set_yscale("log")
    ax_igvg.set_xlabel("VGS")
    ax_igvg.set_yscale("log")
    ax_igvg.set_ylabel("IG")
    ax_igvg.plot(vgs_sweep, results_wl.T)

    # (0,1) ig-unsel vs. vgs
    ax_igun_vgun = axes[0][1]
    ax_igun_vgun.set_xlabel("VGS_UNSEL")
    ax_igun_vgun.set_ylabel("IG_UNSEL")
    ax_igun_vgun.set_yscale("log")
    ax_igun_vgun.plot(vgs_sweep, results_wl_unsel.T)

    fig.tight_layout()

    # save fig
    path_fig_dir = os.path.join(env.path_data, args.device_no)
    os.makedirs(path_fig_dir, exist_ok=True)
    dev = "CNT" if nisys.polarity == "PMOS" else "Si"
    # Die3_FormedWL_{bl}\\
    fig.savefig(os.path.join(f"D:\\nirram\\data\\MPW_Test\\1T1R_Chip11\\", f"Gate_Leakage_{wl_name}_{bl}_{sl}_{dev}.png"))
    #plt.show()
    plt.close()

    nisys.close()

def run_iv_curve(all_iv = False, gate_short = True):
    all_wls = [0,2,4,6,8,10,12,14,39,41,43,45,37,47,49,53,35,51,55,57,59,61,63,65,66,69,62,60,56,54,52,58,48,34,77,79]
    all_bls = [8,9,10,11,12,13,14,15]
    #iv_curve(wl_ind=0,bl_sl_ind=0,args=args)

    # FOR NOW: manually check array input size and change
    # hardcoded string pins (for different array sizes)
    # TODO: better abstracting for array vs single FET pin names

    if args.array == 2:
        print("Array size 2")
        for wl_ind in [0, 1]:
            for bl_sl_ind in [0, 1]:
                iv_curve(
                    args,
                    wl=f"A2_WL_{wl_ind}",
                    bl=f"A2_BL_{bl_sl_ind}",
                    sl=f"A2_SL_{bl_sl_ind}",
                )
    elif args.array == 4:
        print("Array size 4")
        for wl_ind in [0, 1, 2, 3]:
            for bl_sl_ind in [0, 1, 2, 3]:
                iv_curve(
                    args,
                    wl=f"A4_WL_{wl_ind}",
                    bl=f"A4_BL_{bl_sl_ind}",
                    sl=f"A4_SL_{bl_sl_ind}",
                )
    elif args.array == 8:
        print("Array size 8")
        for wl_ind in [0, 1, 2, 3, 4, 5, 6, 7]:
            for bl_sl_ind in [0, 1, 2, 3, 4, 5, 6, 7]:
                iv_curve(
                    args,
                    wl=f"A8_WL_{wl_ind}",
                    bl=f"A8_BL_{bl_sl_ind}",
                    sl=f"A8_SL_{bl_sl_ind}",
                )
    else: # default, single device
        print("Defaulting to single device")
        
        if all_iv:
            
            for bl in all_bls:
                for wl in all_wls:
                    iv_curve(
                        args,
                        wl=f"WL_{wl}",
                        bl=f"BL_{bl}",
                        sl=f"SL_{bl}",
                    )
        
        elif gate_short:   
            # all_wls = [54]
            for wl in all_wls:
                iv_curve(
                    args,
                    wl=f"WL_{wl}",
                    bl=f"BL_8",
                    sl=f"SL_8",
                )
        else:   
            iv_curve(
                args,
                wl=f"WL_54",
                bl=f"BL_8",
                sl=f"SL_8",
            )

if __name__ == "__main__":
    run_iv_curve()
    # run_iv_curve(all_iv =True, gate_short=False)