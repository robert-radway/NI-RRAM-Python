# NI-RRAM-Python
NI RRAM programming in Python

## Conda environment
Install: jupyter and pylint

## Pip environment
Install: hightime, numpy, nitclk, nifgen, nidcpower, nidaqmx

## Scripts
- form_chip.py: FORM a chip
- program_chip.py: Program a bitstream to a chip

Make sure to specify the chip name in the arguments when running either script. Program chip also needs the bitstream file. Two examples can be found in `bitstream/` and the script for generating more can also be found in the other repo.



## Change notes (haitong)
- Add args for target LRS/HRS windows when programming a chip
- Could be perhaps moved into self.settings and then specify a different setting json when targetting at different resistance levels
    - if SET/RESET pulse settings also need to be modified together, this approach would be more convenient 