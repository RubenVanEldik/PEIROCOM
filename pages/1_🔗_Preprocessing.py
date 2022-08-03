from datetime import datetime
import openpyxl
import pandas as pd
import streamlit as st

import utils
import validate


def _download_data(url, filepath, excel_filenames):
    """
    Download the ZIP file and convert the formulas in the Excel workbooks to values
    """
    assert validate.is_url(url)
    assert validate.is_filepath(filepath) or validate.is_directory_path(filepath)
    assert validate.is_filepath_list(excel_filenames)

    # Download file
    utils.download_file(url, filepath, unzip=True, show_progress=True)

    # Convert the Excel formulas to values
    with st.spinner("Converting the Excel formulas to values"):
        for filename in excel_filenames:
            openpyxl.load_workbook(filename, data_only=True).save(filename)

    # Rerun everything from the top
    st.experimental_rerun()


def _validate_and_import_bidding_zone_data():
    """
    Validate and preprocess all bidding zone data
    """
    # Get a list with all bidding zones
    countries = utils.read_yaml(utils.path("input", "countries.yaml"))
    bidding_zones = [bidding_zone for country in countries for bidding_zone in country["bidding_zones"]]

    # Initialize a progress bar
    bidding_zone_progress = st.progress(0.0)

    for year_index, year in enumerate(years):
        for bidding_zone_index, bidding_zone in enumerate(bidding_zones):
            bidding_zone_progress.progress(year_index / len(years) + bidding_zone_index / len(years) / len(bidding_zones))

            filename = utils.path("input", "bidding_zones", year, f"{bidding_zone}.csv")
            if filename.is_file():
                is_valid_file = True
                data = utils.read_csv(filename, parse_dates=True, index_col=0)

                if not validate.is_dataframe(data):
                    is_valid_file = False

                if not "demand_MW" in data.columns or len(data.columns) < 2:
                    is_valid_file = False

                # Check if the DataFrame has any missing timestamps
                start_date = pd.Timestamp(datetime.strptime("1982-01-01", "%Y-%m-%d").strftime("%Y-%m-%d 00:00:00+00:00"))
                end_date = pd.Timestamp(datetime.strptime("2016-12-31", "%Y-%m-%d").strftime("%Y-%m-%d 00:00:00+00:00"))
                required_timestamps = pd.date_range(start=start_date, end=end_date, freq="1H")
                missing_timestamps = required_timestamps.difference(data.index)
                has_missing_timestamps = len(missing_timestamps[~((missing_timestamps.month == 2) & (missing_timestamps.day == 29))]) != 0
                if has_missing_timestamps:
                    is_valid_file = False

            if not is_valid_file:
                with st.spinner(f"Preprocessing {bidding_zone} ({year})"):
                    utils.preprocess_bidding_zone(bidding_zone, year)

    bidding_zone_progress.empty()
    bidding_zone_placeholder.success("The data for all bidding zones is succesfully preprocessed")


def _validate_and_import_interconnection_data():
    """
    Validate and preprocess all interconnection data
    """
    interconnection_progress = st.progress(0.0)

    for year_index, year in enumerate(years):
        interconnection_types = ["hvac", "hvdc", "limits"]
        for interconnection_type_index, interconnection_type in enumerate(interconnection_types):
            interconnection_progress.progress(year_index / len(years) + interconnection_type_index / len(years) / len(interconnection_types))

            filename = utils.path("input", "interconnections", year, f"{interconnection_type}.csv")
            if filename.is_file():
                is_valid_file = True
                data = utils.read_csv(filename, parse_dates=True, index_col=0, header=[0, 1])

                if not validate.is_dataframe(data):
                    is_valid_file = False

                if len(data.columns) < 2 or not all(validate.is_interconnection_tuple(column) for column in data.columns):
                    is_valid_file = False

                # Check if the DataFrame has any missing timestamps
                start_date = pd.Timestamp(datetime.strptime(f"{year}-01-01", "%Y-%m-%d").strftime("%Y-%m-%d 00:00:00+00:00"))
                end_date = pd.Timestamp(datetime.strptime(f"{year}-12-31", "%Y-%m-%d").strftime("%Y-%m-%d 00:00:00+00:00"))
                required_timestamps = pd.date_range(start=start_date, end=end_date, freq="1H")
                missing_timestamps = required_timestamps.difference(data.index)
                has_missing_timestamps = len(missing_timestamps[~((missing_timestamps.month == 2) & (missing_timestamps.day == 29))]) != 0
                if has_missing_timestamps:
                    is_valid_file = False

            if not is_valid_file:
                with st.spinner(f"Preprocessing {utils.format_str(interconnection_type)} interconnections ({year})"):
                    utils.preprocess_interconnections(interconnection_type, year)

    interconnection_progress.empty()
    interconnection_placeholder.success("The data for all interconnections is succesfully preprocessed")


# Global variables
input_directory = utils.path("input", "eraa")
years = [2025, 2030]


# Download the demand files
st.header("Bidding zones")
demand_filenames = [utils.path(input_directory, "Demand Data", f"Demand_TimeSeries_{year}_NationalEstimates.xlsx") for year in years]
if not utils.validate_files(demand_filenames):
    st.warning("The demand files could not be found.")

    # Download the demand data when the button is clicked
    if st.button("Download demand data"):
        demand_data_url = "https://eepublicdownloads.azureedge.net/clean-documents/sdc-documents/ERAA/Demand%20Dataset.7z"
        _download_data(demand_data_url, input_directory, demand_filenames)

# Download the climate files
climate_filenames = [utils.path(input_directory, "Climate Data", f"PECD_{production_type}_{year}_edition 2021.3.xlsx") for year in years for production_type in ["LFSolarPV", "Onshore", "Offshore"]]
if not utils.validate_files(climate_filenames):
    st.warning("The climate files could not be found.")

    # Download the climate data when the button is clicked
    if st.button("Download climate data"):
        climate_data_url = "https://eepublicdownloads.entsoe.eu/clean-documents/sdc-documents/ERAA/Climate%20Data.7z"
        _download_data(climate_data_url, input_directory, climate_filenames)

# Check the bidding zone files
if utils.validate_files(demand_filenames) and utils.validate_files(climate_filenames):
    bidding_zone_placeholder = st.empty()
    if bidding_zone_placeholder.button("Validate and preprocess bidding zone data"):
        _validate_and_import_bidding_zone_data()


# Check and download the interconnection files
st.header("Interconnections")
interconnection_filenames = [utils.path(input_directory, "Transfer Capacities", f"Transfer Capacities_ERAA2021_TY{year}.xlsx") for year in years]
if not utils.validate_files(interconnection_filenames):
    st.warning("The interconnection files could not be found.")

    # Download the interconnection data when the button is clicked
    if st.button("Download interconnection data"):
        interconnection_data_url = "https://eepublicdownloads.azureedge.net/clean-documents/sdc-documents/ERAA/Net%20Transfer%20Capacities.7z"
        _download_data(interconnection_data_url, input_directory, interconnection_filenames)
else:
    interconnection_placeholder = st.empty()
    if interconnection_placeholder.button("Validate and preprocess interconnection data"):
        _validate_and_import_interconnection_data()
