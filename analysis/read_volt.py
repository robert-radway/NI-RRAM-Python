import matplotlib.pyplot as plt
import pandas as pd, numpy as np

names = ["addr", "i", "v"]
data = pd.read_csv("../data/read_multivolt.tsv", sep='\t', names=names)
data["g"] = data["i"] / data["v"]
data["targbin"] = ((data["addr"] - data["addr"][0]) / 2) % 32

for targbin in range(32):
    gdata = data[data["targbin"] == targbin].groupby(["v"])
    plt.plot(gdata["v"].mean(), gdata["i"].mean())
plt.show()
