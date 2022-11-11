import pandas as pd
import streamlit as st

import chart
import colors
import utils
import validate


def correlation(output_directory, resolution):
    """
    Plot the correlation between the distance between of two countries and the value of a specific column
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_resolution(resolution)

    st.title("📉 Correlation")

    # Show a warning message if the run only includes one country
    config = utils.read_yaml(output_directory / "config.yaml")
    if len(config["country_codes"]) == 1:
        st.warning("The correlation plot is only available for runs that include multiple countries.")
        return

    st.sidebar.header("Options")

    # Get the temporal results and merge them on a single column
    all_temporal_results = utils.get_temporal_results(output_directory, resolution, group="country")
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
    correlation_plot.ax.set_ylim([0, 1])
    correlation_plot.format_yticklabels("{:,.0%}")
    correlation_plot.ax.scatter(correlations.distance, correlations.r_squared, color=colors.primary(alpha=0.5), linewidths=0)

    # Add a regression line if the checkbox is checked
    if st.sidebar.checkbox("Show regression line"):
        regression_function_string = st.sidebar.text_input("Curve formula", value="a + b * x", help="Use a, b, and c as variables and use x for the x-value")
        regression_function = eval(f"lambda x, a, b, c: {regression_function_string}")
        try:
            regression_line = utils.fit_curve(correlations.distance, correlations.r_squared, function=regression_function)
            correlation_plot.ax.plot(regression_line, color=colors.get("red", 600))
        except:
            st.sidebar.error("The function is not valid")

    # Show the plot
    correlation_plot.display()
    correlation_plot.download_button("correlation.png")

    # Show the table in an expander
    with st.expander("Data points"):
        correlations.columns = [utils.format_str(column_name) for column_name in correlations.columns]
        correlations["index"] = [f"{utils.get_country_property(from_country_code, 'name')} & {utils.get_country_property(to_country_code, 'name')}" for from_country_code, to_country_code in correlations.index]
        correlations = correlations.set_index("index")
        st.table(correlations)
