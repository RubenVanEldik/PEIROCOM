import utils
import validate


@utils.cache
def get_hydropower_capacity(output_directory, *, group=None, country_codes=None):
    """
    Return the (grouped) hydropower capacity
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_aggregation_level(group, required=False)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)

    # If no countries are specified, set them to all countries modelled in this run
    if not country_codes:
        config = utils.read_yaml(output_directory / "config.yaml")
        country_codes = config["country_codes"]

    # Get the hydropower capacity for each bidding zone
    hydropower_capacity = {}
    for bidding_zone in utils.get_bidding_zones_for_countries(country_codes):
        filepath = output_directory / "capacity" / "hydropower" / f"{bidding_zone}.csv"
        hydropower_capacity[bidding_zone] = utils.read_csv(filepath, index_col=0)

    # Return a dictionary with the hydropower capacity per bidding zone DataFrame if not grouped
    if group is None:
        return hydropower_capacity

    # Return a dictionary with the hydropower capacity per country DataFrame
    if group == "country":
        hydropower_capacity_per_country = {}
        for bidding_zone, hydropower_capacity_local in hydropower_capacity.items():
            country_code = utils.get_country_of_bidding_zone(bidding_zone)
            if country_code not in hydropower_capacity_per_country:
                hydropower_capacity_per_country[country_code] = hydropower_capacity_local.copy(deep=True)
            else:
                hydropower_capacity_per_country[country_code] += hydropower_capacity_local
        return hydropower_capacity_per_country

    # Return a DataFrame with the total hydropower capacity per technology
    if group == "all":
        total_hydropower_capacity = None
        for bidding_zone, hydropower_capacity_local in hydropower_capacity.items():
            if total_hydropower_capacity is None:
                total_hydropower_capacity = hydropower_capacity_local.copy(deep=True)
            else:
                total_hydropower_capacity += hydropower_capacity_local
        return total_hydropower_capacity
