from matplotlib import pyplot as plt

from .chart import Chart
from .map import Map
from .sankey import Sankey

# Set the font for all plots to serif
plt.rcParams["font.family"] = "serif"
plt.rcParams["mathtext.fontset"] = "dejavuserif"
plt.rcParams["xtick.direction"] = "inout"
plt.rcParams["ytick.direction"] = "inout"
