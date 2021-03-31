import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Chip number
CHIP_ID = 'C2'
tsv_file = 'read_formed.tsv'


# Load target output as dataframe
cols = ['addr', 'R']
dtypes = {
    'addr': np.int32,
    'R': np.float64
}


data = pd.read_csv(f'../log/{CHIP_ID}/{tsv_file}', names=cols, sep='\t', dtype=dtypes, index_col='addr')

r_mat = data['R'].values.reshape(256, 256) / 1000 # kOhm

fig = plt.figure()
mat = plt.gca().matshow(r_mat, vmin=0, vmax=100)
cbar = plt.colorbar(mat)
cbar.set_label('Resistance (KOhm', rotation=270)
plt.xlabel('BL/SL #')
plt.ylabel('WL #')
plt.xticks(np.arange(0, 257, 64))
plt.yticks(np.arange(0, 257, 64))
plt.tight_layout()
plt.savefig('./figs/res_matrix.pdf')
