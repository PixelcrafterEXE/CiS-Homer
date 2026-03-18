import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

fig, (ax, cax) = plt.subplots(1, 2, gridspec_kw={'width_ratios': [15, 1]})

lo = 10
hi = 100
data = np.random.uniform(lo, hi, (10, 10))

lo_n, hi_n = lo / 65535.0, hi / 65535.0
cmap = mcolors.LinearSegmentedColormap.from_list(
    'raster', [(0.0, 'black'), (lo_n, 'black'), (hi_n, 'white'), (1.0, 'white')], N=65536
)

norm = mcolors.Normalize(vmin=0, vmax=65535)
im = ax.imshow(data, cmap=cmap, norm=norm, interpolation='nearest', aspect='equal')
cb = fig.colorbar(im, cax=cax)

cax.set_ylim(lo, hi)
fig.savefig('test_cb.png')
