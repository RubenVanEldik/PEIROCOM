import pandas as pd
import streamlit as st

import utils

# Set the page config
st.set_page_config(page_title="Input data - PEIROCOM", page_icon="📂")


def run():
    data_type = st.sidebar.radio("Data type", ["countries", "technologies", "demand", "ires", "hydropower", "interconnections"], format_func=utils.format_str)

    if data_type == "countries":
        st.header("Countries")

        # Read the countries data and convert it to a DataFrame
        countries_df = pd.DataFrame(utils.read_yaml(utils.path("input", "countries.yaml")))

        # Split the capacity column into a new DataFrame
        capacity_df = pd.DataFrame(countries_df.capacity.values.tolist())
        # Get the index of the column
        column_index = countries_df.columns.get_loc("capacity")
        # Drop the column
        countries_df = countries_df.drop("capacity", axis=1)

        # Split the current and potential columns again and add the results to the original countries_df DataFrame
        for column_name in ["current", "potential"]:
            column_df = pd.DataFrame(capacity_df[column_name].values.tolist())
            # Add the sub columns to the DataFrame
            for sub_column_name in column_df.columns:
                countries_df.insert(column_index, f"{column_name}_{sub_column_name}", column_df[sub_column_name])
                column_index += 1

        # Remove the geographic units from the dataframe (if they exist)
        countries_df = countries_df.drop("included_geographic_units", axis=1, errors="ignore")
        countries_df = countries_df.drop("excluded_geographic_subunits", axis=1, errors="ignore")

        # Set the name as index and sort by the name
        countries_df = countries_df.set_index("name")
        countries_df = countries_df.sort_index()

        # Format the column names and show the DataFrame
        countries_df.columns = [utils.format_str(column_name) for column_name in countries_df.columns]
        st.dataframe(countries_df, height=600)

    if data_type == "technologies":
        technology_types = utils.read_yaml(utils.path("input", "technologies.yaml")).keys()
        for technology_type in technology_types:
            st.header(utils.format_str(f"{technology_type}_technologies"))

            # Read the technology data and convert it to a DataFrame
            technologies_df = pd.DataFrame(utils.get_technologies(technology_type=technology_type)).transpose()

            # Beautify the color column
            technologies_df["color"] = technologies_df["color"].apply(lambda obj: f"{obj['name'].capitalize()} ({obj['value']})")

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

    if data_type == "demand":
        # Select the model year
        scenario = st.sidebar.selectbox("Scenario", utils.get_scenarios())

        st.header("Demand")

        # Read the demand data
        demand_df = utils.read_temporal_data(utils.path("input", "scenarios", scenario, "demand.csv"))

        # Format the index and show the DataFrame
        demand_df.index = demand_df.index.strftime("%Y-%m-%d %H:%M UTC")
        st.dataframe(demand_df, height=600)

    if data_type == "ires":
        # Select the model year
        scenario = st.sidebar.selectbox("Scenario", utils.get_scenarios())

        # Select the market node
        input_path = utils.path("input", "scenarios", scenario, "ires")
        market_nodes = [filename.stem for filename in input_path.iterdir() if filename.suffix == ".csv"]
        market_node = st.sidebar.selectbox("Market node", market_nodes)

        st.header(f"IRES capacity factors {market_node}")

        # Read the temporal data
        ires_df = utils.read_temporal_data(input_path / f"{market_node}.csv")

        # Format the index and column names and show the DataFrame
        ires_df.index = ires_df.index.strftime("%Y-%m-%d %H:%M UTC")
        ires_df.columns = [utils.format_column_name(column_name) for column_name in ires_df.columns]
        st.dataframe(ires_df, height=600)

    if data_type == "hydropower":
        # Select the model year
        scenario = st.sidebar.selectbox("Scenario", utils.get_scenarios())

        hydropower_technologies = pd.DataFrame(utils.get_technologies(technology_type="hydropower")).columns
        hydropower_technology = st.sidebar.selectbox("Technology", hydropower_technologies, format_func=utils.format_str)

        # Select the market node
        input_path = utils.path("input", "scenarios", scenario, "hydropower", hydropower_technology)
        market_nodes = [filename.stem for filename in input_path.iterdir() if filename.suffix == ".csv"]
        market_node = st.sidebar.selectbox("Market node", market_nodes)

        st.header(f"Market node {market_node}")

        # Read and show the capacity data
        capacity = utils.read_csv(input_path / "capacity.csv", index_col=0).loc[market_node]
        col1, col2, col3 = st.columns(3)
        col1.metric("Turbine capacity", f"{capacity['turbine']:,.0f}MW")
        col2.metric("Pump capacity", f"{capacity['pump']:,.0f}MW")
        col3.metric("Reservoir capacity", f"{capacity['reservoir'] / 1000:,.0f}GWh")

        # Read the temporal data
        market_node_df = utils.read_temporal_data(input_path / f"{market_node}.csv")

        # Format the index and column names and show the DataFrame
        market_node_df.index = market_node_df.index.strftime("%Y-%m-%d %H:%M UTC")
        market_node_df.columns = [utils.format_column_name(column_name) for column_name in market_node_df.columns]
        st.dataframe(market_node_df, height=600)

    if data_type == "interconnections":
        # Select the model year
        scenario = st.sidebar.selectbox("Scenario", utils.get_scenarios())

        # Select the market node
        interconnection_type = st.sidebar.selectbox("Interconnection type", ["hvac", "hvdc"], format_func=utils.format_str)

        st.header(utils.format_str(f"{interconnection_type}_interconnection_capacities"))

        # Read the temporal data
        interconnection_typedf = utils.read_temporal_data(utils.path("input", "scenarios", scenario, "interconnections", f"{interconnection_type}.csv"), header=[0, 1])

        # Format the index and column names and show the DataFrame
        interconnection_typedf.index = interconnection_typedf.index.strftime("%Y-%m-%d %H:%M UTC")
        interconnection_typedf.columns = [f"{from_market_node} > {to_market_node}" for from_market_node, to_market_node in interconnection_typedf.columns]
        st.dataframe(interconnection_typedf, height=600)


run()
