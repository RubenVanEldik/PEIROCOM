import re

import utils
import validate


@utils.cache
def format_resolution(resolution):
    """
    Format the resolution
    """
    assert validate.is_resolution(resolution)

    # Get the magnitude and type from the resolution string
    groups = re.search(r"^(\d+)([A-Z]+)$", resolution)

    # Return the original resolution string if the regex did not match
    if groups is None:
        return resolution

    # Get the magnitude and type
    magnitude = groups[1]
    resolution_type = groups[2]

    # Return the formatted resolution for hours, days, and weeks
    if resolution_type == "H":
        return f"{magnitude} hour{'' if int(magnitude) == 1 else 's'}"
    if resolution_type == "D":
        return f"{magnitude} day{'' if int(magnitude) == 1 else 's'}"
    if resolution_type == "W":
        return f"{magnitude} week{'' if int(magnitude) == 1 else 's'}"

    # Return the original resolution string if the type is not hour, day, or week
    return resolution
