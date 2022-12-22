# NI-RRAM-Python
NI RRAM programming in Python

## Conda environment
Install: jupyter and pylint

## Pip environment
Install: nidaqmx, nidigital, numpy, (matplotlib, pandas, stats for analysis notebook)

## Project environment config
In settings there is a sample `settings/_env.toml` file. This contains
local paths for storing data. Copy+paste the file into `settings/env.toml`
and customize these paths as needed.

## Scripts
- form_chip.py: FORM a chip
- program_chip.py: Program a bitstream to a chip

Make sure to specify the chip name in the arguments when running either script. Program chip also needs the bitstream file. Two examples can be found in `bitstream/` and the script for generating more can also be found in the other repo.

## Addressing Scheme

```
< MSB.................LSB >
{wl_addr}|{wl_ext_sel}|{sl_addr[6:0]}|sl_ext_sel
```

Note that wl_ext_sel and sl_ext_sel need to be decoded programmatically to determine which wl_ext_[0:3] or bl_ext[0:1] should be high.

## Installing Cascade Autoprobe Controller
Cascade autoprobe controller is used to interface with Cascade autoprobe stations through GPIB.
This is setup as a local pip package named `autoprobe`, so scripts can use `autoprobe` as dependency.
Install the local package using following, run from the root of the project:
```
pip install -e .
```