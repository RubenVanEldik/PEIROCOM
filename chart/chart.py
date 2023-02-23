import io
from matplotlib import pyplot as plt
from matplotlib import ticker as mticker
import streamlit as st


class Chart:
    """
    Create a matplotlib figure
    """

    def __init__(self, *, xlabel, ylabel, xscale="linear", yscale="linear", wide=False):
        # Create the figure
        figure_width = 9 if wide else 7
        figure_height = 4
        self.fig, self.ax = plt.subplots(figsize=(figure_width, figure_height))
        self.fig.tight_layout()

        # Set the axes' labels and scale and remove the top and right spine
        self.ax.set(xlabel=xlabel)
        self.ax.set(ylabel=ylabel)
        self.ax.set_xscale(xscale)
        self.ax.set_yscale(yscale)
        self.ax.spines.right.set_visible(False)
        self.ax.spines.top.set_visible(False)

    def format_xticklabels(self, label):
        self.ax.xaxis.set_major_locator(mticker.FixedLocator(self.ax.get_xticks().tolist()))
        self.ax.set_xticklabels([label.format(tick) for tick in self.ax.get_xticks()])

    def format_yticklabels(self, label):
        self.ax.yaxis.set_major_locator(mticker.FixedLocator(self.ax.get_yticks().tolist()))
        self.ax.set_yticklabels([label.format(tick) for tick in self.ax.get_yticks()])

    def add_legend(self, *, ncol=3):
        self.ax.legend(bbox_to_anchor=(0.5, 1), loc="lower center", ncol=ncol, frameon=False, framealpha=0)

    def display(self):
        # Transparent is required for Streamlit because the background is not white
        st.pyplot(self.fig, dpi=400, bbox_inches="tight", transparent=True)

    def download_button(self, file_name):
        buf = io.BytesIO()
        plt.savefig(buf, dpi=800, bbox_inches="tight", transparent=True)
        st.sidebar.download_button("💾 Download figure", buf, file_name=file_name, mime="image/png")
