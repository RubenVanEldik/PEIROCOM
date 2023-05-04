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


def typical_week(output_directory):
    """
    Show a chart with the typical week for each season
    """
    assert validate.is_directory_path(output_directory)

    st.title("📅 Typical week")

    # Ask for which countries the statistics should be shown
    st.sidebar.header("Options")
    config = utils.read_yaml(output_directory / "config.yaml")
    selected_country_codes = st.sidebar.multiselect("Countries", config["country_codes"], format_func=lambda country_code: utils.get_country_property(country_code, "name"))

    # Only show a message if the resolution is not 1 hour
    if config["resolution"] != "1H":
        st.warning("This analysis is only available for runs with a 1 hour resolution")
        return

    # Get temporal results for all countries
    temporal_results = utils.get_temporal_results(output_directory, group="all", country_codes=selected_country_codes)

    # Ask if the import and export should be shown in the chart
    show_import_export = st.sidebar.checkbox("Show import and export")

    # Set the unit to TW or GW when applicable
    unit = "MW"
    max_cumulative_value = (temporal_results.demand_total_MW + temporal_results.curtailed_MW + temporal_results.net_storage_flow_total_MW.clip(lower=0)).max()
    if max_cumulative_value > 10 ** 6:
        temporal_results /= 10 ** 6
        unit = "TW"
    elif max_cumulative_value > 10 ** 3:
        temporal_results /= 10 ** 3
        unit = "GW"

    # Initialize a plot with 4 subplots
    week_plot = chart.Chart(4, 1)

    # Loop over each of the four seasons
    season_dates = {"winter": list(range(1, 79)) + list(range(355, 366)), "spring": list(range(79, 172)), "summer": list(range(172, 266)), "autumn": list(range(266, 355))}
    season_data = {}
    for index, season in enumerate(season_dates.keys()):
        # Get the data for the current season
        temporal_results_season = temporal_results[temporal_results.index.dayofyear.isin(season_dates[season])]
        # Filter out all weeks that are not completely in this season
        week_numbers = pd.DataFrame({"year": temporal_results_season.index.year, "week": temporal_results_season.index.week})
        complete_weeks = week_numbers[week_numbers.groupby(['year', 'week']).cumcount() == 167].drop_duplicates()
        complete_weeks_in_year = complete_weeks["year"].astype(str) + "_" + complete_weeks["week"].astype(str)
        temporal_results_season = temporal_results_season[(temporal_results_season.index.year.astype(str) + "_" + temporal_results_season.index.week.astype(str)).isin(complete_weeks_in_year)]
        # Calculate the mean per hour
        temporal_results_season_mean = temporal_results_season.groupby([temporal_results_season.index.weekday, temporal_results_season.index.hour]).mean()
        temporal_results_season_errors = temporal_results_season.apply(lambda x: x - temporal_results_season_mean.loc[(x.name.weekday(), x.name.hour)], axis=1).pow(2)
        # Get the RMSE for each week
        temporal_results_rmse = temporal_results_season_errors.pow(2).groupby([temporal_results_season_errors.index.year, temporal_results_season_errors.index.week]).mean().pow(0.5)
        # Get the week number of the most typical week
        best_year, best_week = (temporal_results_rmse.demand_electricity_MW + temporal_results_rmse.generation_ires_MW + temporal_results_rmse.curtailed_MW).idxmin()
        # Select the typical week
        typical_week_data = temporal_results_season[(temporal_results_season.index.year == best_year) & (temporal_results_season.index.week == best_week)]
        typical_week_data.index = 24 * typical_week_data.index.weekday + typical_week_data.index.hour
        # Add the typical week data to the season data dictionary
        season_data[season] = typical_week_data

        # Set the title and format the ticks and labels of the subplot
        subplot = week_plot.axs[index]
        subplot.set_title(utils.format_str(season), rotation=90, x=1.025, y=0.3)
        # Set the limit of the x-axis
        subplot.set_xlim([0, 7 * 24])
        # Show the daily ticks, but don't show the labels
        subplot.set_xticks(range(0, 24 * 7, 24))
        subplot.tick_params(axis="x", which="major", labelbottom=False)  # changes apply to the x-axis  # both major and minor ticks are affected  # ticks along the bottom edge are off  # ticks along the top edge are off
        # Show the weekday labels as minor ticks, so they are between the day ticks
        subplot.set_xticks(range(12, 24 * 7, 24), ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], minor=True)
        subplot.tick_params(axis="x", which="minor", bottom=False, top=False)  # changes apply to the x-axis  # both major and minor ticks are affected  # ticks along the bottom edge are off  # ticks along the top edge are off
        # Show the tick labels on the y-axis as absolute
        subplot.set_yticklabels([f"{abs(x):.0f}" if abs(x) >= 100 else f"{abs(x):.1f}" if abs(x) >= 10 else f"{abs(x):.2f}" for x in subplot.get_yticks()])
        subplot.text(-0.10, 0.25, "From", transform=subplot.transAxes, horizontalalignment="center", verticalalignment="center", rotation=90)
        subplot.text(-0.10, 0.75, "To", transform=subplot.transAxes, horizontalalignment="center", verticalalignment="center", rotation=90)
        subplot.text(-0.14, 0.5, f"({unit})", transform=subplot.transAxes, horizontalalignment="center", verticalalignment="center", rotation=90)

        # Demand
        # Create a series with the cumulative demand
        cumulative_demand = pd.Series(0, index=typical_week_data.index)

        # Add the fixed demand
        _add_area(subplot, cumulative_demand, typical_week_data.demand_electricity_MW, label="Demand", color=colors.get("amber", 500))

        # Add the electrolysis demand
        electrolysis_demand = typical_week_data.demand_total_MW - typical_week_data.demand_electricity_MW
        _add_area(subplot, cumulative_demand, electrolysis_demand, label="Electrolysis", color=colors.get("amber", 600))

        # Add the pumped hydropower
        hydropower_pump_flow = -typical_week_data.generation_total_hydropower_MW.clip(upper=0)
        _add_area(subplot, cumulative_demand, hydropower_pump_flow, color=colors.get("sky", 600))

        # Add the storage charging
        storage_charging_flow = typical_week_data.net_storage_flow_total_MW.clip(lower=0)
        _add_area(subplot, cumulative_demand, storage_charging_flow, label="Storage", color=colors.get("red", 800))

        # Add the net export
        if show_import_export:
            net_export = typical_week_data.net_export_MW.clip(lower=0)
            _add_area(subplot, cumulative_demand, net_export, label="Import/export", color=colors.get("gray", 400))

        # Add the curtailment
        _add_area(subplot, cumulative_demand, typical_week_data.curtailed_MW, label="Curtailed", color=colors.get("gray", 300))

        # Generation
        # Create a series with the cumulative generation
        cumulative_generation = pd.Series(0, index=typical_week_data.index)

        # Add the nuclear generation
        _add_area(subplot, cumulative_generation, typical_week_data.get("generation_nuclear_MW"), reversed=True, label="Nuclear", color=colors.get("green", 700))

        # Add the wind generation
        wind_generation = pd.Series(0, index=typical_week_data.index)
        wind_generation += typical_week_data.get("generation_onshore_MW", default=0)
        wind_generation += typical_week_data.get("generation_offshore_MW", default=0)
        _add_area(subplot, cumulative_generation, wind_generation, reversed=True, label="Onshore and offshore wind", color=colors.get("amber", 300))

        # Add the solar PV generation
        _add_area(subplot, cumulative_generation, typical_week_data.get("generation_pv_MW"), reversed=True, label="Solar PV", color=colors.get("amber", 200))

        # Add the hydropower turbine power
        hydropower_turbine_flow = typical_week_data.generation_total_hydropower_MW.clip(lower=0)
        _add_area(subplot, cumulative_generation, hydropower_turbine_flow, reversed=True, label="Hydropower", color=colors.get("sky", 600))

        # Add the hydrogen turbines
        h2_to_electricity = pd.Series(0, index=typical_week_data.index)
        h2_to_electricity += typical_week_data.get("generation_h2_ccgt_MW", 0)
        h2_to_electricity += typical_week_data.get("generation_h2_gas_turbine_MW", 0)
        _add_area(subplot, cumulative_generation, h2_to_electricity, reversed=True, label="$\mathregular{H_2}$ turbines", color=colors.get("green", 500))

        # Add the storage discharging
        storage_discharging_flow = -typical_week_data.net_storage_flow_total_MW.clip(upper=0)
        _add_area(subplot, cumulative_generation, storage_discharging_flow, reversed=True, color=colors.get("red", 900))

        # Add the import
        if show_import_export:
            net_import = -typical_week_data.net_export_MW.clip(upper=0)
            _add_area(subplot, cumulative_generation, net_import, reversed=True, color=colors.get("gray", 400))

    # Show the plot
    week_plot.add_legend()
    week_plot.display()
    week_plot.download_button("typical_week.png")

    # Show the table in an expander
    for season in season_data:
        with st.expander(f"Data points ({season})"):
            st.dataframe(season_data[season])
