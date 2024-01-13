"""Script to perform a read voltage sweep on a chip"""
import argparse
import numpy as np
from digitalpattern.nirram import NIRRAM
import matplotlib.pyplot as plt
import nidaqmx
# Get arguments
parser = argparse.ArgumentParser(description="RESET a chip.")
parser.add_argument("chip", help="chip name for logging")
parser.add_argument("device", help="device name for logging")

args = parser.parse_args()
# Initialize NI system
# For CNFET: make sure polarity is PMOS
nisys = NIRRAM(args.chip, args.device, settings="settings/MPW_ProbeCard.toml", polarity="PMOS") # FOR CNFET RRAM

#VDD is 1.8V

#RMUX_EN, SA_EN all high
#RMUX_EN: CSA control signal. Pulling this to 5V turns on a thick oxide transistor inside the CSA which connects the RRAM cell with the CSA input.
#SA_EN: Enable signal for CSA.
blref_val = 0b11111111
blrep_val = blref_val
blref_rep = np.uint16(str(blref_val) + str(blrep_val))
read_time = 3
waveform = [blref_rep]*read_time
result = nisys.arbitrary_pulse(waveform, "BLREFBLREP","CSA_Read","RREF_Data",read_time)
data=  []
for timestep in result:
    if timestep["SA_RDY"] == 1:
        data.append(timestep["DO"])
#set BL_REF and BL_REP: always the same value. reference conductance DAC

#set VREAD to desired voltage (probably 0.3V)
VREAD = nisys.op["READ"][nisys.polarity]["VBL"]
nisys.digital.channels["VREAD"].configure_voltage_levels(vil=0, vih=VREAD, vol=0, voh=VREAD, vterm=0)

#start pulsing SA_CLK




#wait until SA_RDY is high 
#read DO (LRS is 1, HRS is 0)




digipat_file = "PULSE_MPW_ProbeCard"
nisys.digital.burst_pattern(digipat_file)
nisys.read(record=True)
#different pattern