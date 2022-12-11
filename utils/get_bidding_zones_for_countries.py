import utils
import validate


@utils.cache
def get_bidding_zones_for_countries(country_codes):
    """
    Return a flat list with all bidding zones for a given list of countries
    """
    assert validate.is_country_code_list(country_codes, code_type="nuts2")

    # Get the countries
    countries = utils.read_yaml(utils.path("input", "countries.yaml"))

    # Add the bidding zones for each country to the bidding_zones list
    bidding_zones = []
    for country_code in country_codes:
        bidding_zones += utils.get_country_property(country_code, "bidding_zones")

    return bidding_zones
