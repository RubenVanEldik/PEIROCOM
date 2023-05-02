import numpy as np
import pandas as pd
import streamlit as st

import chart
import colors
import utils
import validate


@utils.cache
def _retrieve_statistics(steps, method, output_directory, **kwargs):
    """
    Retrieve the statistics for all steps
    """
    assert validate.is_series(steps)
    assert validate.is_string(method)
    assert validate.is_directory_path(output_directory)

    # Initialize the progress bar
    progress_bar = st.progress(0.0)

    # Create a 1-item list so the index can be updated from within the function
    index = [0]

    def _apply_step(step):
        # Retrieve the statistic for this step
        step_data = getattr(utils.previous_run, method)(output_directory / step, **kwargs)
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


def _plot(output_directory, sensitivity_config, sensitivity_plot, statistic_name, *, label=None, line_color=colors.primary()):
    """
    Analyze the sensitivity
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_sensitivity_config(sensitivity_config)
    assert validate.is_chart(sensitivity_plot)
    assert validate.is_string(statistic_name)
    assert validate.is_string(label, required=False)
    assert validate.is_color(line_color)

    # Create a Series with the sensitivity steps as rows
    if sensitivity_config["analysis_type"] == "curtailment":
        # Use the actual curtailment as the index
        step_index = [utils.previous_run.relative_curtailment(output_directory / step) for step in sensitivity_config["steps"].keys()]
    else:
        step_index = sensitivity_config["steps"].values()
    steps = pd.Series(data=sensitivity_config["steps"].keys(), index=step_index).sort_index()

    # Add the output for the sensitivity steps to the sensitivity plot
    if statistic_name in ["firm_lcoe", "unconstrained_lcoe", "premium", "annual_costs"]:
        # Ask for the breakdown level
        breakdown_level_options = {0: "Off", 1: "Technology types", 2: "Technologies"}
        breakdown_level = st.sidebar.selectbox("Breakdown level", breakdown_level_options, index=1, format_func=lambda key: breakdown_level_options[key])

        # Get the data and set the label
        if statistic_name == "firm_lcoe":
            sensitivity_plot.axs.set_ylabel("Firm LCOE (€/MWh)")
            data = _retrieve_statistics(steps, "firm_lcoe", output_directory, breakdown_level=breakdown_level)
        elif statistic_name == "unconstrained_lcoe":
            sensitivity_plot.axs.set_ylabel("Unconstrained LCOE (€/MWh)")
            data = _retrieve_statistics(steps, "unconstrained_lcoe", output_directory, breakdown_level=breakdown_level)
        elif statistic_name == "premium":
            sensitivity_plot.axs.set_ylabel("Firm kWh premium")
            data = _retrieve_statistics(steps, "premium", output_directory, breakdown_level=breakdown_level)
        elif statistic_name == "annual_costs":
            data = _retrieve_statistics(steps, "annual_costs", output_directory, breakdown_level=breakdown_level)
            maximum_annual_costs = data.max() if breakdown_level == 0 else data.sum(axis=1).max()
            if maximum_annual_costs > 10 ** 12:
                data /= 10 ** 12
                unit = "T€"
            elif maximum_annual_costs > 10 ** 9:
                data /= 10 ** 9
                unit = "B€"
            else:
                data /= 10 ** 6
                unit = "M€"
            sensitivity_plot.axs.set_ylabel(f"Annual costs ({unit})")
        else:
            raise ValueError("'statistic_name has to be 'firm_lcoe', 'unconstrained_lcoe', or 'premium'")

        # Remove all technology (types) that have only zeroes throughout the sensitivity analysis
        if isinstance(data, pd.DataFrame):
            data = data.loc[:, (data != 0).any()]

        # Plot the data depending on the breakdown level
        if breakdown_level == 0:
            if st.sidebar.checkbox("Fit a curve on the data"):
                sensitivity_plot.axs.scatter(data.index, data, label=label, color=colors.primary(alpha=0.5), linewidths=0)
                try:
                    # Get the regression function as a string and make it a lambda function
                    regression_function_string = st.sidebar.text_input("Curve formula", value="a + b * x", help="Use a, b, and c as variables and use x for the x-value")
                    regression_function = eval(f"lambda x, a, b, c: {regression_function_string}")

                    # Fit the curve
                    regression_line, parameters = utils.fit_curve(pd.Series(data.index), data, function=regression_function, return_parameters=True)

                    # Format the regression string
                    regression_function_string_formatted = f"${regression_function_string}$"
                    for old_substring, new_substring in [("a ", f"{parameters[0]:.2f} "), (" b ", f" {parameters[1]:.2f} "), (" c ", f" {parameters[2]:.2f} "), (" * ", r" \cdot ")]:
                        regression_function_string_formatted = regression_function_string_formatted.replace(old_substring, new_substring)

                    # Plot the regression line
                    sensitivity_plot.axs.plot(regression_line, color=colors.get("red", 600), label=regression_function_string_formatted)
                    sensitivity_plot.add_legend()
                except (NameError, TypeError, SyntaxError):
                    st.sidebar.error("The function is not valid")
            else:
                sensitivity_plot.axs.plot(data, label=label, color=line_color)
        elif breakdown_level == 1:
            cumulative_data = 0
            for technology_type in sorted(data.columns, key=lambda value: {"hydropower": 0, "ires": 1, "storage": 2}.get(value, 3)):
                # Don't add the technology if it only has 0 values
                if data[technology_type].abs().max() == 0:
                    continue

                # Add the data to the cumulative data
                cumulative_data += data[technology_type]

                # Add the area to the chart
                sensitivity_plot.axs.fill_between(data[technology_type].index, cumulative_data - data[technology_type], cumulative_data, label=utils.format_str(technology_type), facecolor=colors.technology_type(technology_type))

            # Add the legend
            sensitivity_plot.add_legend()

            # Set the x and y limits to the limits of the data so there is no padding in the area chart
            sensitivity_plot.axs.set_xlim([round(data.index.min(), 2), round(data.index.max(), 2)])
            sensitivity_plot.axs.set_ylim([0, sensitivity_plot.axs.set_ylim()[1]])
        else:
            cumulative_data = 0
            for technology in data:
                cumulative_data += data[technology]
                sensitivity_plot.axs.fill_between(data[technology].index, cumulative_data - data[technology], cumulative_data, label=utils.format_technology(technology), facecolor=colors.technology(technology))

            # Add the legend
            sensitivity_plot.add_legend()

            # Set the x and y limits to the limits of the data so there is no padding in the area chart
            sensitivity_plot.axs.set_xlim([round(data.index.min(), 2), round(data.index.max(), 2)])
            sensitivity_plot.axs.set_ylim([0, sensitivity_plot.axs.set_ylim()[1]])
    if statistic_name == "relative_curtailment":
        data = _retrieve_statistics(steps, "relative_curtailment", output_directory)
        sensitivity_plot.axs.set_ylabel("Relative curtailment (%)")
        sensitivity_plot.axs.plot(data, label=label, color=line_color)
        sensitivity_plot.format_yticklabels("{:,.0%}")
    if statistic_name == "ires_capacity":
        data = _retrieve_statistics(steps, "ires_capacity", output_directory) / 1000

        cumulative_data = 0
        for ires_technology in data:
            cumulative_data += data[ires_technology]
            sensitivity_plot.axs.fill_between(data[ires_technology].index, cumulative_data - data[ires_technology], cumulative_data, label=utils.format_technology(ires_technology), facecolor=colors.technology(ires_technology))
        sensitivity_plot.axs.set_ylabel("IRES capacity (GW)")
        sensitivity_plot.add_legend()

        # Set the x and y limits to the limits of the data so there is no padding in the area chart
        sensitivity_plot.axs.set_xlim([round(data.index.min(), 2), round(data.index.max(), 2)])
        sensitivity_plot.axs.set_ylim([0, sensitivity_plot.axs.set_ylim()[1]])
    if statistic_name == "storage_capacity":
        storage_capacity_attribute = st.sidebar.selectbox("Storage capacity attribute", ["energy", "power"], format_func=utils.format_str)
        data = steps.apply(lambda step: utils.previous_run.storage_capacity(output_directory / step)[storage_capacity_attribute])
        data = data / 10 ** 6 if storage_capacity_attribute == "energy" else data / 10 ** 3

        cumulative_data = 0
        for storage_technology in data:
            cumulative_data += data[storage_technology]
            sensitivity_plot.axs.fill_between(data[storage_technology].index, cumulative_data - data[storage_technology], cumulative_data, label=utils.format_technology(storage_technology), facecolor=colors.technology(storage_technology))
        unit = "TWh" if storage_capacity_attribute == "energy" else "GW"
        sensitivity_plot.axs.set_ylabel(f"Storage capacity ({unit})")
        sensitivity_plot.add_legend()

        # Set the x and y limits to the limits of the data so there is no padding in the area chart
        sensitivity_plot.axs.set_xlim([round(data.index.min(), 2), round(data.index.max(), 2)])
        sensitivity_plot.axs.set_ylim([0, sensitivity_plot.axs.set_ylim()[1]])
    if statistic_name == "optimization_duration":
        data = steps.apply(lambda step: utils.read_csv(output_directory / step / "model" / "duration.csv", index_col=0).sum(axis=1)) / 3600
        cumulative_data = 0
        for index, column_name in enumerate(data.columns):
            cumulative_data += data[column_name]
            line_color = colors.get("blue", (index + 1) * 300)
            sensitivity_plot.axs.fill_between(data[column_name].index, cumulative_data - data[column_name], cumulative_data, label=utils.format_str(column_name), color=line_color)
        sensitivity_plot.axs.set_ylabel("Duration (H)")
        sensitivity_plot.axs.set_xlim([data.index.min(), data.index.max()])
        sensitivity_plot.axs.set_ylim([0, sensitivity_plot.axs.set_ylim()[1]])
        sensitivity_plot.add_legend()

    # Return the data, so it can be shown in a table
    return data


def sensitivity(output_directory):
    """
    Analyze the sensitivity
    """
    assert validate.is_directory_path(output_directory)

    st.title("⚖️ Sensitivity analysis")

    st.sidebar.header("Options")

    # Get the sensitivity config
    sensitivity_config = utils.read_yaml(output_directory / "sensitivity.yaml")

    # Select an output variable to run the sensitivity analysis on
    statistic_options = ["firm_lcoe", "unconstrained_lcoe", "premium", "annual_costs", "relative_curtailment", "ires_capacity", "storage_capacity", "optimization_duration"]
    statistic_name = st.sidebar.selectbox("Output variable", statistic_options, format_func=utils.format_str)

    # Plot the data
    sensitivity_plot = chart.Chart(xlabel=None, ylabel=None)
    sensitivity_data = _plot(output_directory, sensitivity_config, sensitivity_plot, statistic_name)

    # Set the range of the y-axis
    col1, col2 = st.sidebar.columns(2)
    default_y_limits = sensitivity_plot.axs.get_ylim()
    y_min = col1.number_input("Min y-axis", value=default_y_limits[0])
    y_max = col2.number_input("Max y-axis", value=default_y_limits[1])
    sensitivity_plot.axs.set_ylim([y_min, y_max])

    # Format the axes
    if sensitivity_config["analysis_type"] == "curtailment":
        sensitivity_plot.axs.set_xlabel("Curtailment (%)")
        x_ticks = np.arange(0, 1.2, 0.2)
        sensitivity_plot.axs.set_xticks(x_ticks, x_ticks)
        sensitivity_plot.format_xticklabels("{:,.0%}")
    elif sensitivity_config["analysis_type"] == "climate_years":
        sensitivity_plot.axs.set_xlabel("Number of climate years")
    elif sensitivity_config["analysis_type"] == "technology_scenario":
        sensitivity_plot.axs.set_xlabel("Technology scenario")
        sensitivity_plot.axs.set_xticks([-1, 0, 1], ["Conservative", "Moderate", "Advanced"])
    elif sensitivity_config["analysis_type"] == "hydrogen_demand":
        sensitivity_plot.axs.set_xlabel(r"Hydrogen demand ($\%_{electricity\ demand}$)")
        sensitivity_plot.format_xticklabels("{:,.0%}")
    elif sensitivity_config["analysis_type"] == "hydropower_capacity":
        sensitivity_plot.axs.set_xlabel(r"Hydropower capacity ($\%_{current}$)")
        sensitivity_plot.format_xticklabels("{:,.0%}")
    elif sensitivity_config["analysis_type"] == "interconnection_capacity":
        sensitivity_plot.axs.set_xlabel("Relative interconnection capacity (%)")
        sensitivity_plot.format_xticklabels("{:,.0%}")
    elif sensitivity_config["analysis_type"] == "interconnection_efficiency":
        sensitivity_plot.axs.set_xlabel("Interconnection efficiency (%)")
        sensitivity_plot.format_xticklabels("{:,.0%}")
    elif sensitivity_config["analysis_type"] == "min_self_sufficiency":
        sensitivity_plot.axs.set_xlabel("Minimum self-sufficiency (%)")
        sensitivity_plot.format_xticklabels("{:,.0%}")
    elif sensitivity_config["analysis_type"] == "max_self_sufficiency":
        sensitivity_plot.axs.set_xlabel("Maximum self-sufficiency (%)")
        sensitivity_plot.format_xticklabels("{:,.0%}")
    elif sensitivity_config["analysis_type"] == "barrier_convergence_tolerance":
        sensitivity_plot.axs.set_xlabel("Barrier convergence tolerance")

    # Plot the sensitivity plot
    sensitivity_plot.display()
    sensitivity_plot.download_button("sensitivity.png")

    # Show the sensitivity data as a table
    with st.expander("Data points"):
        st.table(sensitivity_data)
