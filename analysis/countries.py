import re

import pandas as pd
import streamlit as st

import chart
import colors
import utils
import validate


def _select_data(output_directory, *, name):
    """
    Select the source of the data and the specific columns and aggregation type
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_string(name)

    # Get the source of the data
    col1, col2 = st.sidebar.columns(2)
    data_source_options = ["Statistics", "Temporal results", "Country info", "IRES capacity", "Storage capacity (energy)", "Storage capacity (power)"]
    data_source = col1.selectbox(name.capitalize(), data_source_options)

    # Read the config file
    config = utils.read_yaml(output_directory / "config.yaml")

    if data_source == "Statistics":
        # Get the type of statistic
        statistic_type_options = ["firm_lcoe", "unconstrained_lcoe", "premium", "relative_curtailment", "self_sufficiency"]
        statistic_type = col2.selectbox("Type", statistic_type_options, format_func=utils.format_str, key=name)
        statistic_method = getattr(utils.previous_run, statistic_type)

        # Calculate the statistics for each country and convert them into a Series
        return pd.Series({country_code: statistic_method(output_directory, country_codes=[country_code]) for country_code in config["country_codes"]})

    if data_source == "Temporal results":
        # Get the temporal results
        temporal_results = utils.get_temporal_results(output_directory, group="country")

        # Merge the DataFrames on a specific column
        relevant_columns = utils.find_common_columns(temporal_results)
        column_names = col2.multiselect("Column", relevant_columns, format_func=utils.format_column_name, key=name)

        if len(column_names) == 0:
            return

        # Merge all temporal results
        data = pd.DataFrame()
        for name in column_names:
            data[name] = utils.merge_dataframes_on_column(temporal_results, name).mean()
        return data

    if data_source == "Country info":
        # Get the country information
        country_info = utils.read_yaml(utils.path("input", "countries.yaml"))

        # Select the numeric parameter that should be shown
        country_parameters = list(set([parameter for country in country_info for parameter in country if isinstance(country[parameter], (int, float))]))
        country_parameters += list(set([f"capacity.current.{technology}" for country in country_info for technology in country["capacity"]["current"]]))
        country_parameters += list(set([f"capacity.potential.{technology}" for country in country_info for technology in country["capacity"]["potential"]]))
        selected_parameter = col2.selectbox("Parameter", country_parameters, format_func=lambda key: utils.format_str(key.replace("capacity.", "").replace(".", " ")), key=name)

        # Return a Series with the potential per country for the selected technology
        data = pd.Series({country["nuts2"]: utils.get_nested_key(country, selected_parameter, default=0) for country in country_info if country["nuts2"] in config["country_codes"]})
        data[data == 0] = None
        return data

    if data_source == "IRES capacity":
        # Get the IRES capacity
        ires_capacity = utils.get_ires_capacity(output_directory, group="country")

        # Get the specific technologies
        selected_ires_types = col2.multiselect("Type", ires_capacity.columns, format_func=utils.format_technology, key=name)

        # Return the sum the capacities of all selected technologies
        if selected_ires_types:
            return ires_capacity[selected_ires_types]

    storage_capacity_match = re.search(r"Storage capacity \((.+)\)$", data_source)
    if storage_capacity_match:
        energy_or_power = storage_capacity_match.group(1)

        # Get the storage capacity
        storage_capacity = utils.get_storage_capacity(output_directory, group="country")

        # Create a DataFrame with all storage (energy or power) capacities
        storage_capacity_aggregated = None
        for country_code in storage_capacity:
            if storage_capacity_aggregated is None:
                storage_capacity_aggregated = pd.DataFrame(columns=storage_capacity[country_code].index)
            storage_capacity_aggregated.loc[country_code] = storage_capacity[country_code][energy_or_power]

        # Get the specific technologies
        selected_storage_types = col2.multiselect("Type", storage_capacity_aggregated.columns, format_func=utils.format_technology, key=name)

        # Return the sum the capacities of all selected technologies
        if selected_storage_types:
            return storage_capacity_aggregated[selected_storage_types]


def countries(output_directory):
    """
    Show a choropleth map for all countries modeled in a run
    """
    assert validate.is_directory_path(output_directory)

    st.title("🎌 Countries")

    st.sidebar.header("Options")

    # Check if the data should be relative and get the numerator data
    relative = st.sidebar.checkbox("Relative")
    numerator = _select_data(output_directory, name="numerator")

    # Set 'data' to the numerator, else get de denominator and divide the numerator with it
    if not relative:
        data = numerator
    else:
        denominator = _select_data(output_directory, name="denominator")

        if numerator is not None and denominator is not None:
            # Sum the denominator if it's a DataFrame
            if validate.is_dataframe(denominator):
                denominator = denominator.sum(axis=1)

            data = numerator.divide(denominator, axis=0)
        else:
            data = None

    # Only show the map if the data has been selected
    if data is not None:
        # Get the label for the color bar
        label = st.sidebar.text_input("Label")

        # Show zero values as white areas
        exclude_zero_values = st.sidebar.checkbox("Exclude zero values")
        if exclude_zero_values:
            data.loc[data == 0] = None

        # Ask if the data should be shown on a map if all countries have geographic units defined
        all_countries_have_geographic_units = all(len(utils.get_country_property(country_code, "included_geographic_units")) > 0 for country_code in data.index)
        show_as_map = all_countries_have_geographic_units and st.sidebar.checkbox("Show countries on a map")

        # Ask if the data should be formatted as a percentage
        format_percentage = st.sidebar.checkbox("Show as percentage")

        # Remove excluded countries from the data
        excluded_country_codes = st.sidebar.multiselect("Exclude countries", options=data.index, format_func=lambda nuts2: utils.get_country_property(nuts2, "name"))
        data = data[~data.index.isin(excluded_country_codes)]

        # Get the units for the color bar
        units = {10 ** -9: "Billionth", 10 ** -6: "Millionth", 10 ** -3: "Thousandth", 1: "One", 10 ** 3: "Thousand", 10 ** 6: "Million", 10 ** 9: "Billion"}
        unit = st.sidebar.select_slider("Format units", units.keys(), value=1, format_func=lambda key: units[key])
        data = data / unit

        # Create and show the map
        if show_as_map:
            # If data is still a DataFrame, convert the single column DataFrame to a series
            if validate.is_dataframe(data):
                data = data.sum(axis=1)

            countries_map = chart.Map(data, label=label, format_percentage=format_percentage)
            countries_map.display()
            countries_map.download_button("countries.png")
        else:
            # Drop the non-existing values when zero values are excluded
            if exclude_zero_values:
                data = data.dropna()

            # Initialize bar chart
            bar_chart = chart.Chart(ylabel=label)
            bar_width = 0.8

            data = data.sort_index(key=lambda x: [utils.get_country_property(xx, "name") for xx in x])

            if validate.is_dataframe(data):
                bottom = 0
                for column_name in data:
                    color = colors.technology(column_name) if validate.is_technology(column_name) else colors.random()
                    bar_chart.axs.bar(data.index, data[column_name], bar_width, bottom=bottom, label=utils.format_str(column_name), color=color)
                    bottom += data[column_name]
                bar_chart.add_legend()
            else:
                bar_chart.axs.bar(data.index, data, bar_width, color=colors.primary())

            if format_percentage:
                bar_chart.format_yticklabels("{:,.0%}")

            country_names = ["Bosnia and Herz." if country_code == "BA" else utils.get_country_property(country_code, "name") for country_code in data.index]
            bar_chart.axs.set_xticks(bar_chart.axs.get_xticks())  # Required to not get a warning message when using 'set_xticklabels'
            bar_chart.axs.set_xticklabels(country_names, rotation=90)
            padding = bar_width - (1 - bar_width) / 2
            bar_chart.axs.set_xlim(-padding, len(data.index) - (1 - padding))
            bar_chart.display()
            bar_chart.download_button("countries.png")

        # Show the table in an expander
        with st.expander("Data points"):
            data.index = [utils.get_country_property(country_code, "name") for country_code in data.index]
            st.table(data)
