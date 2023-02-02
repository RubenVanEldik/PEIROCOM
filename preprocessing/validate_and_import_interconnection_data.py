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


def validate_and_import_interconnection_data(scenarios):
    """
    Validate and preprocess all interconnection data
    """
    interconnection_progress = st.progress(0.0)

    for scenario_index, scenario in enumerate(scenarios):
        interconnection_types = ["hvac", "hvdc", "limits"]
        for interconnection_type_index, interconnection_type in enumerate(interconnection_types):
            interconnection_progress.progress(scenario_index / len(scenarios) + interconnection_type_index / len(scenarios) / len(interconnection_types))

            filename = utils.path("input", "scenarios", scenario["name"], "interconnections", f"{interconnection_type}.csv")
            if filename.is_file():
                is_valid_file = True
                data = utils.read_temporal_data(filename, header=[0, 1])

                if not validate.is_dataframe(data):
                    is_valid_file = False

                if len(data.columns) < 2 or not all(validate.is_interconnection_tuple(column) for column in data.columns):
                    is_valid_file = False

                # Check if the DataFrame has any missing timestamps
                start_date = pd.Timestamp(datetime.strptime(f"{scenario['year']}-01-01", "%Y-%m-%d").strftime("%Y-%m-%d 00:00:00+00:00"))
                end_date = pd.Timestamp(datetime.strptime(f"{scenario['year']}-12-31", "%Y-%m-%d").strftime("%Y-%m-%d 00:00:00+00:00"))
                required_timestamps = pd.date_range(start=start_date, end=end_date, freq="1H")
                missing_timestamps = required_timestamps.difference(data.index)
                has_missing_timestamps = len(missing_timestamps[~((missing_timestamps.month == 2) & (missing_timestamps.day == 29))]) != 0
                if has_missing_timestamps:
                    is_valid_file = False

                if not is_valid_file:
                    with st.spinner(f"Preprocessing {utils.format_str(interconnection_type)} interconnections ({scenario['name']})"):
                        # Get the interconnections filepath
                        input_directory = utils.path("input", "eraa", "Transfer Capacities")
                        output_directory = utils.path("input", "scenarios", scenario["name"], "interconnections")
                        filepath = utils.path(input_directory, f"Transfer Capacities_ERAA2021_TY{scenario['name']}.xlsx")

                        # Create the output directory if does not exist yet
                        if not output_directory.is_dir():
                            output_directory.mkdir(parents=True)

                        if interconnection_type == "hvac":
                            hvac = pd.read_excel(filepath, sheet_name="HVAC", index_col=[0, 1], skiprows=10, header=[0, 1])
                            hvac = hvac[sorted(hvac.columns)]
                            hvac.index = utils.create_datetime_index(hvac.index, scenario["name"])
                            hvac.to_csv(output_directory / "hvac.csv")

                        if interconnection_type == "hvdc":
                            hvdc = pd.read_excel(filepath, sheet_name="HVDC", index_col=[0, 1], skiprows=10, header=[0, 1])
                            hvdc = hvdc[sorted(hvdc.columns)]
                            hvdc.index = utils.create_datetime_index(hvdc.index, scenario["name"])
                            hvdc.to_csv(output_directory / "hvdc.csv")

                        if interconnection_type == "limits":
                            limits = pd.read_excel(filepath, sheet_name="Max limit", index_col=[0, 1], skiprows=9)
                            limits = limits.loc[:, ~limits.columns.str.contains("^Unnamed")]
                            limits = limits.drop(index=("Country Level Maximum NTC ", "UTC"))
                            limits.columns = pd.MultiIndex.from_tuples([(bidding_zone, _format_export_limit_type(limit_type)) for bidding_zone, limit_type in limits.columns.str.split(" - ")])
                            limits = limits[sorted(limits.columns)]
                            limits.index = utils.create_datetime_index(limits.index, scenario["name"])
                            limits.to_csv(output_directory / "limits.csv")

    st.success("The data for all interconnections is succesfully preprocessed")
