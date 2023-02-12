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

    # Select the interconnection type
    interconnection_type = st.sidebar.selectbox("Interconnection type", ["hvac", "hvdc"], format_func=utils.format_str)

    # Read the interconnection capacity
    data = utils.read_csv(output_directory / "interconnection_capacity" / f"{interconnection_type}.csv")

    # Change the bidding zones to countries
    data["from"] = data["from"].apply(lambda bidding_zone: utils.get_country_property(bidding_zone[:2], "name"))
    data["to"] = data["to"].apply(lambda bidding_zone: utils.get_country_property(bidding_zone[:2], "name"))

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