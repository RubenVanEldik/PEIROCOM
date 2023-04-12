import pandas as pd
import streamlit as st

import chart
import colors
import utils
import validate


def _add_area(subplot, existing_area, new_area, *, reversed=False, label=None, color):
    """
    Add an area to the weekly subplot
    """
    assert validate.is_series(existing_area)
    assert validate.is_series(new_area, required=False)
    assert validate.is_bool(reversed)
    assert validate.is_string(label, required=False)
    assert validate.is_color(color)

    # Set the direction
    direction = -1 if reversed else 1

    if new_area is not None and new_area.abs().max() > 0:
        # Calculate the lower and upper bound and update the existing area
        lower_bound = existing_area.copy()
        upper_bound = existing_area.copy() + new_area * direction
        existing_area += new_area * direction

        # Add the area to the plot
        subplot.fill_between(existing_area.index, lower_bound, upper_bound, label=label, facecolor=color)


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
        # Set the limit of the x-axis
        subplot.set_xlim([0, 7 * 24])
        # Show the daily ticks, but don't show the labels
        subplot.set_xticks(range(0, 24 * 7, 24))
        subplot.tick_params(axis="x", which="major", labelbottom=False)  # changes apply to the x-axis  # both major and minor ticks are affected  # ticks along the bottom edge are off  # ticks along the top edge are off
        # Show the weekday labels as minor ticks, so they are between the day ticks
        subplot.set_xticks(range(12, 24 * 7, 24), ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"], minor=True)
        subplot.tick_params(axis="x", which="minor", bottom=False, top=False)  # changes apply to the x-axis  # both major and minor ticks are affected  # ticks along the bottom edge are off  # ticks along the top edge are off
        # Show the tick labels on the y-axis as absolute
        subplot.set_yticklabels([round(abs(x)) for x in subplot.get_yticks()])
        subplot.text(-0.075, 0.25, "From", transform=subplot.transAxes, horizontalalignment="center", verticalalignment="center", rotation=90)
        subplot.text(-0.077, 0.75, "To", transform=subplot.transAxes, horizontalalignment="center", verticalalignment="center", rotation=90)
        subplot.text(-0.11, 0.5, f"({unit})", transform=subplot.transAxes, horizontalalignment="center", verticalalignment="center", rotation=90)

        # Demand
        # Create a series with the cumulative demand
        cumulative_demand = pd.Series(0, index=temporal_results_season.index)

        # Add the fixed demand
        _add_area(subplot, cumulative_demand, temporal_results_season.demand_electricity_MW, label="Demand", color=colors.get("amber", 500))

        # Add the electrolysis demand
        electrolysis_demand = temporal_results_season.demand_total_MW - temporal_results_season.demand_electricity_MW
        _add_area(subplot, cumulative_demand, electrolysis_demand, label="Electrolysis", color=colors.get("amber", 600))

        # Add the pumped hydropower
        hydropower_pump_flow = -temporal_results_season.generation_total_hydropower_MW.clip(upper=0)
        _add_area(subplot, cumulative_demand, hydropower_pump_flow, color=colors.get("sky", 600))

        # Add the storage charging
        storage_charging_flow = temporal_results_season.net_storage_flow_total_MW.clip(lower=0)
        _add_area(subplot, cumulative_demand, storage_charging_flow, label="Storage", color=colors.get("red", 800))

        # Add the net export
        if show_import_export:
            net_export = temporal_results_season.net_export_MW.clip(lower=0)
            _add_area(subplot, cumulative_demand, net_export, label="Import/export", color=colors.get("gray", 400))

        # Add the curtailment
        _add_area(subplot, cumulative_demand, temporal_results_season.curtailed_MW, label="Curtailed", color=colors.get("gray", 200))

        # Generation
        # Create a series with the cumulative generation
        cumulative_generation = pd.Series(0, index=temporal_results_season.index)

        # Add the nuclear generation
        _add_area(subplot, cumulative_generation, temporal_results_season.get("generation_nuclear_MW"), reversed=True, label="Nuclear", color=colors.get("green", 700))

        # Add the wind generation
        wind_generation = pd.Series(0, index=temporal_results_season.index)
        wind_generation += temporal_results_season.get("generation_onshore_MW", default=0)
        wind_generation += temporal_results_season.get("generation_offshore_MW", default=0)
        _add_area(subplot, cumulative_generation, wind_generation, reversed=True, label="Onshore and offshore wind", color=colors.get("amber", 300))

        # Add the solar PV generation
        _add_area(subplot, cumulative_generation, temporal_results_season.get("generation_pv_MW"), reversed=True, label="Solar PV", color=colors.get("amber", 200))

        # Add the hydropower turbine power
        hydropower_turbine_flow = temporal_results_season.generation_total_hydropower_MW.clip(lower=0)
        _add_area(subplot, cumulative_generation, hydropower_turbine_flow, reversed=True, label="Hydropower", color=colors.get("sky", 600))

        # Add the hydrogen turbines
        h2_to_electricity = pd.Series(0, index=temporal_results_season.index)
        h2_to_electricity += temporal_results_season.get("generation_h2_ccgt_MW", 0)
        h2_to_electricity += temporal_results_season.get("generation_h2_gas_turbine_MW", 0)
        _add_area(subplot, cumulative_generation, h2_to_electricity, reversed=True, label="$\mathregular{H_2}$ turbines", color=colors.get("green", 500))

        # Add the storage discharging
        storage_discharging_flow = -temporal_results_season.net_storage_flow_total_MW.clip(upper=0)
        _add_area(subplot, cumulative_generation, storage_discharging_flow, reversed=True, color=colors.get("red", 900))

        # Add the import
        if show_import_export:
            net_import = -temporal_results_season.net_export_MW.clip(upper=0)
            _add_area(subplot, cumulative_generation, net_import, reversed=True, color=colors.get("gray", 400))

    # Show the plot
    week_plot.add_legend()
    week_plot.display()
    week_plot.download_button("average_week.png")

    # Show the table in an expander
    for season in season_data:
        with st.expander(f"Data points ({season})"):
            st.dataframe(season_data[season])
