import pandas as pd
import streamlit as st

import analysis
import utils

# Set the page config
st.set_page_config(page_title="Input data - PEIROCOM", page_icon="📂")


def run():
    data_type = st.sidebar.radio("Data type", ["countries", "technologies", "bidding_zones", "interconnections"], format_func=utils.format_str)

    if data_type == "countries":
        st.header("Countries")

        # Read the countries data and convert it to a DataFrame
        countries_df = pd.DataFrame(utils.read_yaml(utils.path("input", "countries.yaml")))

        # Split the current and potential columns
        for column_name in ["current", "potential"]:
            # Split the column into a DataFrame
            column_df = pd.DataFrame(countries_df[column_name].values.tolist())
            # Get the index of the column
            column_index = countries_df.columns.get_loc(column_name)
            # Drop the column
            countries_df = countries_df.drop(column_name, axis=1)
            # Add the sub columns to the DataFrame
            for index, sub_column_name in enumerate(column_df.columns):
                countries_df.insert(column_index + index, f"{column_name}_{sub_column_name}", column_df[sub_column_name])

        # Remove the geographic units from the dataframe
        countries_df = countries_df.drop("included_geographic_units", axis=1)
        countries_df = countries_df.drop("excluded_geographic_subunits", axis=1)

        # Set the name as index and sort by the name
        countries_df = countries_df.set_index("name")
        countries_df = countries_df.sort_index()

        # Format the column names and show the DataFrame
        countries_df.columns = [utils.format_str(column_name) for column_name in countries_df.columns]
        st.dataframe(countries_df, height=600)

    if data_type == "technologies":
        for technology_type in ["production", "storage"]:
            st.header(utils.format_str(f"{technology_type}_technologies"))

            # Read the technology data and convert it to a DataFrame
            technologies_df = pd.DataFrame(utils.read_yaml(utils.path("input", "technologies", f"{technology_type}.yaml"))).transpose()

            for scenario_type in ["conservative", "moderate", "advanced"]:
                # technologies_df = technologies_df.drop(scenario_type)
                values = pd.DataFrame(technologies_df[scenario_type].values.tolist()).transpose()
                values.columns = technologies_df.index

                for value in values.index:
                    technologies_df[f"{scenario_type}_{value}"] = values.loc[value]

                technologies_df = technologies_df.drop(scenario_type, axis=1)

            # Format the column names and show the DataFrame
            technologies_df.columns = [utils.format_str(column_name) for column_name in technologies_df.columns]
            technologies_df.index = [utils.format_str(index) for index in technologies_df.index]
            st.dataframe(technologies_df)

    if data_type == "bidding_zones":
        # Select the model year
        scenario = st.sidebar.selectbox("Scenario", utils.get_scenarios())

        # Select the bidding zone
        input_path = utils.path("input", "scenarios", scenario, "bidding_zones")
        bidding_zones = [filename.stem for filename in input_path.iterdir() if filename.suffix == ".csv"]
        bidding_zone = st.sidebar.selectbox("Bidding zone", bidding_zones)

        st.header(f"Bidding zone {bidding_zone}")

        # Read the temporal data
        bidding_zone_df = utils.read_temporal_data(input_path / f"{bidding_zone}.csv")

        # Format the index and column names and show the DataFrame
        bidding_zone_df.index = bidding_zone_df.index.strftime("%Y-%m-%d %H:%M UTC")
        bidding_zone_df.columns = [utils.format_column_name(column_name) for column_name in bidding_zone_df.columns]
        st.dataframe(bidding_zone_df, height=600)

    if data_type == "interconnections":
        # Select the model year
        scenario = st.sidebar.selectbox("Scenario", utils.get_scenarios())

        # Select the bidding zone
        interconnection_type = st.sidebar.selectbox("Interconnection type", ["hvac", "hvdc"], format_func=utils.format_str)

        st.header(utils.format_str(f"{interconnection_type}_interconnection_capacities"))

        # Read the temporal data
        interconnection_typedf = utils.read_temporal_data(utils.path("input", "scenarios", scenario, "interconnections", f"{interconnection_type}.csv"), header=[0, 1])

        # Format the index and column names and show the DataFrame
        interconnection_typedf.index = interconnection_typedf.index.strftime("%Y-%m-%d %H:%M UTC")
        interconnection_typedf.columns = [f"{from_bidding_zone} > {to_bidding_zone}" for from_bidding_zone, to_bidding_zone in interconnection_typedf.columns]
        st.dataframe(interconnection_typedf, height=600)


run()
