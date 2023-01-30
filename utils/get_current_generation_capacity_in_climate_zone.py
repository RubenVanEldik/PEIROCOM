import utils
import validate


def get_current_generation_capacity_in_climate_zone(bidding_zone, generation_technology, *, config):
    """
    Calculate the current generation capacity per climate zone for a specific bidding zone and generation technology
    """
    assert validate.is_bidding_zone(bidding_zone)
    assert validate.is_technology(generation_technology)
    assert validate.is_config(config)

    # Get the country for this bidding zone
    country_code = utils.get_country_of_bidding_zone(bidding_zone)

    # Return zero if the generation technology has no current capacity specified for this country
    current_capacity = utils.get_country_property(country_code, "capacity.current").get(generation_technology)
    if current_capacity is None:
        return 0

    # Calculate the number of climate zones in the country
    climate_zone_count = 0
    for bidding_zone_in_country in utils.get_country_property(country_code, "bidding_zones"):
        temporal_data = utils.read_temporal_data(utils.path("input", "scenarios", config["scenario"], "bidding_zones", f"{bidding_zone_in_country}.csv"))
        climate_zone_count += len([column for column in temporal_data.columns if column.startswith(f"{generation_technology}_")])

    # Return zero if there are no climate zones in the country for this technology (otherwise there will be a division by zero error in the final return statement)
    if climate_zone_count == 0:
        return 0

    # Return the current generation capacity in the country divided by the number of climate zones in the country
    return current_capacity / climate_zone_count
