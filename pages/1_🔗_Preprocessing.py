import streamlit as st

import preprocessing
import utils


# Set the page config
st.set_page_config(page_title="Preprocessing - PEIROCOM", page_icon="🔗")

# Global variables
input_directory = utils.path("input", "eraa")
scenarios = [{"name": "ERAA 2025", "year": 2025}, {"name": "ERAA 2030", "year": 2030}]


# Download and preprocess the demand files
st.header("Bidding zones")
demand_filenames = [utils.path(input_directory, "Demand Data", f"Demand_TimeSeries_{scenario['year']}_NationalEstimates.xlsx") for scenario in scenarios]
climate_filenames = [utils.path(input_directory, "Climate Data", f"PECD_{generation_type}_{scenario['year']}_edition 2021.3.xlsx") for scenario in scenarios for generation_type in ["LFSolarPV", "Onshore", "Offshore"]]
if not utils.validate_files(demand_filenames):
    st.warning("The demand files could not be found.")

    # Download the demand data when the button is clicked
    if st.button("Download demand data"):
        demand_data_url = "https://eepublicdownloads.azureedge.net/clean-documents/sdc-documents/ERAA/Demand%20Dataset.7z"
        preprocessing.download_eraa_data(demand_data_url, input_directory, demand_filenames)
elif not utils.validate_files(climate_filenames):
    st.warning("The climate files could not be found.")

    # Download the climate data when the button is clicked
    if st.button("Download climate data"):
        climate_data_url = "https://eepublicdownloads.entsoe.eu/clean-documents/sdc-documents/ERAA/Climate%20Data.7z"
        preprocessing.download_eraa_data(climate_data_url, input_directory, climate_filenames)
else:
    bidding_zone_placeholder = st.empty()
    if bidding_zone_placeholder.button("Validate and preprocess bidding zone data"):
        preprocessing.validate_and_import_bidding_zone_data(scenario)


# Download and preprocess the interconnection files
st.header("Interconnections")
interconnection_filenames = [utils.path(input_directory, "Transfer Capacities", f"Transfer Capacities_ERAA2021_TY{scenario['year']}.xlsx") for scenario in scenarios]
if not utils.validate_files(interconnection_filenames):
    st.warning("The interconnection files could not be found.")

    # Download the interconnection data when the button is clicked
    if st.button("Download interconnection data"):
        interconnection_data_url = "https://eepublicdownloads.azureedge.net/clean-documents/sdc-documents/ERAA/Net%20Transfer%20Capacities.7z"
        preprocessing.download_eraa_data(interconnection_data_url, input_directory, interconnection_filenames)
else:
    interconnection_placeholder = st.empty()
    if interconnection_placeholder.button("Validate and preprocess interconnection data"):
        preprocessing.validate_and_import_interconnection_data(scenarios)
