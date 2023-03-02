import re

import utils
import validate


@utils.cache
def format_column_name(column_name):
    """
    Properly format any column name
    """
    assert validate.is_string(column_name)

    match = re.search(r"(.+)_(\w+)$", column_name)
    label = match.group(1)
    unit = match.group(2)

    # Replace all underscores with spaces and use the proper technology labels before capitalizing the first letter
    label = " ".join([(utils.format_technology(label_part, capitalize=False) if validate.is_technology(label_part) else label_part) for label_part in label.split("_")])
    label = label[0].upper() + label[1:]

    return f"{label} ({unit})"
