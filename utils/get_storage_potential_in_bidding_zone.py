import utils
import validate


def get_storage_potential_in_bidding_zone(bidding_zone, storage_technology, *, config):
    """
    Calculate the maximum storage capacity for a specific bidding zone and generation technology
    """
    assert validate.is_bidding_zone(bidding_zone)
    assert validate.is_technology(storage_technology)
    assert validate.is_config(config)

    # Get the country for this bidding zone
    country_code = utils.get_country_of_bidding_zone(bidding_zone)

    # Return infinite if the storage technology has no potential specified for this country
    storage_potential = utils.get_country_property(country_code, "capacity.potential").get(storage_technology)
    if storage_potential is None:
        return float("inf")

    # Calculate the number of bidding zones zones in the country
    bidding_zone_count = len(utils.get_country_property(country_code, "bidding_zones"))

    # Return the storage potential in the country divided by the number of bidding zones in the country
    return storage_potential / bidding_zone_count
