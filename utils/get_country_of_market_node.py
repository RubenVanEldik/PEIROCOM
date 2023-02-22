import utils
import validate


@utils.cache
def get_country_of_market_node(market_node):
    """
    Find to which country a market node belongs to
    """
    assert validate.is_market_node(market_node)

    countries = utils.read_yaml(utils.path("input", "countries.yaml"))
    return next(country["nuts2"] for country in countries if market_node in country["market_nodes"])
