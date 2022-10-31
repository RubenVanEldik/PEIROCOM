from copy import deepcopy
import pandas as pd
import streamlit as st

import stats
import utils
import validate

from .optimize import optimize
from .status import Status


def run(config, *, status=None, output_directory):
    """
    Run the model with the given configuration file
    """
    assert validate.is_config(config)
    assert validate.is_directory_path(output_directory)

    # Initialize the run directory, so other runs will already increment their ID (parents=True is required for sensitivity analyses)
    output_directory.mkdir(parents=True)

    # Check if this run is not part of a sensitivity analysis
    is_standalone_run = status is None

    # Initialize a status object if not defined yet
    if status is None:
        status = Status()

    results = {}
    previous_resolution = None
    for resolution in utils.get_sorted_resolution_stages(config, descending=True):
        results[resolution] = optimize(config, resolution=resolution, previous_resolution=previous_resolution, status=status, output_directory=output_directory)

        # Store the duration of all resolutions after each optimization
        duration = {resolution: results[resolution]["duration"] for resolution in results}
        utils.write_yaml(output_directory / "duration.yaml", duration, exist_ok=True)

        # Stop the run if an error occured during the optimization of one of the resolutions
        error_message = results[resolution].get("error_message")
        if error_message:
            status.update(error_message, status_type="error")
            if config["send_notification"]:
                utils.send_notification(error_message)
            return error_message

        previous_resolution = resolution

    # Store the config as a .YAML file
    utils.write_yaml(output_directory / "config.yaml", config)

    # Upload the output directory to Dropbox
    if config["upload_results"]:
        status.update(f"Uploading the results to Dropbox")
        utils.upload_to_dropbox(output_directory, output_directory)

    # Set the final status and send a message
    if is_standalone_run:
        status.update(f"Optimization has finished and results are stored", status_type="success")
        if config["send_notification"]:
            utils.send_notification(f"Optimization '{config['name']}' has finished")


def run_sensitivity(config, sensitivity_config):
    """
    Run the model for each step in the sensitivity analysis
    """
    assert validate.is_config(config)
    assert validate.is_sensitivity_config(sensitivity_config)

    status = Status()
    output_directory = utils.path("output", config["name"])

    # Run a specific sensitivity analysis for the curtailment
    if sensitivity_config["analysis_type"] == "curtailment":
        # Calculate the optimal storage costs
        st.subheader(f"Sensitivity run 1.000")
        highest_resolution = utils.get_sorted_resolution_stages(config)[0]
        run(config, status=status, output_directory=output_directory / "1.000")
        optimal_storage_costs = {resolution: stats.firm_lcoe(output_directory / "1.000", resolution, breakdown_level=1)["storage"] for resolution in config["time_discretization"]["resolution_stages"]}

        # Send the notification
        if config["send_notification"]:
            utils.send_notification(f"Optimization 1.000 of '{config['name']}' has finished")

        # Add the steps dictionary to the sensitivity config
        sensitivity_config["steps"] = {"1.000": 1.0}

        # Run the sensitivity analysis incrementally for storage cost values both larger and smaller than the optimal
        for step_factor in [1 / sensitivity_config["step_factor"], sensitivity_config["step_factor"]]:
            # Set the first relative_storage_costs to the step factor
            relative_storage_costs = step_factor

            while True:
                step_key = f"{relative_storage_costs:.3f}"
                st.subheader(f"Sensitivity run {step_key}")

                # Set the total storage costs for this step
                step_config = deepcopy(config)
                storage_costs_step = {resolution: float(relative_storage_costs * optimal_storage_costs[resolution]) for resolution in optimal_storage_costs}
                utils.set_nested_key(step_config, "fixed_storage.costs", storage_costs_step)
                fixed_storage_costs_direction = "gte" if step_factor > 1 else "lte" if step_factor < 1 else None
                utils.set_nested_key(step_config, "fixed_storage.direction", fixed_storage_costs_direction)

                # Run the optimization
                output_directory_step = output_directory / step_key
                error_message = run(step_config, status=status, output_directory=output_directory_step)

                # Send the notification
                if config["send_notification"]:
                    utils.send_notification(f"Optimization {step_key} of '{config['name']}' has finished")

                # Break the while loop if the model was infeasible
                if error_message == "The model was infeasible":
                    break

                # Add the step to the sensitivity config
                sensitivity_config["steps"][step_key] = relative_storage_costs

                # Calculate the curtailment
                current_temporal_results = utils.get_temporal_results(output_directory_step, highest_resolution, group="all")
                current_curtailment = current_temporal_results.curtailed_MW.sum() / current_temporal_results.production_total_MW.sum()

                # Break the while loop if the premium exceeds the maximum premium
                firm_lcoe = stats.firm_lcoe(output_directory_step, highest_resolution)
                if firm_lcoe >= sensitivity_config["max_lcoe"]:
                    break

                # Update the relative storage capacity for the next pass
                relative_storage_costs *= step_factor

    # Run a specific sensitivity analysis for the technology scenarios
    elif sensitivity_config["analysis_type"] == "technology_scenario":
        # Loop over all technologies
        for technology_name, technology_type in sensitivity_config["technologies"].items():
            st.subheader(utils.format_technology(technology_name))

            # Loop over each sensitivity analysis step
            for step_key, step_value in sensitivity_config["steps"].items():
                step_number = list(sensitivity_config["steps"].keys()).index(step_key) + 1
                number_of_steps = len(sensitivity_config["steps"])
                st.markdown(f"#### Sensitivity run {step_number}/{number_of_steps}")

                # Make a copy of the config, change the config parameters for the specific technology and run the optimization
                step_config = deepcopy(config)
                utils.set_nested_key(step_config, f"technologies.{technology_type}.{technology_name}", step_value)
                run(step_config, status=status, output_directory=output_directory / technology_name / step_key)

                # If enabled, send a notification
                if config["send_notification"]:
                    utils.send_notification(f"Optimization {step_number}/{number_of_steps} ({technology_name}) of '{config['name']}' has finished")

    # Otherwise run the general sensitivity analysis
    else:
        # Loop over each sensitivity analysis step
        for step_key, step_value in sensitivity_config["steps"].items():
            step_number = list(sensitivity_config["steps"].keys()).index(step_key) + 1
            number_of_steps = len(sensitivity_config["steps"])
            st.subheader(f"Sensitivity run {step_number}/{number_of_steps}")
            step_config = deepcopy(config)

            # Change the config parameters relevant for the current analysis type for this step
            if sensitivity_config["analysis_type"] == "climate_years":
                last_climate_year = utils.get_nested_key(step_config, "climate_years.end")
                utils.set_nested_key(step_config, "climate_years.start", last_climate_year - (step_value - 1))
            elif sensitivity_config["analysis_type"] == "baseload":
                utils.set_nested_key(step_config, "technologies.relative_baseload", step_value)
            elif sensitivity_config["analysis_type"] == "interconnection_capacity":
                utils.set_nested_key(step_config, "interconnections.relative_capacity", step_value)
            elif sensitivity_config["analysis_type"] == "interconnection_efficiency":
                utils.set_nested_key(step_config, "interconnections.efficiency.hvac", step_value)
                utils.set_nested_key(step_config, "interconnections.efficiency.hvdc", step_value)
            elif sensitivity_config["analysis_type"] == "self_sufficiency":
                utils.set_nested_key(step_config, "interconnections.min_self_sufficiency", step_value)

            # Run the optimization
            run(step_config, status=status, output_directory=output_directory / step_key)

            # If enabled, send a notification
            if config["send_notification"]:
                utils.send_notification(f"Optimization {step_number}/{number_of_steps} of '{config['name']}' has finished")

    # Store the sensitivity config file
    utils.write_yaml(output_directory / "sensitivity.yaml", sensitivity_config)

    # Upload the sensitivity config to Dropbox
    if config["upload_results"]:
        utils.upload_to_dropbox(output_directory / "sensitivity.yaml", output_directory)

    # Set the final status
    status.update(f"Sensitivity analysis has finished and results are stored", status_type="success")
    if config["send_notification"]:
        utils.send_notification(f"The '{config['name']}' sensitivity analysis has finished")
