import io

import numpy as np
import streamlit as st
from matplotlib import pyplot as plt

import colors
import utils


class Map:
    """
    Create a geopandas map based on a Series with country level data
    """

    def __init__(self, data, *, label=None, format_percentage=False):
        # Create the figure
        self.fig, self.ax = plt.subplots(figsize=(6, 4))
        self.ax.axis("off")
        self.ax.margins(0)

        # Create the color bar
        colormap = colors.colormap("blue")
        v_min = data.min()
        v_max = data[data < np.Inf].max()
        scalar_mappable = plt.cm.ScalarMappable(cmap=colormap, norm=plt.Normalize(vmin=v_min, vmax=v_max))
        self.fig.colorbar(scalar_mappable, shrink=0.7, aspect=20, label=label, format=lambda x, pos: f"{x:.0%}" if format_percentage else f"{x:.3g}")

        # Get the geopandas DataFrame and map the data to it
        map_df = utils.get_geometries_of_countries(data.index)
        map_df["data"] = map_df.index.map(data)

        # Plot the data
        map_df.to_crs("EPSG:3035").plot(column="data", cmap=colormap, linewidth=0.5, ax=self.ax, edgecolor=colors.get("gray", 600), missing_kwds={"color": "white"})

    def display(self):
        # Transparent is required for Streamlit because the background is not white
        st.pyplot(self.fig, dpi=400, bbox_inches="tight", transparent=True)

    def download_button(self, file_name):
        buf = io.BytesIO()
        plt.savefig(buf, dpi=800, bbox_inches="tight", transparent=True)
        st.sidebar.download_button("💾 Download figure", buf, file_name=file_name, mime="image/png")
