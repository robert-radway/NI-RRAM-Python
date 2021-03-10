"""Example GPIB for communicating with Agilent E3649A power supply for automation"""

# Import Python IVI
import ivi

# Connect to E3649A via GPIB
ADDR = 1
psu = ivi.agilent.agilentE3649A("GPIB0::{ADDR}::INSTR")
# # Connect to E3649A via E2050A GPIB to VXI11 bridge
# psu = ivi.agilent.agilentE3649A("TCPIP0::192.168.1.105::gpib,5::INSTR")
# # Connect to E3649A via serial
# psu = ivi.agilent.agilentE3649A("ASRL::COM1,9600::INSTR")

# Configure output
psu.outputs[0].configure_range('voltage', 5)
psu.outputs[0].voltage_level = 5.0
psu.outputs[0].current_limit = 1.0
psu.outputs[0].ovp_limit = 14.0
psu.outputs[0].ovp_enabled = True
psu.outputs[0].enabled = True
