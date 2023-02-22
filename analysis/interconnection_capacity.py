import streamlit as st

import chart
import colors
import utils
import validate


def interconnection_capacity(output_directory):
    """
    Show a horizontal bar chart with the largest expansions in interonnection capacity
    """
    assert validate.is_directory_path(output_directory)

    st.title("🪢 Interconnection capacity")

    # Only show a warning message if the interconnections were not optimized individually
    config = utils.read_yaml(output_directory / "config.yaml")
    if not config["interconnections"]["optimize_individual_interconnections"]:
        st.warning("This analysis is only available for runs where the interconnections are individually optimized")
        return

    # Select the interconnection type
    interconnection_type = st.sidebar.selectbox("Interconnection type", ["hvac", "hvdc"], format_func=utils.format_str)

    # Read the interconnection capacity
    data = utils.read_csv(output_directory / "capacity" / "interconnections" / f"{interconnection_type}.csv")

    # Change the market nodes to countries
    data["from"] = data["from"].apply(lambda market_node: utils.get_country_property(market_node[:2], "name"))
    data["to"] = data["to"].apply(lambda market_node: utils.get_country_property(market_node[:2], "name"))

    # Group the data per connection
    data["new_index"] = data["from"] + " to " + data["to"]
    data = data.groupby(["new_index"]).sum()

    # Get and sort all interconnections that got extra capacity
    min_extra_capacity = 10
    interconnections_with_extra_capacity = data[data.extra > min_extra_capacity].sort_values("extra")

    # Create the bar chart
    bar_chart = chart.Chart(xlabel="Extra capacity (GW)", ylabel="")
    bar_chart.ax.barh(interconnections_with_extra_capacity.index, interconnections_with_extra_capacity.extra / 1000, color=colors.primary())

    # Show the bar chart
    bar_chart.display()
    bar_chart.download_button("interconnection_capacity.png")

    # Show the sensitivity data as a table
    with st.expander("Data points"):
        st.table(data.sort_values("extra", ascending=False))
