import pandas as pd

import utils
import validate


# Don't cache this, since the data is also cached when reading the CSV file, and it's a lot of data
def get_mean_temporal_results(output_directory, *, group=None, country_codes=None):
    """
    Return the (grouped) mean temporal results
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_aggregation_level(group, required=False)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)

    # If no countries are specified, set them to all countries modelled in this run
    if not country_codes:
        config = utils.read_yaml(output_directory / "config.yaml")
        country_codes = config["country_codes"]

    # Get the data
    filepath = output_directory / "temporal" / "market_nodes" / "mean.csv"
    mean_temporal_results = utils.read_csv(filepath, index_col=0)

    # Filter the countries
    relevant_market_nodes = utils.get_market_nodes_for_countries(country_codes)
    mean_temporal_results = mean_temporal_results.loc[relevant_market_nodes]

    # Return all market nodes individually if not grouped
    if group is None:
        return mean_temporal_results

    # Return the sum of all market nodes per country
    if group == "country":
        mean_temporal_results_per_country = pd.DataFrame(0, columns=country_codes)
        for market_node in mean_temporal_results.index:
            # Add the data from the market node to the existing country's DataFrame
            country_code = utils.get_country_of_market_node(market_node)
            mean_temporal_results_per_country.loc[country_code] += mean_temporal_results.loc[market_node]
        return mean_temporal_results_per_country

    # Return the sum of all market nodes
    if group == "all":
        return mean_temporal_results.sum()
