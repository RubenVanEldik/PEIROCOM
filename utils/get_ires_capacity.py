import pandas as pd

import utils
import validate


@utils.cache
def get_ires_capacity(output_directory, *, group=None, country_codes=None):
    """
    Return the (grouped) IRES capacity
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_aggregation_level(group, required=False)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)

    # If no countries are specified, set them to all countries modelled in this run
    if not country_codes:
        config = utils.read_yaml(output_directory / "config.yaml")
        country_codes = config["country_codes"]

    # Get the capacity for each market node
    ires_capacity = {}
    for market_node in utils.get_market_nodes_for_countries(country_codes):
        filepath = output_directory / "capacity" / "ires" / f"{market_node}.csv"
        ires_capacity[market_node] = utils.read_csv(filepath, index_col=0)

    # Return a dictionary with the capacity per market node DataFrame if not grouped
    if group is None:
        return ires_capacity

    # Return a DataFrame with the capacity per country
    if group == "country":
        ires_capacity_per_country = None
        for market_node, ires_capacity_local in ires_capacity.items():
            country_code = utils.get_country_of_market_node(market_node)
            if ires_capacity_per_country is None:
                ires_capacity_per_country = pd.DataFrame(columns=ires_capacity_local.columns)
            if country_code not in ires_capacity_per_country.index:
                ires_capacity_per_country.loc[country_code] = ires_capacity_local.sum()
            else:
                ires_capacity_per_country.loc[country_code] += ires_capacity_local.sum()
        return ires_capacity_per_country

    # Return a Series with the total IRES capacity per technology
    if group == "all":
        total_ires_capacity = None
        for ires_capacity_local in ires_capacity.values():
            if total_ires_capacity is None:
                total_ires_capacity = ires_capacity_local.sum()
            else:
                total_ires_capacity += ires_capacity_local.sum()
        return total_ires_capacity
