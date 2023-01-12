"""
Utility functions.
"""
from enum import Enum, unique
import numpy as np

@unique
class Comparison(Enum):
    """Enum class for comparison operators (>, >=, <, <=, ==).
    So we can re-use RRAM pulsing functions with different target goals,
    e.g. do a (RES <= HRS) comparison by using RRAMTargetComparison.LESS_THAN_EQUAL. 
    """
    EQUALS = 0
    LESS = 1
    LESS_OR_EQUALS = 2
    GREATER = 3
    GREATER_OR_EQUALS = 4

    def __call__(self, *args, **kwargs):
        """Override call to allow doing comparisons like:
        Comparison.EQUALS(a, b) -> a == b
        """
        a = args[0]
        b = args[1]
        if self == Comparison.EQUALS:
            return a == b
        elif self == Comparison.LESS:
            return a < b
        elif self == Comparison.LESS_OR_EQUALS:
            return a <= b
        elif self == Comparison.GREATER:
            return a > b
        elif self == Comparison.GREATER_OR_EQUALS:
            return a >= b
        else:
            raise ValueError(f"Invalid comparison operator: {self}")

def linear_sweep(
    v,
    dtype=np.float64,
) -> list:
    """Convert different measurement value sweep formats into a list
    of linearly spaced sweep values. Conversions are:
    - num -> [num]: single number to a list with 1 value
    - list -> list: for a list input, simply return same
    - {"start": x0, "stop": x1, "step": dx} -> [x0, x0 + dx, ..., x1]
        Convert a standard dict with "start", "stop", and "step" keys into
        a linspace. This includes the endpoint.
    """
    if isinstance(v, float) or isinstance(v, int):
        return [v]
    elif isinstance(v, list):
        return v
    elif isinstance(v, dict):
        import numpy as np
        # abs required to ensure no negative points if stop < start
        # round required due to float precision errors, avoids .9999 npoint values
        npoints = 1 + int(abs(round((v["stop"] - v["start"])/v["step"])))
        return np.linspace(v["start"], v["stop"], npoints, dtype=dtype)
    else:
        raise ValueError(f"Sweep range is an invalid format (must be number, list, or start/stop/step dict): {v}")

def log10_sweep(
    v,
    dtype=np.float64,
) -> list:
    """Convert different measurement value sweep formats into a list
    of log-spaced sweep values. Conversions are:
    - num -> [num]: single number to a list with 1 value
    - list -> list: for a list input, simply return same
    - {"start": x0, "stop": x1, "steps": n} -> log10_dx = (log10(x1) - log10(x0)) / n
        -> 10^[log10(x0), log10(x0) + log10_dx, ..., log10(x1)]
        Convert a standard dict with "start", "stop", and either "step" or
        "steps" keys into a logspace with base 10, e.g.
            {"start": 1, "stop": 1000, "step": 10] -> [1, 10, 100, 1000].
            {"start": 1, "stop": 1000, "steps": 3] -> [1, 10, 100, 1000].
    """
    if isinstance(v, float) or isinstance(v, int):
        return [v]
    elif isinstance(v, list):
        return v
    elif isinstance(v, dict):
        import numpy as np
        # abs required to ensure no negative points if stop < start
        # round required due to float precision errors, avoids .9999 npoint values
        log10_start = np.log10(v["start"])
        log10_stop = np.log10(v["stop"])
        if "step" in v:
            log10_step = np.log10(v["step"])
            npoints = 1 + int(abs(round((log10_stop - log10_start)/log10_step)))
            return np.logspace(log10_start, log10_stop, npoints, dtype=dtype)
        elif "steps" in v:
            return np.logspace(log10_start, log10_stop, v["steps"], dtype=dtype)
        else:
            raise ValueError(f"log10_sweep dict must have either 'step' or 'steps' key: {v}")
    else:
        raise ValueError(f"Sweep range is an invalid format (must be number, list, or start/stop/step dict): {v}")



if __name__ == "__main__":
    # print line testing/debugging
    print(log10_sweep({"start": 1, "stop": 10000, "step": 10}))
    print(log10_sweep({"start": 1, "stop": 10000, "step": 100}))

    print(log10_sweep({"start": 1, "stop": 10000, "steps": 5}))
    print(log10_sweep({"start": 1, "stop": 10000, "steps": 3}))