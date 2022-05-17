import re
import streamlit as st

import utils
import validate


@st.experimental_memo(show_spinner=False)
def format_column_name(str):
    """
    Properly format any column name
    """
    assert validate.is_string(str)

    match = re.search("(.+)_(\w+)$", str)
    label = match.group(1)
    unit = match.group(2)

    # Replace all underscores with spaces and use the proper technology labels before capitalizing the first letter
    label = " ".join([(utils.labelize_technology(label_part, capitalize=False) if validate.is_technology(label_part) else label_part) for label_part in label.split("_")])
    label = label[0].upper() + label[1:]

    return f"{label} ({unit})"
