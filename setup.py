"""
This sets up the controller backend as a pip module named "controller".
Files can then resolve imports from package root.
"""
from setuptools import setup

setup(
    name="ni_rram",
    version="0.0",
    packages=["autoprobe", "digitalpattern"],
)