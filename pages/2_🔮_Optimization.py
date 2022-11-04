from datetime import date, datetime, time, timedelta
import numpy as np
import os
import streamlit as st

import optimization
import utils
import validate

# Set the page config
st.set_page_config(page_title="Optimization - PEIROCOM", page_icon="🔮")

# Set a help message if it's deployed as a demo
demo_disabled_message = "This feature is not available in the online demo" if utils.is_demo else None

# Settings dictionary for the new run
config = {}

# Ask for the name of the this run
config["name"] = st.sidebar.text_input("Name", value=utils.get_next_run_name(), max_chars=50)

# Set the scope options
with st.sidebar.expander("Scope"):
    # Show a warning message if it's deployed as a demo
    if utils.is_demo:
        st.warning("**This is a demo**\n\nA maximum of 3 countries and 1 year can be modeled simultaneously. Download the model from Github to run larger simulations.")

    # Select the model year
    config["model_year"] = st.selectbox("Model year", [2025, 2030], index=1)

    # Select the countries
    countries = utils.read_yaml(utils.path("input", "countries.yaml"))
    country_codes = [country["nuts_2"] for country in countries]
    if not utils.is_demo and st.checkbox("Include all countries", value=True):
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

    # Check if the config exceeds the demo bounds
    exceeds_demo = utils.is_demo and (config["climate_years"]["end"] > config["climate_years"]["start"] or len(config["country_codes"]) > 3)

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
    sensitivity_analysis_types = ["-", "curtailment", "climate_years", "technology_scenario", "baseload", "interconnection_capacity", "interconnection_efficiency", "self_sufficiency"]
    sensitivity_analysis_type = st.selectbox("Sensitivity type", sensitivity_analysis_types, format_func=utils.format_str, disabled=utils.is_demo, help=demo_disabled_message)

    # Initialize the sensitivity_config if an analysis type has been specified
    if sensitivity_analysis_type is "-":
        sensitivity_config = None
    else:
        sensitivity_config = {"analysis_type": sensitivity_analysis_type}

    # Show the relevant input parameters for each sensitivity analysis type
    if sensitivity_analysis_type == "curtailment":
        sensitivity_config["step_factor"] = st.number_input("Step factor", value=1.2, min_value=1.05, step=0.05)
        sensitivity_config["max_lcoe"] = st.number_input("Maximum LCOE (€/MWh)", value=800, min_value=1, max_value=2000)
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
        number_steps = st.slider("Number of steps", value=10, min_value=3, max_value=50)
        sensitity_steps = np.linspace(start=sensitivity_start, stop=sensitivity_stop, num=number_steps)
        sensitivity_config["steps"] = {f"{step:.3f}": float(step) for step in sensitity_steps}
    elif sensitivity_analysis_type == "technology_scenario":
        number_steps = st.slider("Number of steps", value=10, min_value=3, max_value=50)
        sensitity_steps = np.linspace(start=-1, stop=1, num=number_steps)
        sensitivity_config["steps"] = {f"{step:.3f}": float(step) for step in sensitity_steps}
        # Select the technologies
        technology_names = {technology_name: technology_type for technology_type in ["production", "storage"] for technology_name in config["technologies"][technology_type]}
        selected_technologies = st.multiselect("Technologies", technology_names, format_func=utils.format_technology)
        sensitivity_config["technologies"] = {technology_name: technology_names[technology_name] for technology_name in selected_technologies}
    elif sensitivity_analysis_type == "interconnection_capacity":
        sensitivity_start, sensitivity_stop = st.slider("Interconnection capacity range", value=(0.0, 2.0), min_value=0.0, max_value=2.0, step=0.05)
        number_steps = st.slider("Number of steps", value=10, min_value=3, max_value=50)
        sensitity_steps = np.linspace(start=sensitivity_start, stop=sensitivity_stop, num=number_steps)
        sensitivity_config["steps"] = {f"{step:.3f}": float(step) for step in sensitity_steps}
    elif sensitivity_analysis_type == "interconnection_efficiency":
        sensitivity_start, sensitivity_stop = st.slider("Interconnection efficiency range", value=(0.8, 1.0), min_value=0.05, max_value=1.0, step=0.05)
        number_steps = st.slider("Number of steps", value=10, min_value=3, max_value=50)
        sensitity_steps = np.linspace(start=sensitivity_start, stop=sensitivity_stop, num=number_steps)
        sensitivity_config["steps"] = {f"{step:.3f}": float(step) for step in sensitity_steps}
    elif sensitivity_analysis_type == "self_sufficiency":
        sensitivity_start, sensitivity_stop = st.slider("Self sufficiency range", value=(0.0, 1.0), min_value=0.0, max_value=1.0, step=0.05)
        number_steps = st.slider("Number of steps", value=10, min_value=3, max_value=50)
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
    config["time_discretization"]["temporal_propagation"] = st.slider("Temporal propagation", value=1.0, disabled=not multiple_stages)


# Set the optimization parameters
with st.sidebar.expander("Optimization parameters"):
    config["optimization"] = {}

    # Select the optimization method
    method_options = {-1: "Automatic", 0: "Primal simplex", 1: "Dual simplex", 2: "Barrier", 3: "Concurrent", 4: "Deterministic concurrent", 5: "Deterministic concurrent simplex"}
    config["optimization"]["method"] = st.selectbox("Method", method_options.keys(), index=3, format_func=lambda key: method_options[key])

    # Select the barrier convergence tolerance
    config["optimization"]["barrier_convergence_tolerance"] = st.select_slider("Barrier convergence tolerance", options=[10 ** i for i in range(-6, 1)], value=0.01, disabled=config["optimization"]["method"] != 2)

    # Select the thread count
    cpu_count = os.cpu_count()
    default_thread_count = 1 if utils.is_demo else cpu_count
    config["optimization"]["thread_count"] = st.slider("Thread count", value=default_thread_count, min_value=1, max_value=cpu_count, disabled=utils.is_demo, help=demo_disabled_message)

    # Check if the optimization data should be stored
    config["optimization"]["store_model"] = st.checkbox("Store optimization data", disabled=utils.is_demo, help=demo_disabled_message)


# Check if a notification should be send and results uploaded when the model finishes
dropbox_keys_available = utils.get_env("DROPBOX_APP_KEY") and utils.get_env("DROPBOX_APP_SECRET") and utils.get_env("DROPBOX_REFRESH_TOKEN")
config["upload_results"] = st.sidebar.checkbox("Upload results to Dropbox", disabled=not dropbox_keys_available or utils.is_demo, help=demo_disabled_message)
config["send_notification"] = st.sidebar.checkbox("Send a notification when finished", disabled=not utils.get_env("PUSHOVER_USER_KEY") or not utils.get_env("PUSHOVER_API_TOKEN") or utils.is_demo, help=demo_disabled_message)


# Run the model if the button has been pressed
invalid_config = not validate.is_config(config)
invalid_sensitivity_config = bool(sensitivity_config) and not validate.is_sensitivity_config(sensitivity_config)
if st.sidebar.button("Run model", type="primary", disabled=invalid_config or invalid_sensitivity_config or exceeds_demo):
    if config["name"] in utils.get_previous_runs(include_uncompleted_runs=True):
        st.error(f"There is already a run called '{config['name']}'")
    elif sensitivity_config:
        optimization.run_sensitivity(config, sensitivity_config)
    else:
        optimization.run(config, output_directory=utils.path("output", config["name"]))
