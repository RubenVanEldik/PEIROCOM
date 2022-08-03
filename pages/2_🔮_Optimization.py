from datetime import date, datetime, time, timedelta
import numpy as np
import os
import streamlit as st

import optimization
import utils
import validate


# Settings dictionary for the new run
config = {}

# Ask for the name of the this run
config["name"] = st.sidebar.text_input("Name", value=utils.get_next_run_name(), max_chars=50)

# Set the scope options
with st.sidebar.expander("Scope"):
    # Select the model year
    config["model_year"] = st.selectbox("Model year", [2025, 2030], index=1)

    # Select the countries
    countries = utils.read_yaml(utils.path("input", "countries.yaml"))
    country_codes = [country["nuts_2"] for country in countries]
    if st.checkbox("Include all countries", value=True):
        config["country_codes"] = country_codes
    else:
        default_countries = ["NL", "BE", "DE"]
        format_func = lambda nuts_2: utils.get_country_property(nuts_2, "name")
        config["country_codes"] = st.multiselect("Countries", country_codes, default=default_countries, format_func=format_func)

    # Select the range of years that should be modeled
    climate_years = range(1982, 2017)
    config["climate_years"] = {}
    col1, col2 = st.columns(2)
    config["climate_years"]["start"] = col1.selectbox("Start year", climate_years, index=climate_years.index(2016))
    config["climate_years"]["end"] = col2.selectbox("End year", climate_years, index=climate_years.index(2016))

# Set the technology options
with st.sidebar.expander("Technologies"):
    config["technologies"] = {}

    # Select the scenario
    scenario_levels = {-1: "Conservative", 0: "Moderate", 1: "Advanced"}
    scenario_level = st.select_slider("Scenario", options=scenario_levels.keys(), value=0, format_func=lambda key: scenario_levels[key])

    # Select the relative share of baseload
    config["technologies"]["relative_baseload"] = st.slider("Relative baseload", min_value=0.0, max_value=0.95, step=0.05)

    # Select the production technologies
    col1, col2 = st.columns(2)
    col1.subheader("Production")
    config["technologies"]["production"] = {}
    production_technology_options = utils.read_yaml(utils.path("input", "technologies", "production.yaml")).keys()
    for technology in production_technology_options:
        if col1.checkbox(utils.format_technology(technology), value=True):
            config["technologies"]["production"][technology] = scenario_level

    # Select the storage technologies
    col2.subheader("Storage")
    config["technologies"]["storage"] = {}
    storage_technologies_options = utils.read_yaml(utils.path("input", "technologies", "storage.yaml")).keys()
    for technology in storage_technologies_options:
        if col2.checkbox(utils.format_technology(technology), value=True):
            config["technologies"]["storage"][technology] = scenario_level

# Set the interconnection options
with st.sidebar.expander("Interconnections"):
    config["interconnections"] = {"efficiency": {}}
    config["interconnections"]["min_self_sufficiency"] = st.slider("Minimum self sufficiency factor", value=0.8, max_value=1.0, step=0.05)
    config["interconnections"]["relative_capacity"] = st.slider("Relative capacity", value=1.0, max_value=1.5, step=0.05)
    config["interconnections"]["efficiency"]["hvac"] = st.number_input("Efficiency HVAC", value=0.95, max_value=1.0)
    config["interconnections"]["efficiency"]["hvdc"] = st.number_input("Efficiency HVDC", value=0.95, max_value=1.0)

# Set the sensitivity analysis options
with st.sidebar.expander("Sensitivity analysis"):
    # Enable/disable the sensitivity analysis
    sensitivity_analysis_types = {None: "-", "curtailment": "Curtailment", "climate_years": "Climate years", "technology_scenario": "Technology scenario", "baseload": "Baseload", "interconnection_capacity": "Interconnection capacity", "self_sufficiency": "Self sufficiency"}
    sensitivity_analysis_type = st.selectbox("Sensitivity type", sensitivity_analysis_types.keys(), format_func=lambda key: sensitivity_analysis_types[key])

    # Initialize the sensitivity_config if an analysis type has been specified
    if sensitivity_analysis_type is None:
        sensitivity_config = None
    else:
        sensitivity_config = {"analysis_type": sensitivity_analysis_type}

    # Show the relevant input parameters for each sensitivity analysis type
    if sensitivity_analysis_type == "curtailment":
        sensitivity_config["step_factor"] = st.number_input("Step factor", value=1.2, min_value=1.05, step=0.05)
        sensitivity_config["curtailment_range"] = list(st.slider("Curtailment range", value=(0.05, 0.95), min_value=0.01, max_value=0.99))
    elif sensitivity_analysis_type == "climate_years":
        number_of_climate_years = config["climate_years"]["end"] - config["climate_years"]["start"] + 1
        if number_of_climate_years < 3:
            st.warning("The technology scenario sensitivity analysis is only available if more than two climate years have been selected")
        else:
            # Get all possible step sizes that properly fit into the climate years range
            step_size_options = [step for step in range(1, number_of_climate_years) if ((number_of_climate_years - 1) / step) % 1 == 0]
            # Ask for the number of steps and return the preferred step size
            step_size = st.select_slider("Number of steps", step_size_options[::-1], value=1, format_func=lambda step_size: int(((number_of_climate_years - 1) / step_size) + 1))
            # Use the step size to calculate the sensitivity steps and add them to the config
            sensitivity_config["steps"] = {str(step): step for step in range(1, number_of_climate_years + 1, step_size)}
    elif sensitivity_analysis_type == "baseload":
        sensitivity_start, sensitivity_stop = st.slider("Relative baseload range", value=(0.0, 0.95), min_value=0.0, max_value=0.95, step=0.05)
        number_steps = st.slider("Number of steps", value=10, min_value=5, max_value=50)
        sensitity_steps = np.linspace(start=sensitivity_start, stop=sensitivity_stop, num=number_steps)
        sensitivity_config["steps"] = {f"{step:.3f}": float(step) for step in sensitity_steps}
    elif sensitivity_analysis_type == "technology_scenario":
        st.warning("The technology scenario sensitivity analysis has not yet been implemented")
    elif sensitivity_analysis_type == "interconnection_capacity":
        sensitivity_start, sensitivity_stop = st.slider("Interconnection capacity range", value=(0.0, 2.0), min_value=0.0, max_value=2.0, step=0.05)
        number_steps = st.slider("Number of steps", value=10, min_value=5, max_value=50)
        sensitity_steps = np.linspace(start=sensitivity_start, stop=sensitivity_stop, num=number_steps)
        sensitivity_config["steps"] = {f"{step:.3f}": float(step) for step in sensitity_steps}
    elif sensitivity_analysis_type == "self_sufficiency":
        sensitivity_start, sensitivity_stop = st.slider("Self sufficiency range", value=(0.0, 1.0), min_value=0.0, max_value=1.0, step=0.05)
        number_steps = st.slider("Number of steps", value=10, min_value=5, max_value=50)
        sensitity_steps = np.linspace(start=sensitivity_start, stop=sensitivity_stop, num=number_steps)
        sensitivity_config["steps"] = {f"{step:.3f}": float(step) for step in sensitity_steps}


# Set the time discretization parameters
with st.sidebar.expander("Time discretization"):
    config["time_discretization"] = {}

    # Select the resolution steps
    resolutions = ["1H", "2H", "4H", "6H", "12H", "1D"]
    config["time_discretization"]["resolution_stages"] = st.multiselect("Resolution stages", resolutions, default=["1D", "1H"], format_func=utils.format_resolution)

    # Select the relative boundary propagation
    multiple_stages = len(config["time_discretization"]["resolution_stages"]) > 1
    config["time_discretization"]["capacity_propagation"] = st.slider("Capacity propagation", value=1.0, disabled=not multiple_stages)
    config["time_discretization"]["soc_propagation"] = st.slider("SoC propagation", value=1.0, disabled=not multiple_stages)


# Set the optimization parameters
with st.sidebar.expander("Optimization parameters"):
    config["optimization"] = {}

    # Select the optimization method
    method_options = {-1: "Automatic", 0: "Primal simplex", 1: "Dual simplex", 2: "Barrier", 3: "Concurrent", 4: "Deterministic concurrent", 5: "Deterministic concurrent simplex"}
    config["optimization"]["method"] = st.selectbox("Method", method_options.keys(), index=3, format_func=lambda key: method_options[key])

    # Select the thread count
    cpu_count = os.cpu_count()
    config["optimization"]["thread_count"] = st.slider("Thread count", value=cpu_count, min_value=1, max_value=cpu_count)

    # Check if the optimization data should be stored
    config["optimization"]["store_model"] = st.checkbox("Store optimization data")


# Check if a notification should be send and results uploaded when the model finishes
dropbox_keys_available = utils.getenv("DROPBOX_APP_KEY") and utils.getenv("DROPBOX_APP_SECRET") and utils.getenv("DROPBOX_REFRESH_TOKEN")
config["upload_results"] = st.sidebar.checkbox("Upload results to Dropbox", disabled=not dropbox_keys_available)
config["send_notification"] = st.sidebar.checkbox("Send a notification when finished", disabled=not utils.getenv("PUSHOVER_USER_KEY") or not utils.getenv("PUSHOVER_API_TOKEN"))


# Run the model if the button has been pressed
invalid_config = not validate.is_config(config)
invalid_sensitivity_config = bool(sensitivity_config) and not validate.is_sensitivity_config(sensitivity_config)
if st.sidebar.button("Run model", disabled=invalid_config or invalid_sensitivity_config):
    if config["name"] in utils.get_previous_runs(include_uncompleted_runs=True):
        st.error(f"There is already a run called '{config['name']}'")
    elif sensitivity_config:
        optimization.run_sensitivity(config, sensitivity_config)
    else:
        optimization.run(config, output_directory=utils.path("output", config["name"]))
