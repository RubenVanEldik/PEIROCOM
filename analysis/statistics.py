import streamlit as st

import stats
import utils
import validate


def _format_value_with_unit(value, *, unit):
    """
    Format the value with the proper unit
    """
    assert validate.is_number(value)
    assert validate.is_string(unit)

    if value > 10 ** 15:
        return f"{value / 10 ** 15:,.0f}P{unit}"
    if value > 10 ** 12:
        return f"{value / 10 ** 12:,.0f}T{unit}"
    if value > 10 ** 9:
        return f"{value / 10 ** 9:,.0f}G{unit}"
    if value > 10 ** 6:
        return f"{value / 10 ** 6:,.0f}M{unit}"
    if value > 10 ** 3:
        return f"{value / 10 ** 3:,.0f}k{unit}"
    return f"{value:,.0f}{unit}"


def statistics(output_directory):
    """
    Show the key indicators for a run
    """
    assert validate.is_directory_path(output_directory)

    st.title("📊 Statistics")

    st.sidebar.header("Options")

    # Ask for which countries the statistics should be shown
    config = utils.read_yaml(output_directory / "config.yaml")
    selected_country_codes = st.sidebar.multiselect("Countries", config["country_codes"], format_func=lambda country_code: utils.get_country_property(country_code, "name"))

    # Calculate the mean demand over all selected countries
    temporal_results = utils.get_temporal_results(output_directory, country_codes=selected_country_codes)
    mean_demand = utils.merge_dataframes_on_column(temporal_results, "demand_MW").sum(axis=1).mean()

    # Show the KPI's
    with st.expander("KPI's", expanded=True):
        col1, col2, col3 = st.columns(3)

        # LCOE
        firm_lcoe_selected = stats.firm_lcoe(output_directory, country_codes=selected_country_codes)
        firm_lcoe_all = stats.firm_lcoe(output_directory)
        lcoe_delta = f"{(firm_lcoe_selected / firm_lcoe_all) - 1:.0%}" if selected_country_codes else None
        col1.metric("LCOE", f"{int(firm_lcoe_selected)}€/MWh", lcoe_delta, delta_color="inverse")

        # Firm kWh premium
        premium_selected = stats.premium(output_directory, country_codes=selected_country_codes)
        premium_all = stats.premium(output_directory)
        premium_delta = f"{(premium_selected / premium_all) - 1:.0%}" if selected_country_codes else None
        col2.metric("Firm kWh premium", f"{premium_selected:.2f}", premium_delta, delta_color="inverse")

        # Curtailment
        curtailment_selected = stats.relative_curtailment(output_directory, country_codes=selected_country_codes)
        curtailment_all = stats.relative_curtailment(output_directory)
        curtailment_delta = f"{(curtailment_selected / curtailment_all) - 1:.0%}" if selected_country_codes else None
        col3.metric("Curtailment", f"{curtailment_selected:.1%}", curtailment_delta, delta_color="inverse")

    # Show the generation capacities
    with st.expander("Generation capacity", expanded=True):
        # Ask if the results should be shown relative to the mean demand
        show_relative_generation_capacity = st.checkbox("Relative to demand", key="generation")
        show_hourly_generation = st.checkbox("Mean hourly generation")

        # Get the generation capacities
        generation_capacity = stats.generation_capacity(output_directory, country_codes=selected_country_codes)

        # Create the storage capacity columns
        cols = st.columns(max(len(generation_capacity.index), 3))

        # Create the metric for each generation technology
        for index, technology in enumerate(generation_capacity.index):
            # Set the metric value depending on the checkboxes
            if show_hourly_generation:
                mean_hourly_generation = utils.merge_dataframes_on_column(temporal_results, f"generation_{technology}_MW").sum(axis=1).mean()
                if show_relative_generation_capacity:
                    metric_value = f"{mean_hourly_generation / mean_demand:.1%}"
                else:
                    metric_value = _format_value_with_unit(mean_hourly_generation * 10 ** 6, unit="W")
            else:
                if show_relative_generation_capacity:
                    metric_value = f"{generation_capacity[technology] / mean_demand:.1%}"
                else:
                    metric_value = _format_value_with_unit(generation_capacity[technology] * 10 ** 6, unit="W")

            # Set the metric
            cols[index % 3].metric(utils.format_technology(technology), metric_value)

    if config["technologies"]["hydropower"]:
        with st.expander("Hydropower capacity", expanded=True):
            # Ask if the results should be shown relative to the mean demand
            show_relative_hydropower_capacity = st.checkbox("Relative to demand", key="hydropower")

            # Get the capacities
            hydropower_capacity = stats.hydropower_capacity(output_directory, country_codes=selected_country_codes)
            turbine_capacity = hydropower_capacity.turbine.sum()
            pump_capacity = hydropower_capacity.pump.sum()
            reservoir_capacity = hydropower_capacity.reservoir.sum()

            # Create the hydropower capacity columns
            col1, col2, col3 = st.columns(3)

            # Display the capacities
            if show_relative_hydropower_capacity:
                col1.metric("Turbine capacity", f"{turbine_capacity / mean_demand:.1%}")
                col2.metric("Pumping capacity", f"{pump_capacity / mean_demand:.1%}")
                col3.metric("Reservoir capacity", f"{reservoir_capacity / mean_demand:.1f}H")
            else:
                col1.metric("Turbine capacity", _format_value_with_unit(turbine_capacity * 10 ** 6, unit="W"))
                col2.metric("Pumping capacity", _format_value_with_unit(pump_capacity * 10 ** 6, unit="W"))
                col3.metric("Reservoir capacity", _format_value_with_unit(reservoir_capacity * 10 ** 6, unit="Wh"))

    # Show the storage capacities
    with st.expander("Storage capacity", expanded=True):
        # Ask if the results should be shown relative to the mean demand
        show_relative_storage_capacity = st.checkbox("Relative to demand", key="storage")
        show_power_capacity = st.checkbox("Power capacity")
        storage_capacity_attribute = "power" if show_power_capacity else "energy"

        # Get the storage capacities
        storage_capacity = stats.storage_capacity(output_directory, country_codes=selected_country_codes)[storage_capacity_attribute]

        # Create the storage capacity columns
        cols = st.columns(max(len(storage_capacity.index), 3))

        # Create the metric for each storage technology
        for index, technology in enumerate(storage_capacity.index):
            # Set the metric value depending on the checkbox
            if show_power_capacity:
                if show_relative_storage_capacity:
                    metric_value = f"{storage_capacity[technology] / mean_demand:.1%}"
                else:
                    metric_value = _format_value_with_unit(storage_capacity[technology] * 10 ** 6, unit="W")
            else:
                if show_relative_storage_capacity:
                    metric_value = f"{storage_capacity[technology] / mean_demand:.1f}H"
                else:
                    metric_value = _format_value_with_unit(storage_capacity[technology] * 10 ** 6, unit="Wh")

            # Set the metric
            cols[index % 3].metric(f"{utils.format_technology(technology)} {storage_capacity_attribute}", metric_value)
