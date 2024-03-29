import streamlit as st

import chart
import colors
import utils
import validate


def temporal_results(output_directory):
    """
    Show the temporal results in a chart and table
    """
    assert validate.is_directory_path(output_directory)

    st.title("🕰️ Temporal results")

    st.sidebar.header("Options")

    # Get temporal results for a country
    all_temporal_results = utils.get_temporal_results(output_directory, group="country")
    config = utils.read_yaml(output_directory / "config.yaml")
    country_code = st.sidebar.selectbox("Country", config["country_codes"], format_func=lambda value: utils.get_country_property(value, "name"))
    temporal_results = all_temporal_results[country_code]

    # Filter the data columns
    temporal_results.columns = [utils.format_column_name(column_name) for column_name in temporal_results.columns]
    columns = st.sidebar.multiselect("Columns", temporal_results.columns, default=temporal_results.columns.values[:1])
    temporal_results = temporal_results[columns]

    # Show the chart and DataFrame if any columns are selected
    if columns:
        # Calculate the rolling average
        rolling_average_options = {1: "Off", "1D": "Daily", "7D": "Weekly", "30D": "Monthly", "365D": "Yearly"}
        window = st.sidebar.selectbox("Rolling average", rolling_average_options.keys(), index=2, format_func=lambda key: rolling_average_options[key])
        temporal_results = temporal_results.rolling(window=window).mean()

        # Filter the data temporarily
        start_data = temporal_results.index.min().to_pydatetime()
        end_data = temporal_results.index.max().to_pydatetime()
        data_range = st.sidebar.slider("Date range", value=(start_data, end_data), min_value=start_data, max_value=end_data)
        temporal_results = temporal_results.loc[data_range[0]: data_range[1]]

        # Initialize the plot
        plot = chart.Chart(xlabel="Time", ylabel="", wide=True)

        # Add each of the selected columns to the plot
        for column_name in temporal_results:
            plot.axs.plot(temporal_results[column_name], label=column_name, color=colors.random(value=600))

        # Show the plot
        plot.add_legend()
        plot.display()
        plot.download_button("temporal_results.png")

        # Show the table in an expander
        with st.expander("Data points"):
            st.dataframe(temporal_results)
