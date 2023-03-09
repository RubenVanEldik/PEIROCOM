import pandas as pd
import streamlit as st

import chart
import colors
import utils
import validate


def _scale_column(column):
    """
    Scale the column so the maximum value is between 0 and 1000
    """
    assert validate.is_series(column)

    if column.max() > 10 ** 6:
        return pd.Series(column / 10 ** 6, name=column.name.replace('MW', 'TW'))
    if column.max() > 10 ** 2:
        return pd.Series(column / 10 ** 3, name=column.name.replace('MW', 'GW'))
    if column.max() > 1:
        return pd.Series(column, name=column.name.replace('MW', 'MW'))
    if column.max() > 10 ** -3:
        return pd.Series(column * 10 ** 3, name=column.name.replace('MW', 'kW'))
    return pd.Series(column * 10 ** 6, name=column.name.replace('MW', 'W'))


def average_year(output_directory):
    """
    Show a heatmap with the average year of some selected columns
    """
    assert validate.is_directory_path(output_directory)

    st.title("🎆️ Average year")

    st.sidebar.header("Options")

    # Select which countries should be shown (when none are selected all are shown)
    config = utils.read_yaml(output_directory / "config.yaml")
    selected_country_codes = st.sidebar.multiselect("Countries", config["country_codes"], format_func=lambda country_code: utils.get_country_property(country_code, "name"))

    # Get temporal results for all countries
    temporal_results = utils.get_temporal_results(output_directory, group="all", country_codes=selected_country_codes)

    # Select the relevant columns
    columns = st.sidebar.multiselect("Columns", temporal_results.columns, format_func=utils.format_column_name)

    # Show a message when no columns have been selected
    if len(columns) == 0:
        st.warning("Select one or more columns to plot")
        return

    # Initialize the plot
    plot = chart.Chart(len(columns), 1, xlabel="Time of year", ylabel="Time of day")

    for index, column in enumerate(columns):
        # Get the subplot
        subplot = plot.axs if len(columns) == 1 else plot.axs[index]

        # Get the scaled column
        temporal_results_column = _scale_column(temporal_results[column])

        # Select the label name
        label_name = st.sidebar.text_input(f"Label {index + 1}", value=utils.format_column_name(temporal_results_column.name))

        # Make a DataFrame with the average data per hour and day of year
        temporal_results_parsed = pd.DataFrame()
        for hour in range(24):
            temporal_results_day = temporal_results_column.loc[temporal_results_column.index.hour == hour]
            temporal_results_parsed[hour] = temporal_results_day.groupby(temporal_results_day.index.dayofyear).mean()

        # Plot the data and create the color bar
        imshow = subplot.imshow(temporal_results_parsed.transpose(), aspect="auto", cmap=colors.colormap("blue"), origin='lower')
        subplot.figure.colorbar(imshow, shrink=0.8, aspect=15, label=label_name, pad=0.025)

        # Set the limit of the x-axis
        subplot.set_xlim([0, 365])
        # Show the monthly ticks, but don't show the labels
        subplot.set_xticks([0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 335])
        subplot.tick_params(axis="x", which="major", labelbottom=False)  # changes apply to the x-axis  # both major and minor ticks are affected  # ticks along the bottom edge are off  # ticks along the top edge are off
        # Show the monthly labels as minor ticks, so they are between the day ticks
        subplot.set_xticks([15, 46, 74, 105, 135, 166, 196, 227, 258, 288, 319, 350], ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], minor=True)
        subplot.tick_params(axis="x", which="minor", bottom=False, top=False)  # changes apply to the x-axis  # both major and minor ticks are affected  # ticks along the bottom edge are off  # ticks along the top edge are off

    # Show the plot
    plot.display()
    plot.download_button("average_year.png")

    # Show the table in an expander
    with st.expander("Data points"):
        st.dataframe(temporal_results)
