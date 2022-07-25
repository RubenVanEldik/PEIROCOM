import streamlit as st

import utils
import validate


@st.experimental_memo(show_spinner=False)
def _read_and_map_export_limits(*, model_year, type, timestamps):
    """
    Read the export limits and map them to the given timestamps
    """
    assert validate.is_model_year(model_year)
    assert validate.is_interconnection_type(type)
    assert validate.is_series(timestamps)

    # Read the interconnection CSV file
    filepath = utils.path("input", "interconnections", model_year, f"{type}.csv")
    export_limits = utils.read_csv(filepath, parse_dates=True, index_col=0, header=[0, 1])

    # Resample the export limits if required
    if len(export_limits.index) != len(timestamps):
        resolution = timestamps[1] - timestamps[0]
        export_limits = export_limits.resample(resolution).mean()

    # Remap the export limits from the model year to the selected years
    return timestamps.apply(lambda timestamp: export_limits.loc[timestamp.replace(year=model_year)])


def get_export_limits(bidding_zone, *, config, type, index, direction="export"):
    """
    Find the relevant export limits for a bidding zone
    """
    assert validate.is_bidding_zone(bidding_zone)
    assert validate.is_config(config)
    assert validate.is_interconnection_type(type)
    assert validate.is_datetime_index(index)
    assert validate.is_interconnection_direction(direction)

    # Read and map the export limits
    export_limits = _read_and_map_export_limits(model_year=config["model_year"], type=type, timestamps=index.to_series())

    relevant_interconnections = []
    for zone in utils.get_bidding_zones_for_countries(config["country_codes"]):
        interconnection = (bidding_zone, zone) if direction == "export" else (zone, bidding_zone)
        if interconnection in export_limits.columns:
            relevant_interconnections.append(interconnection)
    return export_limits[relevant_interconnections]
