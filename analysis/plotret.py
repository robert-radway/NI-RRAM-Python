import matplotlib.pyplot as plt
import pandas as pd, numpy as np

# names = ["addr", "time", "r", "g"]
names = ["addr", "r"]
data = pd.read_csv("../data/newwrite.tsv", sep='\t', names=names)
data["g"] = 1/data["r"]
#print(data)
# gdata = data.groupby("addr")
# data["t0"] = gdata["time"].transform(lambda t: t - t.min())
# data[data["addr"] < 19000].groupby("addr").plot("t0", "g", ax=plt.gca(), logx=True, legend=None)
# plt.show()

# firstdata = gdata.first().reset_index()
# lastdata = gdata.last().reset_index()
# print(lastdata)

# for data in [firstdata, lastdata]:
for data in [data]:
    data["bin"] = np.floor(data["g"] / 4e-6)
    data["targbin"] = ((data["addr"] - data["addr"][0]) / 2) % 32
    matdata = data["bin"].values.reshape(32,32)
    plt.matshow(matdata, vmin=0, vmax=32)
    for i in range(len(matdata)):
        for j in range(len(matdata[0])):
            c = int(matdata[j,i])
            plt.text(i, j, str(c), va='center', ha='center')
    plt.show()

    plt.figure(figsize=(4,3))
    plt.xlim(0, 150)
    plt.title('Post-Prog. READ Conductance Dist.')
    for i in range(32):
        rdata = data[data['targbin'] == i]
        counts, bin_edges = np.histogram(rdata['g']*1e6, bins=32, density=True)
        cdf = np.cumsum(counts)
        plt.plot(bin_edges[1:], cdf/cdf[-1]*100)
    plt.xlabel('Conductance (uS)')
    plt.ylabel('CDF (%)')
    plt.tight_layout()
    plt.show()
