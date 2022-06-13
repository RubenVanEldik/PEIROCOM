import streamlit as st

import utils
import validate


def temporal_results(run_name):
    """
    Show the temporal results in a chart and table
    """
    assert validate.is_string(run_name)

    st.title("🕰️ Temporal results")

    # Get temporal results for a country
    all_temporal_results = utils.get_temporal_results(run_name, group="country")
    config = utils.read_yaml(f"./output/{run_name}/config.yaml")
    country = st.sidebar.selectbox("Country", config["countries"], format_func=lambda country: country["name"])
    temporal_results = all_temporal_results[country["nuts_2"]]

    # Filter the data columns
    temporal_results.columns = [utils.format_column_name(column_name) for column_name in temporal_results.columns]
    columns = st.sidebar.multiselect("Columns", temporal_results.columns)
    temporal_results = temporal_results[columns]

    # Show the chart and DataFrame if any columns are selected
    if columns:
        # Calculate the rolling average
        rolling_average_options = {1: "Off", 24: "Daily", 24 * 7: "Weekly", 24 * 28: "Monthly", 24 * 365: "Yearly"}
        window = st.sidebar.selectbox("Rolling average", rolling_average_options.keys(), index=2, format_func=lambda key: rolling_average_options[key])
        temporal_results = temporal_results.rolling(window=window).mean()

        # Filter the data temporarily
        start_data = temporal_results.index.min().to_pydatetime()
        end_data = temporal_results.index.max().to_pydatetime()
        data_range = st.sidebar.slider("Date range", value=(start_data, end_data), min_value=start_data, max_value=end_data)
        temporal_results = temporal_results.loc[data_range[0] : data_range[1]]

        # Show the line chart
        st.line_chart(temporal_results)

        # Show the table in an expander
        with st.expander("Raw data"):
            st.dataframe(temporal_results)
