import numpy as np
from digitalpattern.util import Comparison

a = 1
b = 2

assert Comparison.EQUALS(a, a) == True, "a == a"
assert Comparison.EQUALS(a, b) == False, "a == b"
assert Comparison.EQUALS(b, a) == False, "a == b"
assert Comparison.LESS(a, a) == False, "a < a"
assert Comparison.LESS(a, b) == True, "a < b"
assert Comparison.LESS(b, a) == False, "b < a"
assert Comparison.LESS_OR_EQUALS(a, a) == True, "a <= a"
assert Comparison.LESS_OR_EQUALS(a, b) == True, "a <= b"
assert Comparison.LESS_OR_EQUALS(b, a) == False, "b <= a"
assert Comparison.GREATER(a, a) == False, "a > b"
assert Comparison.GREATER(a, b) == False, "a > b"
assert Comparison.GREATER(b, a) == True, "b > a"
assert Comparison.GREATER_OR_EQUALS(a, a) == True, "a >= a"
assert Comparison.GREATER_OR_EQUALS(a, b) == False, "a >= b"
assert Comparison.GREATER_OR_EQUALS(b, a) == True, "b >= a"
