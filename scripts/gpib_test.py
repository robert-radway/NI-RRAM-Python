import pyvisa

rm = pyvisa.ResourceManager()
resources = rm.list_resources()
print(resources)

INSTRUMENTS = [
    "GPIB0::16::INSTR", # b1500
    "GPIB0::22::INSTR", # gax 1 or gax 2
    "GPIB1::22::INSTR", # gax ni probe card
]

for gpib_addr in INSTRUMENTS:
    try:
        inst = rm.open_resource(gpib_addr)
        idn = inst.query("*IDN?")
        print(f"{gpib_addr}: {idn}")
    except:
        print(f"No instrument at address {gpib_addr}")
