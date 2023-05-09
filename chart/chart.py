import io
import math

import streamlit as st
from matplotlib import pyplot as plt
from matplotlib import ticker as mticker


class Chart:
    """
    Create a matplotlib figure
    """

    def __init__(self, nrows=1, ncols=1, *, xlabel=None, ylabel=None, xscale="linear", yscale="linear", sharex=True, sharey=True, wide=False):
        # Store the number of rows and columns of the figure
        self.nrows = nrows
        self.ncols = ncols
        self.wide = wide

        # Create the figure
        width = 6 * 522 / 252 if wide else 6 # 522/252 is the textwidth/columnwidth ratio in the Elsevier template
        height = 3.5 * nrows ** (5 / 7)
        self.fig, self.axs = plt.subplots(nrows, ncols, figsize=(width, height), sharex=sharex, sharey=sharey)

        # Make a list with all axis independent of layout
        self.all_axs = []
        if nrows > 1 and ncols > 1:
            for axs in self.axs:
                self.all_axs.extend(axs)
        elif nrows > 1 or ncols > 1:
            self.all_axs.extend(self.axs)
        else:
            self.all_axs.append(self.axs)

        # Set the labels on the outer x- and y-axis and remove the top and right spine
        for ax in self.all_axs:
            ax.set_xscale(xscale)
            ax.set_yscale(yscale)
            ax.spines.right.set_visible(False)
            ax.spines.top.set_visible(False)

        if nrows > 1 and ncols > 1:
            for axs in self.axs:
                axs[0].set(ylabel=ylabel)
            for axs in self.axs[-1]:
                axs.set(xlabel=xlabel)
                axs.spines.bottom.set_visible(True)
        elif nrows > 1:
            for axs in self.axs:
                axs.set(ylabel=ylabel)
            self.axs[-1].set(xlabel=xlabel)
            self.axs[-1].spines.bottom.set_visible(True)
        elif ncols > 1:
            for axs in self.axs:
                axs.set(xlabel=xlabel)
                axs.spines.bottom.set_visible(True)
            self.axs[0].set(ylabel=ylabel)
        else:
            self.axs.spines.bottom.set_visible(True)
            self.axs.set(xlabel=xlabel)
            self.axs.set(ylabel=ylabel)

    def format_xticklabels(self, label):
        for ax in self.all_axs:
            ax.xaxis.set_major_locator(mticker.FixedLocator(ax.get_xticks().tolist()))
            ax.set_xticklabels([label.format(tick) for tick in ax.get_xticks()])

    def format_yticklabels(self, label):
        for ax in self.all_axs:
            ax.yaxis.set_major_locator(mticker.FixedLocator(ax.get_yticks().tolist()))
            ax.set_yticklabels([label.format(tick) for tick in ax.get_yticks()])

    def add_legend(self):
        # Get all legend items from the different subplots and display them
        legend_items = {label: handle for ax in self.all_axs for handle, label in zip(*ax.get_legend_handles_labels())}
        self.fig.legend(legend_items.values(), legend_items.keys(), bbox_to_anchor=(0.5, 1), loc="lower center", ncol=4 if self.wide else 3, frameon=False, framealpha=0)

    def display(self):
        # Enable tight_layout
        self.fig.tight_layout()

        # Transparent is required for Streamlit because the background is not white
        st.pyplot(self.fig, dpi=200, bbox_inches="tight", transparent=True)

    def download_button(self, file_name):
        # Enable tight_layout
        self.fig.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, dpi=400, bbox_inches="tight", transparent=True)
        st.sidebar.download_button("💾 Download figure", buf, file_name=file_name, mime="image/png")
