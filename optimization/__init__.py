from copy import deepcopy
import pandas as pd
import streamlit as st

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
        utils.write_yaml(output_directory / "duration.yaml", duration, allow_overwrite=True)

        # Stop the run if an error occured during the optimization of one of the resolutions
        error_message = results[resolution].get("error_message")
        if error_message:
            status.update(error_message, type="error")
            return

        previous_resolution = resolution

    # Store the config as a .YAML file
    utils.write_yaml(output_directory / "config.yaml", config)

    # Set the final status and send a message
    if is_standalone_run:
        status.update(f"Optimization has finished and results are stored", type="success")
        utils.send_notification(f"Optimization '{config['name']}' has finished")


def run_sensitivity(config, sensitivity_config):
    """
    Run the model for each step in the sensitivity analysis
    """
    assert validate.is_config(config)
    assert validate.is_sensitivity_config(sensitivity_config)

    status = Status()
    output_directory = utils.path("output", config["name"])

    # Loop over each sensitivity analysis step
    for step_key, step_value in sensitivity_config["steps"].items():
        step_number = list(sensitivity_config["steps"].keys()).index(step_key) + 1
        number_of_steps = len(sensitivity_config["steps"])
        st.subheader(f"Sensitivity run {step_number}/{number_of_steps}")
        step_config = deepcopy(config)

        # Change the config parameters relevant for the current analysis type for this step
        if sensitivity_config["analysis_type"] == "curtailment":
            utils.set_nested_key(step_config, "relative_curtailment", step_value)
        elif sensitivity_config["analysis_type"] == "climate_years":
            last_climate_year = utils.get_nested_key(step_config, "climate_years.end")
            utils.set_nested_key(step_config, "climate_years.start", last_climate_year - (step_value - 1))
        elif sensitivity_config["analysis_type"] == "variables":
            for variable_key in sensitivity_config["variables"]:
                variable_value = utils.get_nested_key(step_config, variable_key)
                utils.set_nested_key(step_config, variable_key, variable_value * step_value)

        # Run the optimization
        run(step_config, status=status, output_directory=output_directory / step_key)
        utils.send_notification(f"Optimization {step_number}/{number_of_steps} of '{config['name']}' has finished")

    # Store the sensitivity config file
    utils.write_yaml(output_directory / "sensitivity.yaml", sensitivity_config)

    # Set the final status
    status.update(f"Sensitivity analysis has finished and results are stored", type="success")
