import utils
import validate


def get_current_ires_capacity_in_climate_zone(market_node, ires_technology, *, config):
    """
    Calculate the current ires capacity per climate zone for a specific market node and ires technology
    """
    assert validate.is_market_node(market_node)
    assert validate.is_technology(ires_technology)
    assert validate.is_config(config)

    # Get the country for this market node
    country_code = utils.get_country_of_market_node(market_node)

    # Return zero if the IRES technology has no current capacity specified for this country
    current_capacity = utils.get_country_property(country_code, "capacity.current").get(ires_technology)
    if current_capacity is None:
        return 0

    # Calculate the number of climate zones in the country
    climate_zone_count = 0
    for market_node_in_country in utils.get_country_property(country_code, "market_nodes"):
        ires_data = utils.read_temporal_data(utils.path("input", "scenarios", config["scenario"], "ires", f"{market_node_in_country}.csv"))
        climate_zone_count += len([column for column in ires_data.columns if column.startswith(f"{ires_technology}_")])

    # Return zero if there are no climate zones in the country for this technology (otherwise there will be a division by zero error in the final return statement)
    if climate_zone_count == 0:
        return 0

    # Return the current capacity in the country divided by the number of climate zones in the country
    return current_capacity / climate_zone_count
