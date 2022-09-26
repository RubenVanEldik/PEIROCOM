from datetime import datetime
import pandas as pd

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

    relevant_zones = _get_relevant_sheet_names(filepath, bidding_zone)
    for zone in relevant_zones:
        # Import the Excel sheet for a zone
        usecols_func = lambda col: col in ["Date", "Hour"] or isinstance(col, int)
        sheet = pd.read_excel(filepath, sheet_name=zone, index_col=[0, 1], skiprows=10, usecols=usecols_func)
        formatted_column_name = column_name.replace("{bidding_zone}", zone[2:])

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
            print(f"  - Column {formatted_column_name} contains NaN values and is not included")
            continue

        # Don't include the column if it only contains zeroes (only applicable to offshore wind in land-locked countries)
        if new_column.max() == 0.0:
            print(f"  - Column {formatted_column_name} contains only zeroes and is not included")
            continue

        if column_name != "demand_MW" and any(new_column.equals(data[data_column_name]) for data_column_name in data):
            print(f"  - Column {formatted_column_name} is exactly equal to another column and is not included")
            continue

        # Add the new column to the DataFrame or create a new data DataFrame if it doesn't exist yet
        if data is None:
            new_column.name = formatted_column_name
            data = new_column.to_frame()
        else:
            data[formatted_column_name] = new_column

    # Return the DataFrame with the newly created column
    return data


def preprocess_bidding_zone(bidding_zone, year):
    """
    Merge all data for a specific bidding zone and save it as a CSV file
    """
    assert validate.is_bidding_zone(bidding_zone)
    assert validate.is_model_year(year)

    # Import demand data
    filepath_demand = utils.path("input", "eraa", "Demand Data", f"Demand_TimeSeries_{year}_NationalEstimates.xlsx")
    data = _import_data(None, filepath_demand, bidding_zone=bidding_zone, column_name="demand_MW",)

    # Import PV data
    filepath_pv = utils.path("input", "eraa", "Climate Data", f"PECD_LFSolarPV_{year}_edition 2021.3.xlsx")
    data = _import_data(data, filepath_pv, bidding_zone=bidding_zone, column_name="pv_{bidding_zone}_cf",)

    # Import onshore wind data
    filepath_onshore = utils.path("input", "eraa", "Climate Data", f"PECD_Onshore_{year}_edition 2021.3.xlsx")
    data = _import_data(data, filepath_onshore, bidding_zone=bidding_zone, column_name="onshore_{bidding_zone}_cf",)

    # Import offshore wind data
    filepath_offshore = utils.path("input", "eraa", "Climate Data", f"PECD_Offshore_{year}_edition 2021.3.xlsx")
    data = _import_data(data, filepath_offshore, bidding_zone=bidding_zone, column_name="offshore_{bidding_zone}_cf",)

    # Store the data in a CSV file
    data.to_csv(utils.path("input", "bidding_zones", year, f"{bidding_zone}.csv"))
