import streamlit as st

import utils
import validate


# Don't cache this, since the data is also cached when reading the CSV file and it's a lot of data
def get_temporal_results(output_directory, *, group=None, country_codes=None):
    """
    Return the (grouped) temporal results
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_aggregation_level(group, required=False)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)

    # If no countries are specified, set them to all countries modelled in this run
    if not country_codes:
        config = utils.read_yaml(output_directory / "config.yaml")
        country_codes = config["country_codes"]

    # Get the temporal data for each market node
    temporal_results = {}
    for market_node in utils.get_market_nodes_for_countries(country_codes):
        filepath = output_directory / "temporal" / "market_nodes" / f"{market_node}.csv"
        temporal_results[market_node] = utils.read_temporal_data(filepath)

        if temporal_results[market_node].isnull().values.any():
            st.warning(f"market node {market_node} contains NaN values")

    # Return all market nodes individually if not grouped
    if group is None:
        return temporal_results

    # Return the sum of all market nodes per country
    if group == "country":
        temporal_results_per_country = {}
        for market_node, temporal_results_local in temporal_results.items():
            country_code = utils.get_country_of_market_node(market_node)
            if country_code not in temporal_results_per_country:
                # Create a new DataFrame for the country with the data from this market node
                temporal_results_per_country[country_code] = temporal_results_local
            else:
                # Add the missing columns to the country's DataFrame
                missing_columns = [column_name for column_name in temporal_results_local.columns if column_name not in temporal_results_per_country[country_code].columns]
                temporal_results_per_country[country_code][missing_columns] = 0
                # Add the missing columns to the local DataFrame
                missing_columns_local = [column_name for column_name in temporal_results_per_country[country_code].columns if column_name not in temporal_results_local.columns]
                temporal_results_local[missing_columns_local] = 0
                # Add the data from the market node to the existing country's DataFrame
                temporal_results_per_country[country_code] += temporal_results_local
        return temporal_results_per_country

    # Return the sum of all market nodes
    if group == "all":
        total_temporal_results = None
        for temporal_results_local in temporal_results.values():
            if total_temporal_results is None:
                total_temporal_results = temporal_results_local.copy(deep=True)
            else:
                total_temporal_results += temporal_results_local
        return total_temporal_results
