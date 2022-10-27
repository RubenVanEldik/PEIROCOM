import pyproj

import utils
import validate


@utils.cache
def calculate_distance(point1, point2):
    """
    Return the distance in meters between two points
    """
    assert validate.is_point(point1)
    assert validate.is_point(point2)

    geod = pyproj.Geod(ellps="WGS84")
    angle1, angle2, distance = geod.inv(point1.x, point1.y, point2.x, point2.y)

    return distance
