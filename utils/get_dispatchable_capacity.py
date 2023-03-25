import pandas as pd

import utils
import validate


@utils.cache
def get_dispatchable_capacity(output_directory, *, group=None, country_codes=None):
    """
    Return the (grouped) dispatchable capacity
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_aggregation_level(group, required=False)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)

    config = utils.read_yaml(output_directory / "config.yaml")

    # If no countries are specified, set them to all countries modelled in this run
    if not country_codes:
        country_codes = config["country_codes"]

    # Get the dispatchable capacity for the relevant market nodes
    dispatchable_capacity = utils.read_csv(output_directory / "capacity" / "dispatchable.csv", index_col=0)
    market_nodes = utils.get_market_nodes_for_countries(country_codes)
    dispatchable_capacity = dispatchable_capacity.loc[market_nodes]

    # Return the dispatchable capacity per market node if group is not specified
    if group is None:
        return dispatchable_capacity

    # Return a DataFrame with the dispatchable capacity per country
    if group == "country":
        dispatchable_capacity_per_country = pd.DataFrame(0, index=country_codes, columns=config["technologies"]["dispatchable"])
        for market_node in dispatchable_capacity.index:
            country_code = utils.get_country_of_market_node(market_node)
            dispatchable_capacity_per_country.loc[country_code] += dispatchable_capacity.loc[market_node]
        return dispatchable_capacity_per_country

    # Return a Series with the total dispatchable capacity per technology
    if group == "all":
        total_dispatchable_capacity = pd.Series(0, index=config["technologies"]["dispatchable"])
        for market_node in dispatchable_capacity.index:
            total_dispatchable_capacity += dispatchable_capacity.loc[market_node]
        return total_dispatchable_capacity
