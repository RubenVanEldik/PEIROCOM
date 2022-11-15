import utils
import validate


def get_geometries_of_countries(country_codes):
    """
    Return a geopandas DataFrame with the geometries for the specified countries
    """
    assert validate.is_country_code_list(country_codes, code_type="nuts_2")

    # Get a list of all included geographic units and all excluded geographic sub-units
    included_geographic_units = []
    excluded_geographic_subunits = []
    countries = utils.read_yaml(utils.path("input", "countries.yaml"))
    relevant_countries = [country for country in countries if country["nuts_2"] in country_codes]
    for country in relevant_countries:
        included_geographic_units.extend(country.get("included_geographic_units", []))
        excluded_geographic_subunits.extend(country.get("excluded_geographic_subunits", []))

    # Get a Geopandas DataFrame with the relevant rows
    map_df = utils.read_shapefile(utils.path("input", "gis", "ne_10m_admin_0_map_subunits.shp"))
    map_df = map_df[map_df.GU_A3.isin(included_geographic_units)]
    map_df = map_df[~map_df.SU_A3.isin(excluded_geographic_subunits)]

    # Merge the regions for each country and set the nuts_2 country code as the index
    map_df = map_df.dissolve(by="SOV_A3")
    map_df["nuts_2"] = map_df.apply(lambda row: utils.get_country_property(row.ADM0_A3, "nuts_2", code_type="alpha_3"), axis=1)
    map_df = map_df.set_index("nuts_2")

    # Return a DataFrame with only the 'geometry' column
    return map_df[["geometry"]]
