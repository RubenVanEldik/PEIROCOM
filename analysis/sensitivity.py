import numpy as np
import pandas as pd
import streamlit as st

import chart
import colors
import stats
import utils
import validate


@st.experimental_memo(show_spinner=False)
def _retrieve_statistics(steps, method, output_directory, resolution, **kwargs):
    """
    Retrieve the statistics for all steps
    """
    assert validate.is_series(steps)
    assert validate.is_string(method)
    assert validate.is_directory_path(output_directory)
    assert validate.is_resolution(resolution)

    # Initialize the progress bar
    progress_bar = st.progress(0.0)

    # Create a 1-item list so the index can be updated from within the function
    index = [0]

    def _apply_step(step):
        # Retrieve the statistic for this step
        step_data = getattr(stats, method)(output_directory / step, resolution, **kwargs)
        # Update the index
        index[0] += 1
        progress_bar.progress(index[0] / len(steps))
        # Return the data
        return step_data

    # Get the statistics for each step
    data = steps.apply(_apply_step)

    # Remove the progress bar
    progress_bar.empty()

    # Return the data
    return data


def _plot(output_directory, resolution, sensitivity_config, sensitivity_plot, statistic_name, breakdown_level, show_cumulative_results, *, label=None, line_color=colors.primary()):
    """
    Analyze the sensitivity
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_resolution(resolution)
    assert validate.is_sensitivity_config(sensitivity_config)
    assert validate.is_chart(sensitivity_plot)
    assert validate.is_string(statistic_name)
    assert validate.is_integer(breakdown_level, min_value=0, max_value=2)
    assert validate.is_bool(show_cumulative_results)
    assert validate.is_string(label, required=False)
    assert validate.is_color(line_color)

    # Create a Series with the sensitivity steps as rows
    if sensitivity_config["analysis_type"] == "curtailment":
        # Use the actual curtailment as the index
        step_index = [stats.relative_curtailment(output_directory / step, resolution) for step in sensitivity_config["steps"].keys()]
    else:
        step_index = sensitivity_config["steps"].values()
    steps = pd.Series(data=sensitivity_config["steps"].keys(), index=step_index).sort_index()

    # Add the output for the sensitivity steps to the sensitivity plot
    if statistic_name in ["firm_lcoe", "unconstrained_lcoe", "premium"]:
        # Get the data and set the label
        if statistic_name == "firm_lcoe":
            sensitivity_plot.ax.set_ylabel("Firm LCOE (€/MWh)")
            data = _retrieve_statistics(steps, "firm_lcoe", output_directory, resolution, breakdown_level=breakdown_level)
        if statistic_name == "unconstrained_lcoe":
            sensitivity_plot.ax.set_ylabel("Unconstrained LCOE (€/MWh)")
            data = _retrieve_statistics(steps, "unconstrained_lcoe", output_directory, resolution, breakdown_level=breakdown_level)
        if statistic_name == "premium":
            sensitivity_plot.ax.set_ylabel("Firm kWh premium")
            data = _retrieve_statistics(steps, "premium", output_directory, resolution, breakdown_level=breakdown_level)

        # Plot the data depending on the breakdown level
        if breakdown_level == 0 or sensitivity_config["analysis_type"] == "technology_scenario":
            sensitivity_plot.ax.plot(data, label=label, color=line_color)
        elif breakdown_level == 1:
            if show_cumulative_results:
                sensitivity_plot.ax.plot(data.sum(axis=1), color=colors.tertiary(), label="Total")
            sensitivity_plot.ax.plot(data["production"], color=colors.technology_type("production"), label="Production")
            sensitivity_plot.ax.plot(data["storage"], color=colors.technology_type("storage"), label="Storage")
            sensitivity_plot.ax.legend()
        else:
            if show_cumulative_results:
                sensitivity_plot.ax.plot(data.sum(axis=1), color=colors.tertiary(), label="Total")
            for technology in data:
                sensitivity_plot.ax.plot(data[technology], color=colors.technology(technology), label=utils.format_technology(technology))
            sensitivity_plot.ax.legend()
    if statistic_name == "relative_curtailment":
        data = _retrieve_statistics(steps, "relative_curtailment", output_directory, resolution)
        sensitivity_plot.ax.set_ylabel("Relative curtailment (%)")
        sensitivity_plot.ax.plot(data, label=label, color=line_color)
        sensitivity_plot.format_yticklabels("{:,.0%}")
    if statistic_name == "production_capacity":
        data = _retrieve_statistics(steps, "production_capacity", output_directory, resolution) / 1000
        for production_technology in data:
            sensitivity_plot.ax.plot(data[production_technology], color=colors.technology(production_technology), label=utils.format_technology(production_technology))
        sensitivity_plot.ax.set_ylabel("Production capacity (GW)")
        sensitivity_plot.ax.legend()
    if statistic_name == "storage_capacity":
        storage_capacity_type = st.sidebar.selectbox("Storage capacity type", ["energy", "power"], format_func=utils.format_str)
        data = steps.apply(lambda step: pd.Series(stats.storage_capacity(output_directory / step, resolution, storage_type=storage_capacity_type)))
        data = data / 10 ** 6 if storage_capacity_type == "energy" else data / 10 ** 3
        for storage_technology in data:
            sensitivity_plot.ax.plot(data[storage_technology], color=colors.technology(storage_technology), label=utils.format_technology(storage_technology))
        unit = "TWh" if storage_capacity_type == "energy" else "GW"
        sensitivity_plot.ax.set_ylabel(f"Storage capacity ({unit})")
        sensitivity_plot.ax.legend()
    if statistic_name == "optimization_duration":
        data = steps.apply(lambda step: pd.DataFrame(utils.read_yaml(output_directory / step / "duration.yaml")).sum(axis=1)) / 3600
        cumulative_data = 0
        for index, column_name in enumerate(data.columns):
            cumulative_data += data[column_name]
            line_color = colors.get("blue", (index + 1) * 300)
            sensitivity_plot.ax.fill_between(data[column_name].index, cumulative_data - data[column_name], cumulative_data, label=utils.format_str(column_name), color=line_color)
        sensitivity_plot.ax.set_ylabel("Duration (H)")
        handles, labels = sensitivity_plot.ax.get_legend_handles_labels()
        sensitivity_plot.ax.legend(reversed(handles), reversed(labels))
        sensitivity_plot.ax.set_xlim([data.index.min(), data.index.max()])


def sensitivity(output_directory, resolution):
    """
    Analyze the sensitivity
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_resolution(resolution)

    st.title("⚖️ Sensitivity analysis")

    st.sidebar.header("Options")

    # Get the sensitivity config
    sensitivity_config = utils.read_yaml(output_directory / "sensitivity.yaml")

    # Select an output variable to run the sensitivity analysis on
    statistic_options = ["firm_lcoe", "unconstrained_lcoe", "premium", "relative_curtailment"]
    if sensitivity_config["analysis_type"] != "technology_scenario":
        statistic_options += ["production_capacity", "storage_capacity", "optimization_duration"]
    statistic_name = st.sidebar.selectbox("Output variable", statistic_options, format_func=utils.format_str)

    # Ask for the breakdown level and if the cumulative results should be shown
    breakdown_level = 0
    show_cumulative_results = False
    if statistic_name in ["firm_lcoe", "unconstrained_lcoe", "premium"] and sensitivity_config["analysis_type"] != "technology_scenario":
        breakdown_level_options = {0: "Off", 1: "Production and storage", 2: "Technologies"}
        breakdown_level = st.sidebar.selectbox("Breakdown level", breakdown_level_options, format_func=lambda key: breakdown_level_options[key])
        if breakdown_level in [1, 2]:
            show_cumulative_results = st.sidebar.checkbox("Show cumulative results")

    # Plot the data
    sensitivity_plot = chart.Chart(xlabel=None, ylabel=None)
    if sensitivity_config["analysis_type"] == "technology_scenario":
        for technology_name in utils.sort_technology_names(sensitivity_config["technologies"].keys()):
            label = utils.format_technology(technology_name)
            line_color = colors.technology(technology_name)
            _plot(output_directory / technology_name, resolution, sensitivity_config, sensitivity_plot, statistic_name, breakdown_level, show_cumulative_results, label=label, line_color=line_color)
    else:
        _plot(output_directory, resolution, sensitivity_config, sensitivity_plot, statistic_name, breakdown_level, show_cumulative_results)

    # Set the range of the y-axis
    col1, col2 = st.sidebar.columns(2)
    default_y_limits = sensitivity_plot.ax.get_ylim()
    y_min = col1.number_input("Min y-axis", value=default_y_limits[0])
    y_max = col2.number_input("Max y-axis", value=default_y_limits[1])
    sensitivity_plot.ax.set_ylim([y_min, y_max])

    # Format the axes
    if sensitivity_config["analysis_type"] == "curtailment":
        sensitivity_plot.ax.set_xlabel("Curtailment (%)")
        xticks = np.arange(0, 1.2, 0.2)
        sensitivity_plot.ax.set_xticks(xticks, xticks)
        sensitivity_plot.format_xticklabels("{:,.0%}")
    elif sensitivity_config["analysis_type"] == "climate_years":
        sensitivity_plot.ax.set_xlabel("Number of climate years")
    elif sensitivity_config["analysis_type"] == "technology_scenario":
        sensitivity_plot.ax.legend()
        sensitivity_plot.ax.set_xlabel("Technology scenario")
        sensitivity_plot.ax.set_xticks([-1, 0, 1], ["Conservative", "Moderate", "Advanced"])
    elif sensitivity_config["analysis_type"] == "baseload":
        sensitivity_plot.ax.set_xlabel("Relative baseload (%)")
        sensitivity_plot.format_xticklabels("{:,.0%}")
        sensitivity_plot.ax.set_xlim([0, 1])
    elif sensitivity_config["analysis_type"] == "interconnection_capacity":
        sensitivity_plot.ax.set_xlabel("Relative interconnection capacity (%)")
        sensitivity_plot.format_xticklabels("{:,.0%}")
    elif sensitivity_config["analysis_type"] == "self_sufficiency":
        sensitivity_plot.ax.set_xlabel("Minimum self sufficiency (%)")
        sensitivity_plot.format_xticklabels("{:,.0%}")

    # Plot the sensitivity plot
    sensitivity_plot.display()
    sensitivity_plot.download_button("sensitivity.png")
