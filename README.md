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

## Addressing Scheme

```
< MSB.................LSB >
{wl_addr}|{wl_ext_sel}|{sl_addr[6:0]}|sl_ext_sel
```

Note that wl_ext_sel and sl_ext_sel need to be decoded programmatically to determine which wl_ext_[0:3] or bl_ext[0:1] should be high.

## Chip Status

Chip 1: Breakout Board Chip, status: unsure if working, looks like the wire bonds are shorted...  
Chip 2: Prototyping Chip, status: some cells over-SET, working otherwise, nothing formed past 2512 as far as known  
Chip 3: FORMed all, programmed with first set of inputs (HRS: 70-90kOhm)... was somewhat working, but then we tried to push to 500kOhm and shorted a bunch of cells. Lesson learned: don't push past 100kOhm.  
Chip 4: FORMed every 8 cells, programmed with a simple debug vector, working but cell HRS is 70-90kOhm  
Chip 5: FORMed every 8 cells, programmed with a simple debug vector, HRS is >100kOhm, working  
Chip 6: FORMed all, programmed with first set of inputs (HRS: >100kOhm), working!!! Re-measured accuracy matrix vs. bias conditions.   
Chip 7: FORMed all, programmed with second batch of inputs (HRS: >100kOhm). Re-programmed to batch_0 vectors (lots of stuck-at error bits).
Chip 8: FORMed all, programmed with a simple debug vector (same as 4), we think the sense amp might be broken  
Chip 9: prototyping  
Chip 10: FORMed all, programmed with batch_0 feature vectors (HRS >100kOhm). Measured accuracy matrix vs. bias conditoins (consistent with Chip 6).



## Change notes (haitong)
- Add args for target LRS/HRS windows when programming a chip
- Could be perhaps moved into self.settings and then specify a different setting json when targetting at different resistance levels
    - if SET/RESET pulse settings also need to be modified together, this approach would be more convenient 