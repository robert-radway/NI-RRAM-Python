"""
Generate .json containing position of DEC3 wafer modules.
Generated from inspecting die GDS layout.

Home location (0, 0) defined as BOTTOM LEFT corner of die.
"""

import os
import json
from dataclasses import dataclass

path_out = os.path.join("test", "dec3", "modules.json")

@dataclass
class Coord:
    x: float
    y: float

@dataclass
class DeviceColumn:
    col: int
    pads: int # per device, rows = floor(pad_rows_per_column / pads)

# "home" location on overall layout. this is first device column on bottom-left
# corner of bottom left die (cnt/rram die on bottom left)
global_origin = Coord(-4543.50, -12812.50)

# 45 rows of pads per column
pad_rows_per_column = 45

# dx and dy per pad
pad_dx = 50 # um
pad_dy = 90 # um

# simplified modules layout description, will be converted to hard coded
# names and x,y coordinate locations
modules_layout = {
    "si_pmos": {
        "die_origin": Coord(-4543.50, 8852.50),
        "columns": {
            "short_test": DeviceColumn(col=0, pads=2),
            "short_test2": DeviceColumn(col=1, pads=6),
            "short_test3": DeviceColumn(col=2, pads=2),
            "1t_1": DeviceColumn(col=3, pads=5), # D S G B VSS
            "1t_2": DeviceColumn(col=4, pads=5),
            "1t_3": DeviceColumn(col=5, pads=5),
            "1t_4": DeviceColumn(col=6, pads=5),
            "1t_5": DeviceColumn(col=7, pads=5),
            "1t1r_1": DeviceColumn(col=8,  pads=5),
            "1t1r_2": DeviceColumn(col=9,  pads=5),
            "1t1r_3": DeviceColumn(col=10, pads=5),
            "1t1r_4": DeviceColumn(col=11, pads=5),
            "1t1r_5": DeviceColumn(col=12, pads=5),
            "1t1r_6": DeviceColumn(col=13, pads=5),
            "1t1r_7": DeviceColumn(col=14, pads=5),
            "1t1r_8": DeviceColumn(col=15, pads=5),
            "1t1r_9": DeviceColumn(col=16, pads=5),
        },
    },
    "si_nmos": {
        "die_origin": Coord(143.50, 8852.50),
        "columns": {
            "short_test": DeviceColumn(col=0, pads=2),
            "short_test2": DeviceColumn(col=1, pads=6),
            "short_test3": DeviceColumn(col=2, pads=2),
            "1t_1": DeviceColumn(col=3, pads=4), # D S G B
            "1t_2": DeviceColumn(col=4, pads=4),
            "1t_3": DeviceColumn(col=5, pads=4),
            "1t_4": DeviceColumn(col=6, pads=4),
            "1t_5": DeviceColumn(col=7, pads=4),
            "1t1r_1": DeviceColumn(col=8,  pads=4),
            "1t1r_2": DeviceColumn(col=9,  pads=4),
            "1t1r_3": DeviceColumn(col=10, pads=4),
            "1t1r_4": DeviceColumn(col=11, pads=4),
            "1t1r_5": DeviceColumn(col=12, pads=4),
            "1t1r_6": DeviceColumn(col=13, pads=4),
            "1t1r_7": DeviceColumn(col=14, pads=4),
            "1t1r_8": DeviceColumn(col=15, pads=4),
            "1t1r_9": DeviceColumn(col=16, pads=4),
        },
    },
    "cnt_left_bottom": {
        "die_origin": Coord(-4543.50, -12812.50),
        "columns": {
            "short_test": DeviceColumn(col=0, pads=2),
            "short_test2": DeviceColumn(col=1, pads=6),
            "short_test3": DeviceColumn(col=2, pads=2),
            "1t_1": DeviceColumn(col=3, pads=3), # D S G
            "1t_2": DeviceColumn(col=4, pads=3),
            "1t_3": DeviceColumn(col=5, pads=3),
            "1t_4": DeviceColumn(col=6, pads=3),
            "1t_5": DeviceColumn(col=7, pads=3),
            "1t1r_1": DeviceColumn(col=8,  pads=3),
            "1t1r_2": DeviceColumn(col=9,  pads=3),
            "1t1r_3": DeviceColumn(col=10, pads=3),
            "1t1r_4": DeviceColumn(col=11, pads=3),
            "1t1r_5": DeviceColumn(col=12, pads=3),
            "1t1r_6": DeviceColumn(col=13, pads=3),
            "1t1r_7": DeviceColumn(col=14, pads=3),
            "1t1r_8": DeviceColumn(col=15, pads=3),
            "1t1r_sc": DeviceColumn(col=16, pads=3), # "short channel" ??
        },
    },
    "cnt_left_top": {
        "die_origin": Coord(-4543.50, -8479.50),
        "columns": {
            "short_test": DeviceColumn(col=0, pads=2),
            "short_test2": DeviceColumn(col=1, pads=6),
            "short_test3": DeviceColumn(col=2, pads=2),
            "1t_1": DeviceColumn(col=3, pads=3), # D S G
            "1t_2": DeviceColumn(col=4, pads=3),
            "1t_3": DeviceColumn(col=5, pads=3),
            "1t_4": DeviceColumn(col=6, pads=3),
            "1t_5": DeviceColumn(col=7, pads=3),
            "1t1r_1": DeviceColumn(col=8,  pads=3),
            "1t1r_2": DeviceColumn(col=9,  pads=3),
            "1t1r_3": DeviceColumn(col=10, pads=3),
            "1t1r_4": DeviceColumn(col=11, pads=3),
            "1t1r_5": DeviceColumn(col=12, pads=3),
            "1t1r_6": DeviceColumn(col=13, pads=3),
            "1t1r_7": DeviceColumn(col=14, pads=3),
            "1t1r_8": DeviceColumn(col=15, pads=3),
            "1t1r_sc": DeviceColumn(col=16, pads=3), # "short channel" ??
        },
    },
    "cnt_right_bottom": {
        "die_origin": Coord(143.50, -12812.50),
        "columns": {
            "short_test": DeviceColumn(col=0, pads=2),
            "short_test2": DeviceColumn(col=1, pads=6),
            "short_test3": DeviceColumn(col=2, pads=2),
            "1t_1": DeviceColumn(col=3, pads=3), # D S G
            "1t_2": DeviceColumn(col=4, pads=3),
            "1t_3": DeviceColumn(col=5, pads=3),
            "1t_4": DeviceColumn(col=6, pads=3),
            "1t_5": DeviceColumn(col=7, pads=3),
            "1t1r_1": DeviceColumn(col=8,  pads=3),
            "1t1r_2": DeviceColumn(col=9,  pads=3),
            "1t1r_3": DeviceColumn(col=10, pads=3),
            "1t1r_4": DeviceColumn(col=11, pads=3),
            "1t1r_5": DeviceColumn(col=12, pads=3),
            "1t1r_6": DeviceColumn(col=13, pads=3),
            "1t1r_7": DeviceColumn(col=14, pads=3),
            "1t1r_8": DeviceColumn(col=15, pads=3),
            "1t1r_sc": DeviceColumn(col=16, pads=3), # "short channel" ??
        },
    },
    "cnt_right_top": {
        "die_origin": Coord(143.50, -8479.50),
        "columns": {
            "short_test": DeviceColumn(col=0, pads=2),
            "short_test2": DeviceColumn(col=1, pads=6),
            "short_test3": DeviceColumn(col=2, pads=2),
            "1t_1": DeviceColumn(col=3, pads=3), # D S G
            "1t_2": DeviceColumn(col=4, pads=3),
            "1t_3": DeviceColumn(col=5, pads=3),
            "1t_4": DeviceColumn(col=6, pads=3),
            "1t_5": DeviceColumn(col=7, pads=3),
            "1t1r_1": DeviceColumn(col=8,  pads=3),
            "1t1r_2": DeviceColumn(col=9,  pads=3),
            "1t1r_3": DeviceColumn(col=10, pads=3),
            "1t1r_4": DeviceColumn(col=11, pads=3),
            "1t1r_5": DeviceColumn(col=12, pads=3),
            "1t1r_6": DeviceColumn(col=13, pads=3),
            "1t1r_7": DeviceColumn(col=14, pads=3),
            "1t1r_8": DeviceColumn(col=15, pads=3),
            "1t1r_sc": DeviceColumn(col=16, pads=3), # "short channel" ??
        },
    },
}


# =============================================================================
# BUILD FULL MODULES LIST
# =============================================================================
modules = {}
for subdie_name, subdie in modules_layout.items():
    die_origin = Coord( # translate so global home is at (0, 0)
        subdie["die_origin"].x - global_origin.x,
        subdie["die_origin"].y - global_origin.y,
    )

    for module_name, module in subdie["columns"].items():
        x = die_origin.x + (module.col * pad_dx)
        rows = int(pad_rows_per_column / module.pads)
        row_dy = module.pads * pad_dy
        for row in range(rows):
            y = die_origin.y + (row * row_dy)
            full_module_name = f"{subdie_name}_{module_name}_row_{row+1}" # 1-indexed
            modules[full_module_name] = {
                "x": x,
                "y": y,
            }

with open(path_out, "w+") as f:
    json.dump(modules, f, indent=2)
