import utils
import validate


def get_potential_per_ires_node(market_node, ires_technology, *, mean_demand, config):
    """
    Calculate the maximum ires capacity per IRES node for a specific market node and ires technology
    """
    assert validate.is_market_node(market_node)
    assert validate.is_technology(ires_technology)
    assert validate.is_series(mean_demand)
    assert validate.is_config(config)

    # Get the country for this market node
    country_code = utils.get_country_of_market_node(market_node)

    # Return infinite if the technology has no potential specified for this country
    ires_potential_country = utils.get_country_property(country_code, "capacity.potential").get(ires_technology)
    if ires_potential_country is None:
        return float("inf")

    # Calculate the potential in the market node based upon the demand of the market node compared to the potential of the country
    demand_factor = mean_demand[market_node] / sum([mean_demand[market_node_in_country] for market_node_in_country in utils.get_country_property(country_code, "market_nodes")])
    ires_potential_market_node = demand_factor * ires_potential_country

    # Calculate the number of IRES nodes in this market node
    ires_data = utils.read_temporal_data(utils.path("input", "scenarios", config["scenario"], "ires", f"{market_node}.csv"))
    ires_nodes_in_market_node_count = len([column for column in ires_data.columns if column.startswith(f"{ires_technology}_")])

    # Return 0 if ires_nodes_in_market_node_count is 0 otherwise a division by 0 error might occur
    if ires_nodes_in_market_node_count == 0:
        return 0

    # Return the potential of the market node divided by the number of IRES nodes in the market node (with a minimum of the currently installed capacity (only required for Italy))
    current_capacity_ires_node = utils.get_current_capacity_per_ires_node(market_node, ires_technology, config=config)
    potential_capacity_ires_node = ires_potential_market_node / ires_nodes_in_market_node_count
    return max(current_capacity_ires_node, potential_capacity_ires_node)
