import gurobipy as gp
import pandas as pd
import streamlit as st
import yaml

import validate


@st.experimental_memo(show_spinner=False)
def read_csv(filepath, **kwargs):
    """
    Read, cache, and return a CSV file
    """
    return pd.read_csv(filepath, **kwargs)


def read_hourly_data(filepath, *, start=None, end=None):
    """
    Returns the hourly data, if specified only for a specific date range
    """
    assert validate.is_filepath(filepath, suffix=".csv")
    assert validate.is_date(start, required=False)
    assert validate.is_date(end, required=False)

    hourly_data = read_csv(filepath, parse_dates=True, index_col=0)

    # Set the time to the beginning and end of the start and end date respectively
    start = start.strftime("%Y-%m-%d 00:00:00") if start else None
    end = end.strftime("%Y-%m-%d 23:59:59") if end else None

    # Return the hourly data
    return hourly_data[start:end]


@st.experimental_memo
def open_yaml(filepath):
    """
    Returns the content of a .yaml file as python list or dictionary
    """
    assert validate.is_filepath(filepath, suffix=".yaml")

    # Read and parse the file
    with open(filepath) as f:
        return yaml.load(f, Loader=yaml.SafeLoader)


def store_yaml(filepath, data):
    """
    Store a dictionary or list as .yaml file
    """
    assert validate.is_filepath(filepath, suffix=".yaml")
    assert validate.is_dict_or_list(data)

    # Read and parse the file
    with open(filepath, "w") as f:
        return yaml.dump(data, f, Dumper=yaml.Dumper)


def get_interconnections(bidding_zone, *, config, type, direction="export"):
    """
    Find the relevant interconnections for a bidding zone
    """
    assert validate.is_bidding_zone(bidding_zone)
    assert validate.is_config(config)
    assert validate.is_interconnection_type(type)
    assert validate.is_interconnection_direction(direction)

    filepath = f"../input/interconnections/{config['model_year']}/{type}.csv"
    interconnections = read_csv(filepath, parse_dates=True, index_col=0, header=[0, 1])

    relevant_interconnections = []
    for country in config["countries"]:
        for zone in country["zones"]:
            interconnection = (bidding_zone, zone) if direction == "export" else (zone, bidding_zone)
            if interconnection in interconnections:
                relevant_interconnections.append(interconnection)
    return interconnections[relevant_interconnections]


def convert_variables_recursively(data):
    """
    Store a dictionary or list as .yaml file
    """
    if type(data) is dict:
        for key, value in data.items():
            data[key] = convert_variables_recursively(value)
        return data
    elif type(data) is list:
        return [convert_variables_recursively(value) for value in data]
    elif type(data) is pd.core.frame.DataFrame:
        return data.applymap(convert_variables_recursively)
    elif type(data) is gp.Var:
        return data.X
    elif type(data) in [gp.LinExpr, gp.QuadExpr]:
        return data.getValue()
    return data
