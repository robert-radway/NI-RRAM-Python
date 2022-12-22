"""
Python wrapper for local environment config "env".
Load local paths for data, figs, etc. from `settings/env.toml` file.
This parses and stores config parameters in the `settings/env.toml`
file into local python global variables. Other modules can import
this module and simply references variables like fields on the module:

```
from digitalpattern import env
print(env.path_data)
```
"""

import tomli

# load env file
with open("settings/env.toml", "rb") as f:
    toml = tomli.load(f)

# parse fields into properties
path_data: str = toml["path_data"]