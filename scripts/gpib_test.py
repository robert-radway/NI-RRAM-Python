import pyvisa

rm = pyvisa.ResourceManager()
resources = rm.list_resources()
print(resources)

# inst = rm.open_resource("GPIB0::16::INSTR") # b1500
inst = rm.open_resource("GPIB0::22::INSTR") # cascade
print(inst.query("*IDN?"))

