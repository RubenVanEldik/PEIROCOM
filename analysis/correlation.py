import pandas as pd
import streamlit as st

import chart
import colors
import utils
import validate


def correlation(run_name, resolution):
    """
    Plot the correlation between the distance between of two countries and the value of a specific column
    """
    assert validate.is_string(run_name)
    assert validate.is_resolution(resolution)

    st.title("📉 Correlation")

    st.sidebar.header("Options")

    # Get the temporal results and merge them on a single column
    all_temporal_results = utils.get_temporal_results(run_name, resolution, group="country")
    relevant_columns = utils.find_common_columns(all_temporal_results)
    column_name = st.sidebar.selectbox("Column", relevant_columns, format_func=utils.format_column_name)
    temporal_results = utils.merge_dataframes_on_column(all_temporal_results, column_name)

    # Remove all columns which contain only zeroes
    temporal_results = temporal_results.loc[:, (temporal_results != 0).any(axis=0)]

    # Get the geometries and centroids for all countries
    geometries = utils.get_geometries_of_countries(all_temporal_results.keys())
    geometries["centroid"] = geometries.centroid

    # Calculate the distance and R-squared for each country pair
    index = [(column_name1, column_name2) for column_name1 in temporal_results for column_name2 in temporal_results if column_name1 < column_name2]
    columns = ["distance", "r_squared"]
    correlations = pd.DataFrame(index=index, columns=columns)
    correlations["distance"] = correlations.apply(lambda row: utils.calculate_distance(geometries.loc[row.name[0], "centroid"], geometries.loc[row.name[1], "centroid"]) / 1000, axis=1)
    correlations["r_squared"] = correlations.apply(lambda row: utils.calculate_r_squared(temporal_results[row.name[0]], temporal_results[row.name[1]]), axis=1)

    # Create a scatter plot
    correlation_plot = chart.Chart(xlabel="Distance (km)", ylabel="Coefficient of determination")
    correlation_plot.set_y_limits(0, 1)
    correlation_plot.format_yticklabels("{:,.0%}")
    correlation_plot.ax.scatter(correlations.distance, correlations.r_squared, color=colors.get("blue", 600), alpha=0.5)

    # Add a regression line if the checkbox is checked
    if st.sidebar.checkbox("Show regression line"):
        degree = st.sidebar.slider("Degrees", min_value=1, value=2, max_value=5)
        trendline_x, trendline_y = utils.calculate_regression_line(correlations.distance, correlations.r_squared, degree=degree)
        correlation_plot.ax.plot(trendline_x, trendline_y, color=colors.get("red", 600))

    # Show the plot
    st.pyplot(correlation_plot.fig)
