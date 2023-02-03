from datetime import datetime
import pandas as pd
import streamlit as st

import utils
import validate


def _format_export_limit_type(limit_type):
    """
    Format the export limit type to snake_case
    """
    assert validate.is_string(limit_type)

    if limit_type == "Gross Export limit":
        return "gross_export_limit"
    if limit_type == "Gross Import limit":
        return "gross_import_limit"
    if limit_type == "Country position (net exp. limit)":
        return "net_export_limit"
    if limit_type == "Country position (net imp. limit)":
        return "net_import_limit"


def preprocess_interconnection_data(scenarios):
    """
    Preprocess all interconnection data
    """
    assert validate.is_list_like(scenarios)

    for scenario_index, scenario in enumerate(scenarios):
        interconnection_types = ["hvac", "hvdc", "limits"]
        for interconnection_type_index, interconnection_type in enumerate(interconnection_types):
            with st.spinner(f"Preprocessing {utils.format_str(interconnection_type)} interconnections ({scenario['name']})"):
                # Get the interconnections filepath
                input_directory = utils.path("input", "eraa", "Transfer Capacities")
                output_directory = utils.path("input", "scenarios", scenario["name"], "interconnections")
                filepath = utils.path(input_directory, f"Transfer Capacities_ERAA2021_TY{scenario['year']}.xlsx")

                # Create the output directory if does not exist yet
                if not output_directory.is_dir():
                    output_directory.mkdir(parents=True)

                if interconnection_type == "hvac":
                    hvac = pd.read_excel(filepath, sheet_name="HVAC", index_col=[0, 1], skiprows=10, header=[0, 1])
                    hvac = hvac[sorted(hvac.columns)]
                    hvac.index = utils.create_datetime_index(hvac.index, scenario["year"])
                    hvac.to_csv(output_directory / "hvac.csv")

                if interconnection_type == "hvdc":
                    hvdc = pd.read_excel(filepath, sheet_name="HVDC", index_col=[0, 1], skiprows=10, header=[0, 1])
                    hvdc = hvdc[sorted(hvdc.columns)]
                    hvdc.index = utils.create_datetime_index(hvdc.index, scenario["year"])
                    hvdc.to_csv(output_directory / "hvdc.csv")

                if interconnection_type == "limits":
                    limits = pd.read_excel(filepath, sheet_name="Max limit", index_col=[0, 1], skiprows=9)
                    limits = limits.loc[:, ~limits.columns.str.contains("^Unnamed")]
                    limits = limits.drop(index=("Country Level Maximum NTC ", "UTC"))
                    limits.columns = pd.MultiIndex.from_tuples([(bidding_zone, _format_export_limit_type(limit_type)) for bidding_zone, limit_type in limits.columns.str.split(" - ")])
                    limits = limits[sorted(limits.columns)]
                    limits.index = utils.create_datetime_index(limits.index, scenario["year"])
                    limits.to_csv(output_directory / "limits.csv")

    st.success("The data for all interconnections is succesfully preprocessed")
