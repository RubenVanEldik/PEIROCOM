import io
from matplotlib import pyplot as plt
from matplotlib import ticker as mticker
import streamlit as st


class Chart:
    """
    Create a matplotlib figure
    """

    fig = None
    ax = None

    def __init__(self, *, xlabel, ylabel, xscale="linear", yscale="linear"):
        # Create the figure
        self.fig, self.ax = plt.subplots(figsize=(7, 5))

        # Set the axes' labels and scale
        self.ax.set(xlabel=xlabel)
        self.ax.set(ylabel=ylabel)
        self.ax.set_xscale(xscale)
        self.ax.set_yscale(yscale)

    def set_x_limits(self, x_min, x_max):
        self.ax.set_xlim([x_min, x_max])

    def set_y_limits(self, y_min, y_max):
        self.ax.set_ylim([y_min, y_max])

    def format_xticklabels(self, label):
        ticks_loc = self.ax.get_xticks().tolist()
        self.ax.xaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
        xticks = self.ax.get_xticks()
        self.ax.set_xticklabels([label.format(tick) for tick in xticks])

    def format_yticklabels(self, label):
        ticks_loc = self.ax.get_yticks().tolist()
        self.ax.yaxis.set_major_locator(mticker.FixedLocator(ticks_loc))
        yticks = self.ax.get_yticks()
        self.ax.set_yticklabels([label.format(tick) for tick in yticks])

    def display(self):
        st.pyplot(self.fig)

    def download_button(self, file_name):
        buf = io.BytesIO()
        plt.savefig(buf, dpi=400, bbox_inches="tight")
        st.download_button("Download figure", buf, file_name=file_name, mime="image/png")
