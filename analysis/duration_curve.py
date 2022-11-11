import numpy as np
import pandas as pd
import re
import streamlit as st

import chart
import colors
import utils
import validate


def _sort(data, *, ascending=False):
    """
    Sort a DataFrame or Series and give it an index from 0 to 1
    """
    assert validate.is_dataframe(data) or validate.is_series(data)
    assert validate.is_bool(ascending)

    # Create an index from 0 to 1
    index = np.linspace(start=0, stop=1, num=len(data.index))

    # Return a sorted Series if the data is a Series
    if validate.is_series(data):
        return pd.Series(data.sort_values(ascending=ascending).tolist(), index=index)

    # Return a sorted DataFrame if the data is a DataFrame
    data_sorted = pd.DataFrame(index=index)
    for column_name in data:
        data_sorted[column_name] = data[column_name].sort_values(ascending=ascending).tolist()

    return data_sorted


def duration_curve(output_directory, resolution):
    """
    Analyze the storage
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_resolution(resolution)

    st.title("⌛ Duration curve")

    st.sidebar.header("Options")

    # Get the storage capacity and temporal results
    all_temporal_results = utils.get_temporal_results(output_directory, resolution, group="country")

    # Select a column as numerator and denominator
    st.sidebar.subheader("Columns")
    first_country = next(iter(all_temporal_results))
    columns = all_temporal_results[first_country].columns
    relevant_columns = utils.find_common_columns(all_temporal_results)
    relative = st.sidebar.checkbox("Relative")
    if relative:
        col1, col2 = st.sidebar.columns(2)
        numerator = col1.selectbox("Numerator", relevant_columns, format_func=utils.format_column_name)
        denominator = col2.selectbox("Denominator", relevant_columns, format_func=utils.format_column_name)
    else:
        numerator = st.sidebar.selectbox("Column", relevant_columns, format_func=utils.format_column_name)
        denominator = None

    # Set the label for the y-axis
    st.sidebar.subheader("Axes")
    col1, col2 = st.sidebar.columns(2)
    ylabel_match = re.search("(.+)_(\w+)$", numerator)
    ylabel_text = utils.format_str(ylabel_match.group(1))
    ylabel_unit = ylabel_match.group(2) if denominator is None else "%"
    xlabel = col1.text_input("Label x-axis", value="Time (%)")
    ylabel = col2.text_input("Label y-axis", value=f"{ylabel_text} ({ylabel_unit})")
    axis_scale_options = ["linear", "log", "symlog", "logit"]
    xscale = col1.selectbox("Scale x-axis", axis_scale_options, format_func=utils.format_str)
    yscale = col2.selectbox("Scale y-axis", axis_scale_options, format_func=utils.format_str)

    # Set the waterfall parameters
    st.sidebar.subheader("Options")
    range_area = st.sidebar.checkbox("Range area", value=True)
    individual_lines = st.sidebar.checkbox("Individual lines", value=False)
    ignore_zeroes = st.sidebar.checkbox("Ignore zeroes", value=False)
    unity_line = st.sidebar.checkbox("Unity line", value=False)

    # Calculate the waterfall DataFrame (for each country) and Series (for all countries combined)
    if denominator:
        numerator_df = utils.merge_dataframes_on_column(all_temporal_results, numerator)
        denominator_df = utils.merge_dataframes_on_column(all_temporal_results, denominator)
        waterfall_df = _sort(numerator_df / denominator_df)
        waterfall_df_mean = _sort((numerator_df / denominator_df).mean(axis=1))
    else:
        numerator_df = utils.merge_dataframes_on_column(all_temporal_results, numerator)
        waterfall_df = _sort(numerator_df)
        waterfall_df_mean = _sort(numerator_df.mean(axis=1))

    # Create the chart
    waterfall_plot = chart.Chart(xlabel=xlabel, ylabel=ylabel, xscale=xscale, yscale=yscale)

    # Remove all rows where all values are zero
    if ignore_zeroes:
        last_non_zero_row = waterfall_df[waterfall_df.max(axis=1) != 0].iloc[-1].name
        waterfall_df = waterfall_df[:last_non_zero_row]

    # Plot the range fill
    if range_area:
        waterfall_plot.ax.fill_between(waterfall_df.index, waterfall_df.min(axis=1), waterfall_df.max(axis=1), color=colors.get("blue", 100))

    # Plot a line for each column (country)
    if individual_lines:
        waterfall_plot.ax.plot(waterfall_df, color=colors.primary(alpha=0.1), linewidth=1)

    # Plot the mean values
    waterfall_plot.ax.plot(waterfall_df_mean, color=colors.primary())

    # Plot the unity line
    if unity_line:
        waterfall_plot.ax.axhline(y=1, color=colors.get("red", 600), linewidth=1)

    # Set the x-axis limits. Use round() to ensure that the labels on either end are included
    waterfall_plot.ax.set_xlim([round(waterfall_df.index.min(), 2), round(waterfall_df.index.max(), 2)])

    # Format the axes to be percentages
    waterfall_plot.format_xticklabels("{:,.0%}")
    waterfall_plot.format_yticklabels("{:,.0%}" if denominator else "{:,.0f}")

    # Plot the figure
    waterfall_plot.display()
    waterfall_plot.download_button("duration_curve.png")

    # Show the table in an expander
    with st.expander("Data points"):
        st.dataframe(waterfall_df)
