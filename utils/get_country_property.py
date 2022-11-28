import utils
import validate


def get_country_property(country_code, key, *, code_type="nuts2"):
    """
    Get a specific property of a country via its code
    """
    assert validate.is_country_code_type(code_type)
    assert validate.is_country_code(country_code, code_type=code_type)
    assert validate.is_string(key)

    # Read the countries
    countries = utils.read_yaml(utils.path("input", "countries.yaml"))

    # Get the specific country
    country = next(country for country in countries if country[code_type] == country_code)

    # Return the key from the country
    return country.get(key)
