import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Define conductances
CONDS = np.arange(0, 129e-6, 4e-6)
CONDS[0] = 1e-9
print(CONDS)

names = ["addr", "op", "rf", "gf", "if", "vf"]

data = pd.read_csv("log/read2.csv", names=names)
data["bin"] = np.floor(data["gf"] / 4e-6)
data["targbin"] = (data["addr"] - data["addr"][0]) % 32
plt.matshow(data["bin"].values.reshape(32,32), vmin=0, vmax=32)
plt.show()

print(data[data["targbin"] == 0])
