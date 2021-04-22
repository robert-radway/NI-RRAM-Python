# Import libraries
import matplotlib.pyplot as plt, numpy as np, pandas as pd

# Load bitstream as matrix
data = pd.read_csv(open("../data/1us_endurance.tsv"), sep="\t", names=["addr", "Ri", "Rf", "cycle"])

plt.figure(figsize=(4,3))
plt.xlabel("Cycle")
plt.ylabel("Resistance (kOhm)")
plt.xlim(1e2, 1e6)
plt.ylim(0, 100)
plt.xscale('log')
plt.plot(data["cycle"], data["Ri"]/1000, ".")
plt.plot(data["cycle"], data["Rf"]/1000, ".")
plt.tight_layout()
plt.savefig("figs/endurance-R.pdf")

plt.figure(figsize=(4,3))
plt.xlabel("Cycle")
plt.ylabel("Conductance (uS)")
plt.xlim(1e2, 1e6)
plt.xscale('log')
plt.plot(data["cycle"], 1e6/data["Ri"], ".")
plt.plot(data["cycle"], 1e6/data["Rf"], ".")
plt.tight_layout()
plt.savefig("figs/endurance-G.pdf")
