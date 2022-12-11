import plotly
import streamlit as st


class Sankey:
    """
    Create a Plotly sankey figure
    """

    def __init__(self, *, node_color=None, link_color=None, valueformat=None, pad=None):
        self.node = {"label": [], "x": [], "y": [], "color": node_color, "pad": pad, "line": None}
        self.link = {"source": [], "target": [], "value": [], "color": link_color}
        self.valueformat = valueformat

    def add_node(self, label, *, x=None, y=None):
        self.node["label"].append(label)
        self.node["x"].append(x)
        self.node["y"].append(y)

    def add_link(self, source, target, value):
        self.link["source"].append(self.node["label"].index(source))
        self.link["target"].append(self.node["label"].index(target))
        self.link["value"].append(value)

    def display(self):
        layout = plotly.graph_objects.Layout(paper_bgcolor="rgba(255, 255, 255, 0)", font={"family": "Source Serif Pro"})
        sankey = plotly.graph_objects.Sankey(node=self.node, link=self.link, valueformat=self.valueformat)
        fig = plotly.graph_objects.Figure(sankey, layout=layout)

        # Plot the figure
        st.plotly_chart(fig)
