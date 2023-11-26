# Examples of nbti script usage on MIT gax2 probe station

Be sure to change wafer name e.g.
`cnfet_scaling_w2_x_2_y_1_lc_400_lch_160`
and device ID  `..._col1_10_...` (for device on wafer)
before running and switching devices.

## DC NBTI

### DC Stress at constant gate voltage
- VGstress = -2 V
- (Default) VDread = -0.1 V
- Initial IDVG sweep from +0.4 to -1.4 V with 0.2 V step (~1 ms pulsed spot IV)
```
python .\scripts\nbti.py .\settings\NBTI_GAX2.toml cnfet_scaling_w2_x_2_y_1_lc_400_lch_160 col1_23_dc --tend 1e4 --tend-relax 1e4 --samples 100 --samples-relax 100 --initial-sweep 0.4 -1.4 0.2 --read-gate-bias -1.2 --gate-bias -2
```

### DC Stress at constant gate voltage with VG boosting
- Need "boosting" for < -2 V and >6 V bias (NI 6571 limits)
- VGstress = -2 V
- VGboost = +1 V
- (Default) VDread = -0.1 V
- Initial IDVG sweep from +0.4 to -1.4 V with 0.2 V step (~1 ms pulsed spot IV)
- VGstress,actual = -1 V
- VS,actual = +1 V
- VD,actual = +1 V
- VD,read,actual = +0.9 V
```
python .\scripts\nbti.py .\settings\NBTI_GAX2.toml cnfet_scaling_w2_x_2_y_1_lc_400_lch_160 col1_23_dc --tend 1e4 --tend-relax 1e4 --samples 100 --samples-relax 100 --initial-sweep 0.4 -1.4 0.2 --read-gate-bias -1.2 --gate-bias -2 --boost-voltage 1
```

### DC Stress at a oxide electric field
- Calculates VGS to reach normalized Eox ~ (VGS - VT) / EOT
- Requires EOT input
- Eox = -10 MV/cm
- EOT = 2.13 nm
- With VT ~ 0, this will be around VGS ~ -2.15 V
- (Default) VDread = -0.1 V
- Initial IDVG sweep from +0.4 to -1.4 V with 0.2 V step (~1 ms pulsed spot IV)
- Will automatically choose the read gate bias below VG stress found
```
python .\scripts\nbti.py .\settings\NBTI_GAX2.toml cnfet_scaling_w2_x_2_y_1_lc_400_lch_160 col1_23_dc_efield_10 --tend 1e4 --tend-relax 1e4 --samples 100 --samples-relax 100 --initial-sweep 0.4 -1.4 0.2 --eot 2.13 --efield -10
```


## AC NBTI

Need to adjust `t_nbti_ac_unit` based on period of signal
otherwise may overflow cycles count needed on the NI system.
The examples below are adjusted for this.

Measurement time based on total cumulative stress time:
```
Tstresstotal = Tstress/cycle * cycles = Duty cycle * 1/Freq * cycles = Duty cycle * T
T = Tstresstotal / duty cycle
```
- for 1e4 s stress and 0.5 duty cycle, measurement will take 1e4/0.5 = 2e4 ~  5.6 hr
- for 1e4 s stress and 0.2 duty cycle, measurement will take 1e4/0.2 = 5e4 ~ 13.9 hr

These are long times so plan accordingly, do low duty cycle measurements overnight.

It takes 4-5 hours for our CNFETs to relax to within <0.1% of original VT at room T.


### 1 Hz, 0.5 duty cycle AC stress at low gate voltage = -0.6 V
- Freq = 1 Hz
- Duty cycle = 0.5
- Tstress/cycle = 500 ms
- Trelax/cycle = 500 ms
- Tstresstotal = 1e4
- No relaxation measurement
- VGstress = -0.6 V
- VGread = -0.3 V
```
python .\scripts\nbti.py .\settings\NBTI_GAX2.toml cnfet_scaling_w2_x_2_y_1_lc_400_lch_160 col1_23_ac --no-relax --tstart 1e0 --tend 1e4 --samples 20 --ac --ac-freq 1 --dutycycle 0.5 --t-unit 1e-5 --initial-sweep 0.1 -0.4 0.1 --read-gate-bias -0.3 --gate-bias -0.6
```

### 1 Hz, 0.5 duty cycle AC stress at medium gate voltage = -1.2 V
- Freq = 1 Hz
- Duty cycle = 0.5
- Tstress/cycle = 500 ms
- Trelax/cycle = 500 ms
- Tstresstotal = 1e4
- No relaxation measurement
- VGstress = -1.2 V
- VGread = -0.6 V
```
python .\scripts\nbti.py .\settings\NBTI_GAX2.toml cnfet_scaling_w2_x_2_y_1_lc_400_lch_160 col1_23_ac --no-relax --tstart 1e0 --tend 1e4 --samples 20 --ac --ac-freq 1 --dutycycle 0.5 --t-unit 1e-5 --initial-sweep 0.2 -0.8 0.2 --read-gate-bias -0.6 --gate-bias -1.2
```

### 1 Hz, 0.5 duty cycle AC stress at high gate voltage = -1.8 V
- Freq = 1 Hz
- Duty cycle = 0.5
- Tstress/cycle = 500 ms
- Trelax/cycle = 500 ms
- Tstresstotal = 1e4
- No relaxation measurement
- VGstress = -1.8 V
- VGread = -1.0 V
```
python .\scripts\nbti.py .\settings\NBTI_GAX2.toml cnfet_scaling_w2_x_2_y_1_lc_400_lch_160 col1_23_ac --no-relax --tstart 1e0 --tend 1e4 --samples 20 --ac --ac-freq 1 --dutycycle 0.5 --t-unit 1e-5 --initial-sweep 0.4 -1.2 0.2 --read-gate-bias -1.0 --gate-bias -1.8
```

### 1 kHz, 0.5 duty cycle AC stress at medium gate voltage = -0.6 V
- Freq = 1 kHz
- Duty cycle = 0.5
- Tstress/cycle = 500 us
- Trelax/cycle = 500 us
- Tstresstotal = 1e4
- No relaxation measurement
- VGstress = -0.6 V
- VGread = -0.3 V
```
python .\scripts\nbti.py .\settings\NBTI_GAX2.toml cnfet_scaling_w2_x_2_y_1_lc_400_lch_160 col1_23_ac --no-relax --tstart 5e-3 --tend 1e4 --samples 20 --ac --ac-freq 1e3 --dutycycle 0.5 --t-unit 1e-6 --initial-sweep 0.1 -0.4 0.1 --read-gate-bias -0.3 --gate-bias -0.6
```

### 1 kHz, 0.5 duty cycle AC stress at medium gate voltage = -1.2 V
- Freq = 1 kHz
- Duty cycle = 0.5
- Tstress/cycle = 500 us
- Trelax/cycle = 500 us
- Tstresstotal = 1e4
- No relaxation measurement
- VGstress = -1.2 V
- VGread = -0.6 V
```
python .\scripts\nbti.py .\settings\NBTI_GAX2.toml cnfet_scaling_w2_x_2_y_1_lc_400_lch_160 col1_23_ac --no-relax --tstart 5e-3 --tend 1e4 --samples 20 --ac --ac-freq 1e3 --dutycycle 0.5 --t-unit 1e-6 --initial-sweep 0.4 -1.2 0.2 --read-gate-bias -0.6 --gate-bias -1.2
```

### 1 kHz, 0.5 duty cycle AC stress at medium gate voltage = -1.8 V
- Freq = 1 kHz
- Duty cycle = 0.5
- Tstress/cycle = 500 us
- Trelax/cycle = 500 us
- Tstresstotal = 1e4
- No relaxation measurement
- VGstress = -1.8 V
- VGread = -1.0 V
```
python .\scripts\nbti.py .\settings\NBTI_GAX2.toml cnfet_scaling_w2_x_2_y_1_lc_400_lch_160 col1_23_ac --no-relax --tstart 5e-3 --tend 1e4 --samples 20 --ac --ac-freq 1e3 --dutycycle 0.5 --t-unit 1e-6 --initial-sweep 0.4 -1.2 0.2 --read-gate-bias -1.0 --gate-bias -1.8
```

### 1 MHz, 0.5 duty cycle AC stress at low gate voltage = -0.6 V
- Freq = 1 MHz
- Duty cycle = 0.5
- Tstress/cycle = 500 ns
- Trelax/cycle = 500 ns
- VGstress = -1.2 V
- No relaxation measurement
- VGstress = -0.6 V
- VGread = -0.3 V
```
python .\scripts\nbti.py .\settings\NBTI_GAX2.toml cnfet_scaling_w2_x_2_y_1_lc_400_lch_160 col1_23_ac --no-relax --tstart 5e-3 --tend 1e4 --samples 20 --ac --ac-freq 1e6 --dutycycle 0.5 --t-unit 50e-9 --initial-sweep 0.1 -0.4 0.1 --read-gate-bias -0.3 --gate-bias -0.6
```

### 1 MHz, 0.5 duty cycle AC stress at medium gate voltage = -1.2 V
- Freq = 1 MHz
- Duty cycle = 0.5
- Tstress/cycle = 500 ns
- Trelax/cycle = 500 ns
- VGstress = -1.2 V
- No relaxation measurement
- VGstress = -1.2 V
- VGread = -0.6 V
```
python .\scripts\nbti.py .\settings\NBTI_GAX2.toml cnfet_scaling_w2_x_2_y_1_lc_400_lch_160 col1_23_ac --no-relax --tstart 5e-3 --tend 1e4 --samples 20 --ac --ac-freq 1e6 --dutycycle 0.5 --t-unit 50e-9 --initial-sweep 0.4 -1.2 0.2 --read-gate-bias -0.6 --gate-bias -1.2
```

### 1 MHz, 0.5 duty cycle AC stress at high gate voltage = -1.8 V
- Freq = 1 MHz
- Duty cycle = 0.5
- Tstress/cycle = 500 ns
- Trelax/cycle = 500 ns
- VGstress = -1.2 V
- No relaxation measurement
- VGstress = -1.8 V
- VGread = -1.0 V
```
python .\scripts\nbti.py .\settings\NBTI_GAX2.toml cnfet_scaling_w2_x_2_y_1_lc_400_lch_160 col1_23_ac --no-relax --tstart 5e-3 --tend 1e4 --samples 20 --ac --ac-freq 1e6 --dutycycle 0.5 --t-unit 50e-9 --initial-sweep 0.4 -1.2 0.2 --read-gate-bias -1.0 --gate-bias -1.8
```


## IDVG, VT, gm Relaxation Tests

### Post-stress IDVG curve sampling
- Does DC VG stress for 1e3 seconds then relaxes and measures post stress IVs
- Takes 20 post stress IV during relax with log time spacing
- (Default) VGstress = -2 V
- (Default) VDread = -0.1 V
```
python .\scripts\nbti.py .\settings\NBTI_GAX2.toml cnfet_scaling_w2_x_2_y_1_lc_400_lch_160 col1_10_burnin_relax_iv --no-relax --tend 1e3 --samples 40 --tend-relax 2e3 --samples-relax 20 --relax-iv
```
