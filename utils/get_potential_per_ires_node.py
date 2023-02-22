import utils
import validate


def get_potential_per_ires_node(market_node, ires_technology, *, config):
    """
    Calculate the maximum ires capacity per IRES node for a specific market node and ires technology
    """
    assert validate.is_market_node(market_node)
    assert validate.is_technology(ires_technology)
    assert validate.is_config(config)

    # Get the country for this market node
    country_code = utils.get_country_of_market_node(market_node)

    # Return infinite if the technology has no potential specified for this country
    ires_potential = utils.get_country_property(country_code, "capacity.potential").get(ires_technology)
    if ires_potential is None:
        return float("inf")

    # Return 0 if there is no potential for this technology in this market node
    if ires_potential == 0:
        return 0

    # Calculate the number of IRES nodes in the country
    ires_node_count = 0
    for market_node_in_country in utils.get_country_property(country_code, "market_nodes"):
        ires_data = utils.read_temporal_data(utils.path("input", "scenarios", config["scenario"], "ires", f"{market_node_in_country}.csv"))
        ires_node_count += len([column for column in ires_data.columns if column.startswith(f"{ires_technology}_")])

    # Return the potential in the country divided by the number of IRES nodes in the country
    return ires_potential / ires_node_count
