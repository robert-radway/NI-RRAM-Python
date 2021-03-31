# Import libraries
import matplotlib.pyplot as plt, numpy as np, pandas as pd

<<<<<<< HEAD
# Chip ID
CHIP = 'C2'
tsv_file = 'read.tsv'
=======
# Chip number
CHIP = 7
tsv_file = 'read_0325.tsv'
>>>>>>> b2d044268b7995dee9ad083e3f7d5c52aaa9e23a

# Load bitstream
# bs = np.loadtxt(open("../bitstream/vectors_bitstream.txt"), dtype=np.int32)
bs = np.loadtxt(open("../bitstream/vectors_bitstream_2.txt"), dtype=np.int32)

# Load target output as dataframe
cols = ['addr', 'R']
dtypes = {
    'addr': np.int32,
    'R': np.float64
}
data = pd.read_csv(f'../log/{CHIP}/{tsv_file}', names=cols, sep='\t', dtype=dtypes, index_col='addr')
data['bin'] = bs[:len(data)]

# CDF curves
plt.figure(figsize=(4,3))
plt.xlim(5, 1e3)
plt.xscale('log')
plt.title('Post-Prog. READ Resistance Dist.')
for i in range(2):
    rdata = data[data['bin'] == i]
    counts, bin_edges = np.histogram(rdata['R']/1000, bins=65536, density=True)
    cdf = np.cumsum(counts)
    plt.plot(bin_edges[1:], cdf/cdf[-1]*100)
plt.xlabel('Resistance (kOhm)')
plt.ylabel('CDF (%)')
plt.tight_layout()
plt.savefig('figs/progread-cdf.pdf')

plt.figure(figsize=(4,3))
plt.xlim(0, 150)
plt.title('Post-Prog. READ Conductance Dist.')
for i in range(2):
    rdata = data[data['bin'] == i]
    counts, bin_edges = np.histogram(1e6/rdata['R'], bins=65536, density=True)
    cdf = np.cumsum(counts)
    plt.plot(bin_edges[1:], cdf/cdf[-1]*100)
plt.xlabel('Conductance (uS)')
plt.ylabel('CDF (%)')
plt.tight_layout()
plt.savefig('figs/progread-g-cdf.pdf')
