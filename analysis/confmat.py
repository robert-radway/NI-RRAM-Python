import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Define conductances
CONDS = np.arange(0, 129e-6, 4e-6)
CONDS[0] = 1e-9
print(CONDS)

#names = ["addr", "op", "rf", "gf", "if", "vf"]
names = ["addr", "rf"]

data = pd.read_csv("../data/newwrite.tsv", names=names, sep='\t')
data["gf"] = 1/data["rf"]
data["bin"] = np.floor(data["gf"] / 4e-6)
data["targbin"] = ((data["addr"] - data["addr"][0]) / 2) % 32
matdata = data["bin"].values.reshape(32,32)
plt.matshow(matdata, vmin=0, vmax=32)
plt.show()

plt.figure(figsize=(4,3))
plt.xlim(0, 150)
plt.title('Post-Prog. READ Conductance Dist.')
for i in range(32):
    rdata = data[data['targbin'] == i]
    counts, bin_edges = np.histogram(rdata['gf']*1e6, bins=32, density=True)
    cdf = np.cumsum(counts)
    plt.plot(bin_edges[1:], cdf/cdf[-1]*100)
plt.xlabel('Conductance (uS)')
plt.ylabel('CDF (%)')
plt.tight_layout()
plt.savefig('figs/mb-cdf.pdf')

print(data[data["targbin"] == 0])
