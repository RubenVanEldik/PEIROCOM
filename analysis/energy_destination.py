import pandas as pd
import streamlit as st

import chart
import colors
import utils
import validate


def energy_destination(output_directory, resolution):
    """
    Show a bar chart with the initial destination of the energy
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_resolution(resolution)

    st.title("🧭️ Energy destination")

    # Get temporal results for all countries
    all_temporal_results = utils.get_temporal_results(output_directory, resolution)
    config = utils.read_yaml(output_directory / "config.yaml")

    # Select the included countries
    st.sidebar.header("Options")
    country_codes = st.sidebar.multiselect("Country", config["country_codes"], format_func=lambda country_code: utils.get_country_property(country_code, "name"))

    # Show all countries if none are selected
    if len(country_codes) == 0:
        country_codes = config["country_codes"]

    index = all_temporal_results[next(iter(all_temporal_results))].index
    cumulative_temporal_results = pd.DataFrame(index=index)
    for production_technology in config["technologies"]["production"]:
        cumulative_temporal_results[f"production_{production_technology}_MW"] = 0
        cumulative_temporal_results[f"demand_{production_technology}_MW"] = 0
        cumulative_temporal_results[f"curtailed_{production_technology}_MW"] = 0
        cumulative_temporal_results[f"stored_{production_technology}_MW"] = 0
        cumulative_temporal_results[f"export_{production_technology}_MW"] = 0

        for bidding_zone in utils.get_bidding_zones_for_countries(country_codes):
            temporal_results_bidding_zone = all_temporal_results[bidding_zone]

            # Calculate the ratio of production of this technology to all production
            production_share = temporal_results_bidding_zone[f"production_{production_technology}_MW"] / (temporal_results_bidding_zone.production_total_MW - temporal_results_bidding_zone.net_export_MW.clip(upper=0) - temporal_results_bidding_zone.net_storage_flow_total_MW.clip(upper=0))

            # Calculate the destination of electricity generated by this technology
            cumulative_temporal_results[f"production_{production_technology}_MW"] += temporal_results_bidding_zone[f"production_{production_technology}_MW"]
            cumulative_temporal_results[f"demand_{production_technology}_MW"] += production_share * temporal_results_bidding_zone.demand_MW
            cumulative_temporal_results[f"curtailed_{production_technology}_MW"] += production_share * temporal_results_bidding_zone.curtailed_MW
            cumulative_temporal_results[f"stored_{production_technology}_MW"] += production_share * temporal_results_bidding_zone.net_storage_flow_total_MW.clip(lower=0)
            cumulative_temporal_results[f"export_{production_technology}_MW"] += production_share * temporal_results_bidding_zone.net_export_MW.clip(lower=0)

    # Create a new DataFrame with the data for the bar chart
    data = pd.DataFrame()
    cumulative_temporal_results = cumulative_temporal_results.sum()
    for production_technology in config["technologies"]["production"]:
        data.loc[production_technology, "consumed"] = cumulative_temporal_results[f"demand_{production_technology}_MW"] / cumulative_temporal_results[f"production_{production_technology}_MW"]
        data.loc[production_technology, "curtailed"] = cumulative_temporal_results[f"curtailed_{production_technology}_MW"] / cumulative_temporal_results[f"production_{production_technology}_MW"]
        data.loc[production_technology, "stored"] = cumulative_temporal_results[f"stored_{production_technology}_MW"] / cumulative_temporal_results[f"production_{production_technology}_MW"]
        data.loc[production_technology, "export"] = cumulative_temporal_results[f"export_{production_technology}_MW"] / cumulative_temporal_results[f"production_{production_technology}_MW"]

    # Initialize bar chart
    bar_chart = chart.Chart(xlabel="", ylabel="Initial destination (%)")
    bar_width = 0.8

    # Create the bars for each destination
    bottom = 0
    for index, column_name in enumerate(data):
        bar_chart.ax.bar(data.index, data[column_name], bar_width, bottom=bottom, label=utils.format_str(column_name), color=colors.get("gray", 900 - index * 200))
        bottom += data[column_name]

    # Set some chart options
    bar_chart.ax.legend()
    bar_chart.ax.set_ylim([0, 1])
    bar_chart.ax.set_xticklabels([utils.format_technology(technology_name) for technology_name in config["technologies"]["production"]])
    bar_chart.format_yticklabels("{:,.0%}")

    # Plot the destination plot
    bar_chart.display()
    bar_chart.download_button("energy_destination.png")

    # Show the sensitivity data as a table
    with st.expander("Data points"):
        st.table(data)
