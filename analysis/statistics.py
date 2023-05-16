import numpy as np
import streamlit as st

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
    mean_temporal_results = utils.get_mean_temporal_results(output_directory, country_codes=selected_country_codes)
    mean_demand = mean_temporal_results["demand_total_MW"]

    # Show the KPI's
    with st.expander("Electricity", expanded=True):
        col1, col2, col3 = st.columns(3)

        # LCOE
        firm_lcoe_selected = utils.previous_run.firm_lcoe(output_directory, country_codes=selected_country_codes)
        firm_lcoe_all = utils.previous_run.firm_lcoe(output_directory)
        lcoe_delta = f"{(firm_lcoe_selected / firm_lcoe_all) - 1:.0%}" if selected_country_codes else None
        col1.metric("LCOE", f"{int(firm_lcoe_selected)}€/MWh", lcoe_delta, delta_color="inverse")

        # Firm kWh premium
        premium_selected = utils.previous_run.premium(output_directory, country_codes=selected_country_codes)
        premium_all = utils.previous_run.premium(output_directory)
        premium_delta = f"{(premium_selected / premium_all) - 1:.0%}" if selected_country_codes else None
        col2.metric("Firm kWh premium", f"{premium_selected:.2f}", premium_delta, delta_color="inverse")

        # Curtailment
        curtailment_selected = utils.previous_run.relative_curtailment(output_directory, country_codes=selected_country_codes)
        curtailment_all = utils.previous_run.relative_curtailment(output_directory)
        curtailment_delta = f"{(curtailment_selected / curtailment_all) - 1:.0%}" if selected_country_codes else None
        col3.metric("Curtailment", f"{curtailment_selected:.1%}", curtailment_delta, delta_color="inverse")

    with st.expander("Hydrogen", expanded=True):
        col1, col2, col3 = st.columns(3)

        for electrolysis_technology in config["technologies"]["electrolysis"]:
            electrolysis_technology_name = utils.format_technology(electrolysis_technology)

            # LCOH
            lcoh_selected = utils.previous_run.lcoh(output_directory, country_codes=selected_country_codes, electrolysis_technology=electrolysis_technology)
            lcoh_all = utils.previous_run.lcoh(output_directory, electrolysis_technology=electrolysis_technology)
            lcoh_delta = f"{(lcoh_selected / lcoh_all) - 1:.0%}" if selected_country_codes else None
            if np.isnan(lcoh_selected):
                col1.metric(f"LCOH ({electrolysis_technology_name})", "—")
            else:
                hydrogen_mwh_kg = 0.033333
                col1.metric(f"LCOH ({electrolysis_technology_name})", f"{lcoh_selected * hydrogen_mwh_kg:.2f}€/kg", lcoh_delta, delta_color="inverse")

            # Electrolyzer capacity factor
            electrolyzer_capacity_factor_selected = utils.previous_run.electrolyzer_capacity_factor(output_directory, country_codes=selected_country_codes, electrolysis_technology=electrolysis_technology)
            electrolyzer_capacity_factor_all = utils.previous_run.electrolyzer_capacity_factor(output_directory, electrolysis_technology=electrolysis_technology)
            electrolyzer_capactity_factor_delta = f"{(electrolyzer_capacity_factor_selected / electrolyzer_capacity_factor_all) - 1:.0%}" if selected_country_codes else None
            if np.isnan(electrolyzer_capacity_factor_selected):
                col2.metric(f"Capacity factor ({electrolysis_technology_name})", "—")
            else:
                col2.metric(f"Capacity factor ({electrolysis_technology_name})", f"{electrolyzer_capacity_factor_selected:.0%}", electrolyzer_capactity_factor_delta)

    # Show the IRES capacities
    with st.expander("IRES capacity", expanded=True):
        # Ask if the results should be shown relative to the mean demand
        show_relative_capacity = st.checkbox("Relative to demand", key="relative_to_demand_ires")
        show_hourly_generation = st.checkbox("Mean hourly generation", key="mean_hourly_ires")

        # Get the capacities
        ires_capacity = utils.previous_run.ires_capacity(output_directory, country_codes=selected_country_codes)

        # Create the storage capacity columns
        cols = st.columns(max(len(ires_capacity.index), 3))

        # Create the metric for each technology
        for index, technology in enumerate(ires_capacity.index):
            # Set the metric value depending on the checkboxes
            if show_hourly_generation:
                mean_hourly_generation = utils.merge_dataframes_on_column(temporal_results, f"generation_{technology}_MW").sum(axis=1).mean()
                if show_relative_capacity:
                    metric_value = f"{mean_hourly_generation / mean_demand:.1%}"
                else:
                    metric_value = _format_value_with_unit(mean_hourly_generation * 10 ** 6, unit="W")
            else:
                if show_relative_capacity:
                    metric_value = f"{ires_capacity[technology] / mean_demand:.1%}"
                else:
                    metric_value = _format_value_with_unit(ires_capacity[technology] * 10 ** 6, unit="W")

            # Set the metric
            cols[index % 3].metric(utils.format_technology(technology), metric_value)

    # Show the dispatchable capacities
    if len(config["technologies"]["dispatchable"]) > 0:
        with st.expander("Dispatchable capacity", expanded=True):
            # Ask if the results should be shown relative to the mean demand
            show_relative_capacity = st.checkbox("Relative to demand", key="relative_to_demand_dispatchable")
            show_hourly_generation = st.checkbox("Mean hourly generation", key="mean_hourly_dispatchable")

            # Get the capacities
            dispatchable_capacity = utils.previous_run.dispatchable_capacity(output_directory, country_codes=selected_country_codes)

            # Create the storage capacity columns
            cols = st.columns(max(len(dispatchable_capacity.index), 3))

            # Create the metric for each technology
            for index, technology in enumerate(dispatchable_capacity.index):
                # Set the metric value depending on the checkboxes
                if show_hourly_generation:
                    mean_hourly_generation = utils.merge_dataframes_on_column(temporal_results, f"generation_{technology}_MW").sum(axis=1).mean()
                    if show_relative_capacity:
                        metric_value = f"{mean_hourly_generation / mean_demand:.1%}"
                    else:
                        metric_value = _format_value_with_unit(mean_hourly_generation * 10 ** 6, unit="W")
                else:
                    if show_relative_capacity:
                        metric_value = f"{dispatchable_capacity[technology] / mean_demand:.1%}"
                    else:
                        metric_value = _format_value_with_unit(dispatchable_capacity[technology] * 10 ** 6, unit="W")

                # Set the metric
                cols[index % 3].metric(utils.format_technology(technology), metric_value)

    if config["technologies"]["hydropower"]:
        with st.expander("Hydropower capacity", expanded=True):
            # Ask if the results should be shown relative to the mean demand
            show_relative_hydropower_capacity = st.checkbox("Relative to demand", key="hydropower")

            # Get the capacities
            hydropower_capacity = utils.previous_run.hydropower_capacity(output_directory, country_codes=selected_country_codes)
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
        storage_capacity = utils.previous_run.storage_capacity(output_directory, country_codes=selected_country_codes)[storage_capacity_attribute]

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
