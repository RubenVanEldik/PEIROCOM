import pandas as pd
import streamlit as st

import utils
import validate


def _get_relevant_sheet_names(filepath, market_node):
    """
    Returns the relevant Excel sheets for a specific market node
    """
    assert validate.is_filepath(filepath)
    assert validate.is_market_node(market_node)

    def sheet_belongs_to_node(sheet, market_node):
        """
        Check if a specific sheet belongs to a market node
        """
        # Return True if it's an exact match
        if sheet == market_node:
            return True

        # If the country has only 1 market node, just check the first two letters
        countries = utils.read_yaml(utils.path("input", "countries.yaml"))
        if len([z for country in countries for z in country["market_nodes"] if z.startswith(market_node[:2])]) < 2:
            return sheet.startswith(market_node[:2])

        exceptions = {
            "DKKF": None,
            "FR01": "FR00",
            "FR02": "FR00",
            "FR03": "FR00",
            "FR04": "FR00",
            "FR05": "FR00",
            "FR06": "FR00",
            "FR07": "FR00",
            "FR08": "FR00",
            "FR09": "FR00",
            "FR10": "FR00",
            "FR11": "FR00",
            "FR12": "FR00",
            "FR13": "FR00",
            "FR14": "FR00",
            "GR01": "GR00",
            "GR02": "GR00",
            "LU00": None,
            "LUV1": None,
            "NOS1": "NOS0",
            "NOS2": "NOS0",
            "NOS3": "NOS0",
            "UK01": "UK00",
            "UK02": "UK00",
            "UK03": "UK00",
            "UK04": "UK00",
            "UK05": "UK00",
        }

        # Check if the market node is part of the exception list
        if exceptions.get(sheet) is not None:
            return exceptions.get(sheet) == market_node

        # Return false if it's not an exact match, the country has multiple market nodes, and it's not an exception
        return False

    # Return a sorted list of all relevant sheet names
    relevant_sheet_names = [sheet_name for sheet_name in pd.ExcelFile(filepath).sheet_names if sheet_belongs_to_node(sheet_name, market_node)]
    relevant_sheet_names.sort()
    return relevant_sheet_names


def _import_data(data, filepath, *, market_node, column_name=None):
    """
    Find and add all the relevant columns from a specific Excel file to the data DataFrame
    """
    assert validate.is_dataframe(data, required=False)
    assert validate.is_filepath(filepath)
    assert validate.is_market_node(market_node)
    assert validate.is_string(column_name)

    ires_nodes = _get_relevant_sheet_names(filepath, market_node)
    for ires_node in ires_nodes:
        # Import the Excel sheet for a IRES node
        sheet = pd.read_excel(filepath, sheet_name=ires_node, index_col=[0, 1], skiprows=10, usecols=lambda col: col in ["Date", "Hour"] or isinstance(col, int))
        formatted_column_name = column_name.replace("{ires_node}", ires_node)

        # Transform the sheet DataFrame to a Series with appropriate index
        new_column = pd.Series([], dtype="float64")
        for year_column in sheet.columns:
            data_year = sheet[year_column]
            data_year.index = utils.create_datetime_index(sheet.index, year_column)
            new_column = pd.concat([new_column, data_year])

        # Remove any rows that are not included in the data DataFrame
        if data is not None:
            new_column = new_column[data.index]

        # Don't include the column if it contains NaN values (only applicable to DEKF)
        if new_column.isna().any():
            print(f"  - Column {formatted_column_name} ({market_node}) contains NaN values and is not included")
            continue

        # Don't include the column if it only contains zeroes (only applicable to offshore wind in land-locked countries)
        if new_column.max() == 0.0:
            print(f"  - Column {formatted_column_name} ({market_node}) contains only zeroes and is not included")
            continue

        if column_name != "demand_MW" and data is not None and any(new_column.equals(data[data_column_name]) for data_column_name in data):
            print(f"  - Column {formatted_column_name} ({market_node}) is exactly equal to another column and is not included")
            continue

        # Add the new column to the DataFrame or create a new data DataFrame if it doesn't exist yet
        if data is None:
            new_column.name = formatted_column_name
            data = new_column.to_frame()
        else:
            data[formatted_column_name] = new_column

    # Return the DataFrame with the newly created column
    return data


def preprocess_demand_and_ires_data(scenarios):
    """
    Preprocess all market node data
    """
    assert validate.is_list_like(scenarios)

    # Get a list with all market nodes
    countries = utils.read_yaml(utils.path("input", "countries.yaml"))
    market_nodes = [market_node for country in countries for market_node in country["market_nodes"]]

    for scenario_index, scenario in enumerate(scenarios):
        # Define the directory variables
        climate_directory = utils.path("input", "eraa", "Climate Data")
        output_directory = utils.path("input", "scenarios", scenario["name"])
        ires_directory = output_directory / "ires"

        # Create the IRES directory if it does not exist yet
        if not ires_directory.is_dir():
            ires_directory.mkdir(parents=True)

        # Import the demand data
        demand_data = None
        for market_node_index, market_node in enumerate(market_nodes):
            with st.spinner(f"Preprocessing demand data for {market_node} ({scenario['name']})"):
                # Import demand data
                filepath_demand = utils.path("input", "eraa", "Demand Data", f"Demand_TimeSeries_{scenario['year']}_NationalEstimates.xlsx")
                demand_data = _import_data(demand_data, filepath_demand, market_node=market_node, column_name=market_node)
        demand_data.to_csv(output_directory / "demand.csv")

        # Import the IRES data
        for market_node_index, market_node in enumerate(market_nodes):
            with st.spinner(f"Preprocessing IRES data for {market_node} ({scenario['name']})"):
                # Import PV data
                filepath_pv = climate_directory / f"PECD_LFSolarPV_{scenario['year']}_edition 2021.3.xlsx"
                ires_data = _import_data(None, filepath_pv, market_node=market_node, column_name="pv_{ires_node}_cf")

                # Import onshore wind data
                filepath_onshore = climate_directory / f"PECD_Onshore_{scenario['year']}_edition 2021.3.xlsx"
                ires_data = _import_data(ires_data, filepath_onshore, market_node=market_node, column_name="onshore_{ires_node}_cf")

                # Import offshore wind data
                filepath_offshore = climate_directory / f"PECD_Offshore_{scenario['year']}_edition 2021.3.xlsx"
                ires_data = _import_data(ires_data, filepath_offshore, market_node=market_node, column_name="offshore_{ires_node}_cf")

                # Store the data in a CSV file
                ires_data.to_csv(ires_directory / f"{market_node}.csv")

    st.success("The demand and IRES data for all market nodes is successfully preprocessed")
