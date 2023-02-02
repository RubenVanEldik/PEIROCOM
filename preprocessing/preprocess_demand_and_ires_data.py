from datetime import datetime
import pandas as pd
import streamlit as st

import utils
import validate


def _get_relevant_sheet_names(filepath, bidding_zone):
    """
    Returns the relevant Excel sheets for a specific bidding zone
    """
    assert validate.is_filepath(filepath)
    assert validate.is_bidding_zone(bidding_zone)

    def sheet_belongs_to_zone(sheet, bidding_zone):
        """
        Check if a specific sheet belongs to a bidding zone
        """
        # Return True if its an exact match
        if sheet == bidding_zone:
            return True

        # If the country has only 1 bidding zone, just check the first two letters
        countries = utils.read_yaml(utils.path("input", "countries.yaml"))
        if len([z for country in countries for z in country["bidding_zones"] if z.startswith(bidding_zone[:2])]) < 2:
            return sheet.startswith(bidding_zone[:2])

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

        # Check if the bidding zone is part of the exception list
        if exceptions.get(sheet) is not None:
            return exceptions.get(sheet) == bidding_zone

        # Return false if its not an exact match, the country has multiple bidding zones and its not an exception
        return False

    # Return a sorted list of all relevant sheet names
    relevant_sheet_names = [sheet_name for sheet_name in pd.ExcelFile(filepath).sheet_names if sheet_belongs_to_zone(sheet_name, bidding_zone)]
    relevant_sheet_names.sort()
    return relevant_sheet_names


def _import_data(data, filepath, *, bidding_zone, column_name=None):
    """
    Find and add all the relevant columns from a specific Excel file to the data DataFrame
    """
    assert validate.is_dataframe(data, required=False)
    assert validate.is_filepath(filepath)
    assert validate.is_bidding_zone(bidding_zone)
    assert validate.is_string(column_name)

    climate_zones = _get_relevant_sheet_names(filepath, bidding_zone)
    for climate_zone in climate_zones:
        # Import the Excel sheet for a zone
        usecols_func = lambda col: col in ["Date", "Hour"] or isinstance(col, int)
        sheet = pd.read_excel(filepath, sheet_name=climate_zone, index_col=[0, 1], skiprows=10, usecols=usecols_func)
        formatted_column_name = column_name.replace("{climate_zone}", climate_zone)

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
            print(f"  - Column {formatted_column_name} ({bidding_zone}) contains NaN values and is not included")
            continue

        # Don't include the column if it only contains zeroes (only applicable to offshore wind in land-locked countries)
        if new_column.max() == 0.0:
            print(f"  - Column {formatted_column_name} ({bidding_zone}) contains only zeroes and is not included")
            continue

        if column_name != "demand_MW" and data is not None and any(new_column.equals(data[data_column_name]) for data_column_name in data):
            print(f"  - Column {formatted_column_name} ({bidding_zone}) is exactly equal to another column and is not included")
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
    Preprocess all bidding zone data
    """
    assert validate.is_list_like(scenarios)

    # Get a list with all bidding zones
    countries = utils.read_yaml(utils.path("input", "countries.yaml"))
    bidding_zones = [bidding_zone for country in countries for bidding_zone in country["bidding_zones"]]

    for scenario_index, scenario in enumerate(scenarios):
        # Define the directory variables
        demand_directory = utils.path("input", "eraa", "Demand Data")
        climate_directory = utils.path("input", "eraa", "Climate Data")
        output_directory = utils.path("input", "scenarios", scenario["name"])
        ires_directory = output_directory / "ires"

        # Create the IRES directory if does not exist yet
        if not ires_directory.is_dir():
            ires_directory.mkdir(parents=True)

        # Import the demand data
        demand_data = None
        for bidding_zone_index, bidding_zone in enumerate(bidding_zones):
            with st.spinner(f"Preprocessing demand data for {bidding_zone} ({scenario['name']})"):
                # Import demand data
                filepath_demand = utils.path("input", "eraa", "Demand Data", f"Demand_TimeSeries_{scenario['year']}_NationalEstimates.xlsx")
                demand_data = _import_data(demand_data, filepath_demand, bidding_zone=bidding_zone, column_name=bidding_zone)
        demand_data.to_csv(output_directory / "demand.csv")

        # Import the IRES data
        for bidding_zone_index, bidding_zone in enumerate(bidding_zones):
            with st.spinner(f"Preprocessing IRES data for {bidding_zone} ({scenario['name']})"):
                # Import PV data
                filepath_pv = climate_directory / f"PECD_LFSolarPV_{scenario['year']}_edition 2021.3.xlsx"
                ires_data = _import_data(None, filepath_pv, bidding_zone=bidding_zone, column_name="pv_{climate_zone}_cf")

                # Import onshore wind data
                filepath_onshore = climate_directory / f"PECD_Onshore_{scenario['year']}_edition 2021.3.xlsx"
                ires_data = _import_data(ires_data, filepath_onshore, bidding_zone=bidding_zone, column_name="onshore_{climate_zone}_cf")

                # Import offshore wind data
                filepath_offshore = climate_directory / f"PECD_Offshore_{scenario['year']}_edition 2021.3.xlsx"
                ires_data = _import_data(ires_data, filepath_offshore, bidding_zone=bidding_zone, column_name="offshore_{climate_zone}_cf")

                # Store the data in a CSV file
                ires_data.to_csv(ires_directory / f"{bidding_zone}.csv")

    st.success("The demand and IRES data for all bidding zones is succesfully preprocessed")
