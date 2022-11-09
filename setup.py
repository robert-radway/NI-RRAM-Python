"""
This sets up the controller backend as a pip module named "controller".
Files can then resolve imports from package root.
"""
from setuptools import setup, find_packages

setup(name="autoprobe", version="0.0", packages=find_packages())