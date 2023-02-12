import utils
import validate


def get_ires_potential_in_climate_zone(bidding_zone, ires_technology, *, config):
    """
    Calculate the maximum ires capacity per climate zone for a specific bidding zone and ires technology
    """
    assert validate.is_bidding_zone(bidding_zone)
    assert validate.is_technology(ires_technology)
    assert validate.is_config(config)

    # Get the country for this bidding zone
    country_code = utils.get_country_of_bidding_zone(bidding_zone)

    # Return infinite if the technology has no potential specified for this country
    ires_potential = utils.get_country_property(country_code, "capacity.potential").get(ires_technology)
    if ires_potential is None:
        return float("inf")

    # Return 0 if there is no potential for this technology in this bidding zone
    if ires_potential == 0:
        return 0

    # Calculate the number of climate zones in the country
    climate_zone_count = 0
    for bidding_zone_in_country in utils.get_country_property(country_code, "bidding_zones"):
        ires_data = utils.read_temporal_data(utils.path("input", "scenarios", config["scenario"], "ires", f"{bidding_zone_in_country}.csv"))
        climate_zone_count += len([column for column in ires_data.columns if column.startswith(f"{ires_technology}_")])

    # Return the potential in the country divided by the number of climate zones in the country
    return ires_potential / climate_zone_count
