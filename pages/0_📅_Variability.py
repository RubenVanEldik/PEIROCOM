from datetime import datetime, timezone, timedelta
import entsoe
import matplotlib
import pandas as pd
import streamlit as st

import chart
import colors
import utils


def run():
    """
    Show the variability plot
    """
    variability_type = st.sidebar.radio("Variability", ["day", "year"], format_func=utils.format_str)

    # Get the country code
    countries = utils.read_yaml(utils.path("input", "countries.yaml"))
    country_codes = [country["nuts_2"] for country in countries]
    format_func = lambda nuts_2: utils.get_country_property(nuts_2, "name")
    country_code = st.sidebar.selectbox("Country", country_codes, index=country_codes.index("NL"), format_func=format_func)

    # Calculate the start and end date and time
    if variability_type == "day":
        date = st.sidebar.date_input("Date", max_value=datetime.now())
        start = pd.Timestamp(datetime(date.year, date.month, date.day, 0, 0, tzinfo=timezone.utc))
        date_after = date + timedelta(days=1)
        end = pd.Timestamp(datetime(date_after.year, date_after.month, date_after.day, 0, 0, tzinfo=timezone.utc))
    elif variability_type == "year":
        current_year = datetime.today().year
        year = st.sidebar.number_input("Year", value=current_year - 1, min_value=2000, max_value=current_year)
        start = pd.Timestamp(datetime(int(year), 1, 1, 0, 0, tzinfo=timezone.utc))
        end = pd.Timestamp(datetime(int(year), 12, 31, 23, 59, tzinfo=timezone.utc))

    # Get the demand and production data
    try:
        demand = utils.entsoe.query_load(country_code, start=start, end=end)["Actual Load"]
        demand.name = "demand"
        demand_relative = demand / demand.mean()

        # Get the IRES production
        production = utils.entsoe.query_generation(country_code, start=start, end=end)
        production_pv = production[("Solar", "Actual Aggregated")]
        production_onshore = production[("Wind Onshore", "Actual Aggregated")]
        production_offshore = production[("Wind Offshore", "Actual Aggregated")]
        production_ires = production_pv + production_onshore + production_offshore
        production_ires_relative = production_ires / production_ires.mean()
    except entsoe.exceptions.NoMatchingDataError:
        st.error(f"Could not find the data for {utils.get_country_property(country_code, 'name')}")
        return

    # Show the weekly rolling average for the yearly data
    if variability_type == "year":
        demand_relative = demand_relative.rolling(4 * 24 * 7).mean()
        production_ires_relative = production_ires_relative.rolling(4 * 24 * 7).mean()

    # Plot the demand and IRES production
    xlabel = "Hour" if variability_type == "day" else "Month"
    plot = chart.Chart(xlabel=xlabel, ylabel="Relative power")
    plot.ax.plot(demand_relative, label="Demand", color=colors.primary())
    plot.ax.plot(production_ires_relative, label="IRES production", color=colors.secondary())
    plot.ax.set_xlim([start, end - pd.Timedelta(15, "min")])
    date_format = matplotlib.dates.DateFormatter("%H:%M" if variability_type == "day" else "%b")
    plot.ax.xaxis.set_major_formatter(date_format)
    plot.ax.legend()
    st.pyplot(plot.fig)


run()
