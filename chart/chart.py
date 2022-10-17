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

    def format_xticklabels(self, label):
        self.ax.xaxis.set_major_locator(mticker.FixedLocator(self.ax.get_xticks().tolist()))
        self.ax.set_xticklabels([label.format(tick) for tick in self.ax.get_xticks()])

    def format_yticklabels(self, label):
        self.ax.yaxis.set_major_locator(mticker.FixedLocator(self.ax.get_yticks().tolist()))
        self.ax.set_yticklabels([label.format(tick) for tick in self.ax.get_yticks()])

    def display(self):
        # Transparent is required for Streamlit because the background is not white
        st.pyplot(self.fig, transparent=True)

    def download_button(self, file_name):
        buf = io.BytesIO()
        plt.savefig(buf, dpi=400, bbox_inches="tight", transparent=True)
        st.sidebar.download_button("Download figure", buf, file_name=file_name, mime="image/png")
