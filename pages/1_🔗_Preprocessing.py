import streamlit as st

import preprocessing
import utils

# Set the page config
st.set_page_config(page_title="Preprocessing - PEIROCOM", page_icon="🔗")

# Define the scenarios
scenarios = [{"name": "ERAA 2025", "year": 2025}, {"name": "ERAA 2030", "year": 2030}]

# Show the download section
st.header("Download files")

# Check if the demand files are downloaded
demand_filenames = [utils.path("input", "eraa", "Demand Data", f"Demand_TimeSeries_{scenario['year']}_NationalEstimates.xlsx") for scenario in scenarios]
demand_files_are_downloaded = utils.validate_files(demand_filenames)
if st.button("Download demand data", disabled=demand_files_are_downloaded):
    demand_data_url = "https://eepublicdownloads.azureedge.net/clean-documents/sdc-documents/ERAA/Demand%20Dataset.7z"
    preprocessing.download_eraa_data(demand_data_url, demand_filenames)

# Check if the climate files are downloaded
climate_filenames = [utils.path("input", "eraa", "Climate Data", f"PECD_{generation_type}_{scenario['year']}_edition 2021.3.xlsx") for scenario in scenarios for generation_type in ["LFSolarPV", "Onshore", "Offshore"]]
climate_files_are_downloaded = utils.validate_files(climate_filenames)
if st.button("Download climate data", disabled=climate_files_are_downloaded):
    climate_data_url = "https://eepublicdownloads.entsoe.eu/clean-documents/sdc-documents/ERAA/Climate%20Data.7z"
    preprocessing.download_eraa_data(climate_data_url, climate_filenames)

# Check if the interconnection files are downloaded
interconnection_filenames = [utils.path("input", "eraa", "Transfer Capacities", f"Transfer Capacities_ERAA2021_TY{scenario['year']}.xlsx") for scenario in scenarios]
interconnection_files_are_downloaded = utils.validate_files(interconnection_filenames)
if st.button("Download interconnection data", disabled=interconnection_files_are_downloaded):
    interconnection_data_url = "https://eepublicdownloads.azureedge.net/clean-documents/sdc-documents/ERAA/Net%20Transfer%20Capacities.7z"
    preprocessing.download_eraa_data(interconnection_data_url, interconnection_filenames)

# Show the preprocessing section
st.header("Preprocess files")

# Download and preprocess the demand files
if st.button("Preprocess demand and IRES data", disabled=not demand_files_are_downloaded or not climate_files_are_downloaded):
    preprocessing.preprocess_demand_and_ires_data(scenarios)

# Download and preprocess the hydropower files
if st.button("Preprocess hydropower data", disabled=not climate_files_are_downloaded):
    preprocessing.preprocess_hydropower_data(scenarios)

# Download and preprocess the interconnection files
if st.button("Preprocess interconnection data", disabled=not interconnection_files_are_downloaded):
    preprocessing.preprocess_interconnection_data(scenarios)
