import pandas as pd

import utils
import validate


@utils.cache
def get_production_capacity(output_directory, *, group=None, country_codes=None):
    """
    Return the (grouped) production capacity
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_aggregation_level(group, required=False)
    assert validate.is_country_code_list(country_codes, code_type="nuts_2", required=False)

    # If no countries are specified, set them to all countries modelled in this run
    if not country_codes:
        config = utils.read_yaml(output_directory / "config.yaml")
        country_codes = config["country_codes"]

    # Get the production capacity for each bidding zone
    production_capacity = {}
    for bidding_zone in utils.get_bidding_zones_for_countries(country_codes):
        filepath = output_directory / "production_capacities" / f"{bidding_zone}.csv"
        production_capacity[bidding_zone] = utils.read_csv(filepath, index_col=0)

    # Return a dictionary with the production capacity per bidding zone DataFrame if not grouped
    if group is None:
        return production_capacity

    # Return a DataFrame with the production capacity per country
    if group == "country":
        production_capacity_per_country = None
        for bidding_zone, production_capacity_local in production_capacity.items():
            country_code = utils.get_country_of_bidding_zone(bidding_zone)
            if production_capacity_per_country is None:
                production_capacity_per_country = pd.DataFrame(columns=production_capacity_local.columns)
            if country_code not in production_capacity_per_country.index:
                production_capacity_per_country.loc[country_code] = production_capacity_local.sum()
            else:
                production_capacity_per_country.loc[country_code] += production_capacity_local.sum()
        return production_capacity_per_country

    # Return a Series with the total production capacity per technology
    if group == "all":
        total_production_capacity = None
        for bidding_zone, production_capacity_local in production_capacity.items():
            if total_production_capacity is None:
                total_production_capacity = production_capacity_local.sum()
            else:
                total_production_capacity += production_capacity_local.sum()
        return total_production_capacity
