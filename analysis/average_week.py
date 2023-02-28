import pandas as pd
import streamlit as st

import chart
import colors
import utils
import validate


def average_week(output_directory):
    """
    Show a chart with the average week for each season
    """
    assert validate.is_directory_path(output_directory)

    st.title("📅 Average week")

    # Ask for which countries the statistics should be shown
    st.sidebar.header("Options")
    config = utils.read_yaml(output_directory / "config.yaml")
    selected_country_codes = st.sidebar.multiselect("Countries", config["country_codes"], format_func=lambda country_code: utils.get_country_property(country_code, "name"))

    # Get temporal results for all countries
    temporal_results = utils.get_temporal_results(output_directory, group="all", country_codes=selected_country_codes)

    # Ask if the import and export should be shown in the chart
    show_import_export = st.sidebar.checkbox("Show import and export")
    show_hydropower = temporal_results.generation_total_hydropower_MW.abs().max() != 0

    # Set the unit to TW or GW when applicable
    unit = "MW"
    if temporal_results.demand_total_MW.max() > 10 ** 6:
        temporal_results /= 10 ** 6
        unit = "TW"
    elif temporal_results.demand_total_MW.max() > 10 ** 3:
        temporal_results /= 10 ** 3
        unit = "GW"

    # Initialize a plot with 4 subplots
    week_plot = chart.Chart(4, 1)

    # Loop over each of the four seasons
    season_dates = {"winter": list(range(1, 79)) + list(range(355, 366)), "spring": list(range(79, 172)), "summer": list(range(172, 266)), "autumn": list(range(266, 355))}
    season_data = {}
    for index, season in enumerate(season_dates.keys()):
        # Get a subset of the temporal results
        temporal_results_season = temporal_results[temporal_results.index.dayofyear.isin(season_dates[season])]

        # Get the results of an average week
        temporal_results_season = temporal_results_season.groupby([temporal_results_season.index.weekday, temporal_results_season.index.hour]).mean()
        temporal_results_season["hour_of_week"] = temporal_results_season.index.to_series().apply(lambda x: 24 * x[0] + x[1])
        temporal_results_season = temporal_results_season.set_index("hour_of_week")
        season_data[season] = temporal_results_season

        # Set the title and format the ticks and labels of the subplot
        subplot = week_plot.axs[index]
        subplot.set_title(utils.format_str(season), rotation=90, x=1.025, y=0.3)
        subplot.set_xticks(range(0, 24 * 7, 24), ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], ha="left")
        subplot.set_xlim([0, 7 * 24])
        subplot.set_yticklabels([round(abs(x)) for x in subplot.get_yticks()])
        subplot.text(-0.055, 0.46, "Generation", transform=subplot.transAxes, horizontalalignment="right", verticalalignment="top", rotation=90)
        subplot.text(-0.055, 0.59, "Demand", transform=subplot.transAxes, horizontalalignment="right", verticalalignment="bottom", rotation=90)
        subplot.text(-0.1, 0.5, f"({unit})", transform=subplot.transAxes, horizontalalignment="right", verticalalignment="center", rotation=90)

        # Demand
        # Create a series with the cumulative demand
        cumulative_demand = pd.Series(0, index=temporal_results_season.index)

        # Add the fixed demand
        subplot.fill_between(cumulative_demand.index, cumulative_demand, cumulative_demand + temporal_results_season.demand_fixed_MW, label="Demand", facecolor=colors.get("amber", 500))
        cumulative_demand += temporal_results_season.demand_fixed_MW

        # Add the electrolysis demand
        electrolysis_demand = temporal_results_season.demand_total_MW - temporal_results_season.demand_fixed_MW
        subplot.fill_between(cumulative_demand.index, cumulative_demand, cumulative_demand + electrolysis_demand, label="Electrolysis", facecolor=colors.get("amber", 600))
        cumulative_demand += electrolysis_demand

        # Add the pumped hydropower
        if show_hydropower:
            hydropower_pump_flow = -temporal_results_season.generation_total_hydropower_MW.clip(upper=0)
            subplot.fill_between(cumulative_demand.index, cumulative_demand, cumulative_demand + hydropower_pump_flow, label="Hydropower", facecolor=colors.get("sky", 600))
            cumulative_demand += hydropower_pump_flow

        # Add the storage charging
        storage_charging_flow = temporal_results_season.net_storage_flow_total_MW.clip(lower=0)
        subplot.fill_between(cumulative_demand.index, cumulative_demand, cumulative_demand + storage_charging_flow, label="Storage", facecolor=colors.get("red", 800))
        cumulative_demand += storage_charging_flow

        # Add the net export
        if show_import_export:
            net_export = temporal_results_season.net_export_MW.clip(lower=0)
            subplot.fill_between(cumulative_demand.index, cumulative_demand, cumulative_demand + net_export, label="Import/export", facecolor=colors.get("gray", 400))
            cumulative_demand += net_export

        # Add the curtailment
        subplot.fill_between(cumulative_demand.index, cumulative_demand, cumulative_demand + temporal_results_season.curtailed_MW, label="Curtailed", facecolor=colors.get("gray", 200))
        cumulative_demand += temporal_results_season.curtailed_MW

        # Generation
        # Create a series with the cumulative generation
        cumulative_generation = pd.Series(0, index=temporal_results_season.index)

        # Add the IRES generation
        subplot.fill_between(cumulative_generation.index, -cumulative_generation, -(cumulative_generation + temporal_results_season.generation_ires_MW), label="Intermittent renewables", facecolor=colors.get("amber", 300))
        cumulative_generation += temporal_results_season.generation_ires_MW

        # Add the hydropower turbine power
        if show_hydropower:
            hydropower_turbine_flow = temporal_results_season.generation_total_hydropower_MW.clip(lower=0)
            subplot.fill_between(cumulative_generation.index, -cumulative_generation, -(cumulative_generation + hydropower_turbine_flow), facecolor=colors.get("sky", 600))
            cumulative_generation += hydropower_turbine_flow

        # Add the storage discharging
        storage_discharging_flow = -temporal_results_season.net_storage_flow_total_MW.clip(upper=0)
        subplot.fill_between(cumulative_generation.index, -cumulative_generation, -(cumulative_generation + storage_discharging_flow), facecolor=colors.get("red", 900))
        cumulative_generation += storage_discharging_flow

        # Add the import
        if show_import_export:
            net_import = -temporal_results_season.net_export_MW.clip(upper=0)
            subplot.fill_between(cumulative_generation.index, -cumulative_generation, -(cumulative_generation + net_import), facecolor=colors.get("gray", 400))
            cumulative_generation += net_import

    # Show the plot
    week_plot.add_legend()
    week_plot.display()
    week_plot.download_button("average_week.png")

    # Show the table in an expander
    for season in season_data:
        with st.expander(f"Data points ({season})"):
            st.dataframe(season_data[season])
