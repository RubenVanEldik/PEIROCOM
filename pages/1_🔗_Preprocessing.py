import pandas as pd
import streamlit as st

import utils

# Set the page config
st.set_page_config(page_title="Preprocessing - PEIROCOM", page_icon="🔗")

# Get the solar PV capacity factors
pv_capacity_factors = utils.read_temporal_data(utils.path("input", "lombok_raw", "cf_new.csv"), timezone="UTC")
pv_capacity_factors = pv_capacity_factors.clip(lower=0)
pv_capacity_factors = pv_capacity_factors[~((pv_capacity_factors.index.month == 2) & (pv_capacity_factors.index.day == 29))]

# Get the transformer data
transformer_data = utils.read_temporal_data(utils.path("input", "lombok_raw", "transformer_data.csv"))

# Change the year to 2022 so the 2021 December days are used in December 2022
transformer_data.index = transformer_data.index.map(lambda t: t.replace(year=2022))

# Create a completeness DataFrame and a function to calculate it
completeness_share = pd.DataFrame()
calculate_completeness = lambda data: 1 - (len(transformer_data.index) - transformer_data.count()) / len(transformer_data.index)

# Calculate the completeness of the dataset
completeness_share["1. Raw data"] = calculate_completeness(transformer_data)

# Remove all values below zero
transformer_data[transformer_data <= 0] = None

# Calculate the completeness of the dataset
completeness_share["2. Remove negative values"] = calculate_completeness(transformer_data)

# Resample the data to 1 hour (this also adds the missing values for 2022)
transformer_data = transformer_data.resample("1H").mean()

# Calculate the completeness of the dataset
completeness_share["3. Resample to 1 hour"] = calculate_completeness(transformer_data)

# Calculate the mean relative demand per timestep and use to fill NaNs
mean_relative_transformer_data = (transformer_data / transformer_data.mean()).mean(axis=1)
for column_name in transformer_data:
    transformer_data[column_name] = transformer_data[column_name].fillna(mean_relative_transformer_data * transformer_data[column_name].mean())

# Calculate the completeness of the dataset
completeness_share["4. Mean relative demand"] = calculate_completeness(transformer_data)

# Remove all values below 0 and remove all values further than 4 standard deviation
transformer_data[transformer_data <= 0] = None
outliers = (transformer_data - transformer_data.mean()).abs() > 4 * transformer_data.std()
transformer_data[outliers] = None

# Replace all NaN's with the average value of that time in the week
for column_name in transformer_data:
    transformer_data_column = transformer_data[column_name]
    group_list = [transformer_data_column.index.weekday, transformer_data_column.index.hour, transformer_data_column.index.minute]
    transformer_data[column_name] = transformer_data_column.groupby(group_list).transform(lambda group: group.fillna(group.mean()))

# Calculate the completeness of the dataset show it in an expander
with st.expander("Transformer dataset completeness"):
    completeness_share["5. Average weekday"] = calculate_completeness(transformer_data)
    st.line_chart(completeness_share.transpose())

# Change the transformer data to MW
transformer_data = transformer_data / 1000

# Show a chart with the temporal data
with st.expander("Temporal data preview"):
    column_name = st.selectbox("Demand column", transformer_data.columns)
    st.line_chart(transformer_data[column_name])

# Generate the data in bidding zone files for both with and without EV demand
if st.button("Generate bidding zone files"):
    # Change the transformer data to the same timeseries as the demand
    transformer_data = pv_capacity_factors.index.to_series().apply(lambda timestamp: transformer_data.loc[timestamp.replace(year=2022)])

    for index, scenario_name in enumerate(["Lombok", "Lombok (without EV)"]):
        # Create the scenario directory
        scenario_directory = utils.path("input", "scenarios", scenario_name)
        scenario_directory.mkdir(exist_ok=True)

        # Get either the data with or without EV load and set the column names
        transformer_data_subset = transformer_data[transformer_data.columns[index::2]]
        transformer_data_subset.columns = [f"LB{str(index).rjust(2, '0')}" for index in range(len(transformer_data_subset.columns))]

        # Store the capacity factors
        pv_capacity_factors.columns = [f"pv_LB{column_name}_cf" for column_name in pv_capacity_factors.columns]
        (scenario_directory / "ires").mkdir(exist_ok=True)
        for column_name in transformer_data_subset.columns:
            pv_capacity_factors.to_csv(utils.path("input", "scenarios", scenario_name, "ires", f"{column_name}.csv"))

        # Store the demand data
        transformer_data_subset["NL00"] = 0
        transformer_data_subset.to_csv(scenario_directory / "demand.csv")
