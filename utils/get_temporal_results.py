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

    # Get the temporal data for each bidding zone
    temporal_results = {}
    for bidding_zone in utils.get_bidding_zones_for_countries(country_codes):
        filepath = output_directory / "temporal_results" / f"{bidding_zone}.csv"
        temporal_results[bidding_zone] = utils.read_temporal_data(filepath)

        if temporal_results[bidding_zone].isnull().values.any():
            st.warning(f"Bidding zone {bidding_zone} contains NaN values")

    # Return all bidding zones individually if not grouped
    if group is None:
        return temporal_results

    # Return the sum of all bidding zones per country
    if group == "country":
        temporal_results_per_country = {}
        for bidding_zone, temporal_results_local in temporal_results.items():
            country_code = utils.get_country_of_bidding_zone(bidding_zone)
            if country_code not in temporal_results_per_country:
                # Create a new DataFrame for the country with the data from this bidding zone
                temporal_results_per_country[country_code] = temporal_results_local
            else:
                # Add the missing columns to the country's DataFrame
                missing_columns = [column_name for column_name in temporal_results_local.columns if column_name not in temporal_results_per_country[country_code].columns]
                temporal_results_per_country[country_code][missing_columns] = 0
                # Add the missing columns to the local DataFrame
                missing_columns_local = [column_name for column_name in temporal_results_per_country[country_code].columns if column_name not in temporal_results_local.columns]
                temporal_results_local[missing_columns_local] = 0
                # Add the data from the bidding zone to the existing country's DataFrame
                temporal_results_per_country[country_code] += temporal_results_local
        return temporal_results_per_country

    # Return the sum of all bidding zones
    if group == "all":
        total_temporal_results = None
        for temporal_results_local in temporal_results.values():
            if total_temporal_results is None:
                total_temporal_results = temporal_results_local.copy(deep=True)
            else:
                total_temporal_results += temporal_results_local
        return total_temporal_results
