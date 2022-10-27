import geopandas as gpd

import utils
import validate


@utils.cache
def read_shapefile(filepath):
    """
    Returns the content of a .shp file as a geopandas DataFrame
    """
    assert validate.is_filepath(filepath, suffix=".shp", existing=True)

    # Read and return the file
    return gpd.read_file(filepath)
