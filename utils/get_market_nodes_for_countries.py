import utils
import validate


@utils.cache
def get_market_nodes_for_countries(country_codes):
    """
    Return a flat list with all market nodes for a given list of countries
    """
    assert validate.is_country_code_list(country_codes, code_type="nuts2")

    # Get the countries
    countries = utils.read_yaml(utils.path("input", "countries.yaml"))

    # Add the market nodes for each country to the market_nodes list
    market_nodes = []
    for country_code in country_codes:
        market_nodes += utils.get_country_property(country_code, "market_nodes")

    return market_nodes
