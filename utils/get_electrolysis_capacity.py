import pandas as pd

import utils
import validate


@utils.cache
def get_electrolysis_capacity(output_directory, *, group=None, country_codes=None):
    """
    Return the (grouped) electrolysis capacity
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_aggregation_level(group, required=False)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)

    config = utils.read_yaml(output_directory / "config.yaml")

    # If no countries are specified, set them to all countries modelled in this run
    if not country_codes:
        country_codes = config["country_codes"]

    # Get the electrolysis capacity for the relevant market nodes
    electrolysis_capacity = utils.read_csv(output_directory / "capacity" / "electrolysis.csv", index_col=0)
    market_nodes = utils.get_market_nodes_for_countries(country_codes)
    electrolysis_capacity = electrolysis_capacity.loc[market_nodes]

    # Return the electrolysis capacity per market node if group is not specified
    if group is None:
        return electrolysis_capacity

    # Return a DataFrame with the electrolysis capacity per country
    if group == "country":
        electrolysis_capacity_per_country = pd.DataFrame(0, index=country_codes, columns=config["technologies"]["electrolysis"])
        for market_node in electrolysis_capacity.index:
            country_code = utils.get_country_of_market_node(market_node)
            electrolysis_capacity_per_country.loc[country_code] += electrolysis_capacity.loc[market_node]
        return electrolysis_capacity_per_country

    # Return a Series with the total electrolysis capacity per technology
    if group == "all":
        total_electrolysis_capacity = pd.Series(0, index=config["technologies"]["electrolysis"])
        for market_node in electrolysis_capacity.index:
            total_electrolysis_capacity += electrolysis_capacity.loc[market_node]
        return total_electrolysis_capacity
