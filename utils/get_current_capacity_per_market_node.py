import utils
import validate


def get_current_capacity_per_market_node(market_node, technology, *, config):
    """
    Calculate the current capacity per market node for a specific market node and technology
    """
    assert validate.is_market_node(market_node)
    assert validate.is_technology(technology)
    assert validate.is_config(config)

    # Get the country for this market node
    country_code = utils.get_country_of_market_node(market_node)

    # Return zero if the technology has no current capacity specified for this country
    current_capacity = utils.get_country_property(country_code, "capacity.current").get(technology)
    if current_capacity is None:
        return 0

    # If the current capacity is specified on bidding zone level, return this
    if isinstance(current_capacity, dict):
        return current_capacity.get(market_node)

    # Return the current capacity in the country divided by the number of market nodes in the country
    country = utils.get_country_of_market_node(market_node)
    market_node_count = len(utils.get_market_nodes_for_countries([country]))
    return current_capacity / market_node_count
