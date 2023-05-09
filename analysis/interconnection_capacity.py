import pandas as pd
import streamlit as st

import chart
import colors
import utils
import validate


def interconnection_capacity(output_directory):
    """
    Show a horizontal bar chart with the largest expansions in interconnection capacity
    """
    assert validate.is_directory_path(output_directory)

    st.title("🪢 Interconnection capacity")

    # Only show a warning message if the interconnections were not optimized individually
    config = utils.read_yaml(output_directory / "config.yaml")
    if not config["interconnections"]["optimize_individual_interconnections"]:
        st.warning("This analysis is only available for runs where the interconnections are individually optimized")
        return

    # Check if the data should be aggregated per country
    aggregrate_per_country = st.sidebar.checkbox("Aggregate per country")

    # Read the interconnection capacity
    all_data = pd.DataFrame()
    for interconnection_type in ["hvac", "hvdc"]:
        data = utils.read_csv(output_directory / "capacity" / "interconnections" / f"{interconnection_type}.csv")

        if aggregrate_per_country:
            # Change the market nodes to countries
            data["from"] = data["from"].apply(lambda market_node: utils.get_country_property(market_node[:2], "name"))
            data["to"] = data["to"].apply(lambda market_node: utils.get_country_property(market_node[:2], "name"))

        # Group the data per connection
        data["new_index"] = data["from"] + " to " + data["to"]
        data = data.groupby(["new_index"]).sum(numeric_only=True)
        data["interconnection_type"] = interconnection_type

        all_data = pd.concat([all_data, data])

    # Get and sort all interconnections that got extra capacity
    number_of_shown_interconnections = st.sidebar.slider("Number of interconnections shown", value=10, min_value=3, max_value=len(all_data.index))
    interconnections_with_extra_capacity = all_data.sort_values("extra").tail(number_of_shown_interconnections)

    # Set the interconnection capacity to GW if the maximum extra capacity exceeds 1 GW
    unit = "MW"
    if interconnections_with_extra_capacity.extra.max() > 1000:
        interconnections_with_extra_capacity[["current", "extra"]] /= 1000
        unit = "GW"

    # Create the bar chart
    bar_chart = chart.Chart(xlabel=f"Extra capacity ({unit})", ylabel="")
    bar_colors = [colors.primary() if interconnection_type == "hvdc" else colors.secondary() for interconnection_type in interconnections_with_extra_capacity["interconnection_type"]]
    labels = [utils.format_str(interconnection_type) for interconnection_type in interconnections_with_extra_capacity["interconnection_type"]]
    bar_chart.axs.barh(interconnections_with_extra_capacity.index, interconnections_with_extra_capacity.extra, color=bar_colors, label=labels)
    bar_chart.add_legend()

    # Show the bar chart
    bar_chart.display()
    bar_chart.download_button("interconnection_capacity.png")

    # Show the sensitivity data as a table
    with st.expander("Data points"):
        st.table(data.sort_values("extra", ascending=False))
