import pandas as pd

import utils
import validate


@utils.cache
def get_generation_capacity(output_directory, *, group=None, country_codes=None):
    """
    Return the (grouped) generation capacity
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_aggregation_level(group, required=False)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)

    # If no countries are specified, set them to all countries modelled in this run
    if not country_codes:
        config = utils.read_yaml(output_directory / "config.yaml")
        country_codes = config["country_codes"]

    # Get the generation capacity for each bidding zone
    generation_capacity = {}
    for bidding_zone in utils.get_bidding_zones_for_countries(country_codes):
        filepath = output_directory / "generation_capacities" / f"{bidding_zone}.csv"
        generation_capacity[bidding_zone] = utils.read_csv(filepath, index_col=0)

    # Return a dictionary with the generation capacity per bidding zone DataFrame if not grouped
    if group is None:
        return generation_capacity

    # Return a DataFrame with the generation capacity per country
    if group == "country":
        generation_capacity_per_country = None
        for bidding_zone, generation_capacity_local in generation_capacity.items():
            country_code = utils.get_country_of_bidding_zone(bidding_zone)
            if generation_capacity_per_country is None:
                generation_capacity_per_country = pd.DataFrame(columns=generation_capacity_local.columns)
            if country_code not in generation_capacity_per_country.index:
                generation_capacity_per_country.loc[country_code] = generation_capacity_local.sum()
            else:
                generation_capacity_per_country.loc[country_code] += generation_capacity_local.sum()
        return generation_capacity_per_country

    # Return a Series with the total generation capacity per technology
    if group == "all":
        total_generation_capacity = None
        for bidding_zone, generation_capacity_local in generation_capacity.items():
            if total_generation_capacity is None:
                total_generation_capacity = generation_capacity_local.sum()
            else:
                total_generation_capacity += generation_capacity_local.sum()
        return total_generation_capacity
