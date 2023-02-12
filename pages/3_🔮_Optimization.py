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
    config["scenario"] = st.selectbox("Scenario", utils.get_scenarios(), index=1)

    # Select the countries
    countries = utils.read_yaml(utils.path("input", "countries.yaml"))
    country_codes = [country["nuts2"] for country in countries]
    map_country_name_to_code = lambda nuts2: utils.get_country_property(nuts2, "name")
    if not utils.is_demo and st.checkbox("Include all countries", value=True):
        config["country_codes"] = country_codes
    else:
        config["country_codes"] = st.multiselect("Countries", country_codes, format_func=map_country_name_to_code)

    # Sort the countries by name
    config["country_codes"] = sorted(config["country_codes"], key=map_country_name_to_code)

    # Select the range of years that should be modeled
    climate_years = range(1982, 2017)
    config["climate_years"] = {}
    col1, col2 = st.columns(2)
    config["climate_years"]["start"] = col1.selectbox("Start year", climate_years, index=climate_years.index(2016))
    config["climate_years"]["end"] = col2.selectbox("End year", climate_years, index=climate_years.index(2016))

    # Select the resolution
    resolutions = [f"{i}H" for i in range(24, 0, -1) if 24 % i == 0]
    config["resolution"] = st.select_slider("Resolution", resolutions, value="1H", format_func=utils.format_resolution)

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

    # Get the technology names
    ires_technology_options = utils.get_technologies(technology_type="ires").keys()
    hydropower_technologies_options = utils.get_technologies(technology_type="hydropower").keys()
    storage_technologies_options = utils.get_technologies(technology_type="storage").keys()

    # Create the technology tabs
    if hydropower_technologies_options:
        ires_tab, storage_tab, hydropower_tab = st.tabs(["IRES", "Hydropower", "Storage"])
    else:
        ires_tab, storage_tab = st.tabs(["IRES", "Storage"])

    # Select the IRES technologies
    config["technologies"]["ires"] = {}
    for technology in ires_technology_options:
        if ires_tab.checkbox(utils.format_technology(technology), value=True):
            config["technologies"]["ires"][technology] = scenario_level

    # Select the hydropower technologies
    config["technologies"]["hydropower"] = {}
    for technology in hydropower_technologies_options:
        if hydropower_tab.checkbox(utils.format_technology(technology), value=True):
            config["technologies"]["hydropower"][technology] = scenario_level

    # Select the storage technologies
    config["technologies"]["storage"] = {}
    for technology in storage_technologies_options:
        if storage_tab.checkbox(utils.format_technology(technology), value=True):
            config["technologies"]["storage"][technology] = scenario_level


# Set the interconnection options
with st.sidebar.expander("Interconnections"):
    config["interconnections"] = {"efficiency": {}}
    min_self_sufficiency, max_self_sufficiency = st.slider("Self-sufficiency range", value=(0.8, 1.5), max_value=2.0, step=0.05)
    config["interconnections"]["min_self_sufficiency"] = min_self_sufficiency
    config["interconnections"]["max_self_sufficiency"] = max_self_sufficiency
    config["interconnections"]["relative_capacity"] = st.slider("Relative interconnection capacity", value=1.0, max_value=1.5, step=0.05)
    config["interconnections"]["optimize_individual_interconnections"] = st.checkbox("Optimize individual interconnections")
    col1, col2 = st.columns(2)
    config["interconnections"]["efficiency"]["hvac"] = col1.number_input("Efficiency HVAC", value=0.95, max_value=1.0)
    config["interconnections"]["efficiency"]["hvdc"] = col2.number_input("Efficiency HVDC", value=0.95, max_value=1.0)

# Set the sensitivity analysis options
with st.sidebar.expander("Sensitivity analysis"):
    # Enable/disable the sensitivity analysis
    sensitivity_analysis_types = ["-", "curtailment", "climate_years", "technology_scenario", "baseload", "hydropower_capacity", "interconnection_capacity", "interconnection_efficiency", "min_self_sufficiency", "max_self_sufficiency"]
    sensitivity_analysis_type = st.selectbox("Sensitivity type", sensitivity_analysis_types, format_func=utils.format_str, disabled=utils.is_demo, help=demo_disabled_message)

    # Initialize the sensitivity_config if an analysis type has been specified
    if sensitivity_analysis_type == "-":
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
        technology_names = {technology_name: technology_type for technology_type in ["ires", "storage"] for technology_name in config["technologies"][technology_type]}
        selected_technologies = st.multiselect("Technologies", technology_names, format_func=utils.format_technology)
        sensitivity_config["technologies"] = {technology_name: technology_names[technology_name] for technology_name in selected_technologies}
    elif sensitivity_analysis_type == "hydropower_capacity":
        sensitivity_start, sensitivity_stop = st.slider("Hydropower capacity range", value=(0.0, 2.0), min_value=0.0, max_value=2.0, step=0.05)
        number_steps = st.slider("Number of steps", value=10, min_value=3, max_value=50)
        sensitity_steps = np.linspace(start=sensitivity_start, stop=sensitivity_stop, num=number_steps)
        sensitivity_config["steps"] = {f"{step:.3f}": float(step) for step in sensitity_steps}
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
    elif sensitivity_analysis_type == "min_self_sufficiency":
        sensitivity_start, sensitivity_stop = st.slider("Minimum self-sufficiency range", value=(0.0, 1.0), min_value=0.0, max_value=1.0, step=0.05)
        number_steps = st.slider("Number of steps", value=10, min_value=3, max_value=50)
        sensitity_steps = np.linspace(start=sensitivity_start, stop=sensitivity_stop, num=number_steps)
        sensitivity_config["steps"] = {f"{step:.3f}": float(step) for step in sensitity_steps}
    elif sensitivity_analysis_type == "max_self_sufficiency":
        sensitivity_start, sensitivity_stop = st.slider("Maximum self-sufficiency range", value=(1.0, 2.0), min_value=1.0, max_value=2.0, step=0.05)
        number_steps = st.slider("Number of steps", value=10, min_value=3, max_value=50)
        sensitity_steps = np.linspace(start=sensitivity_start, stop=sensitivity_stop, num=number_steps)
        sensitivity_config["steps"] = {f"{step:.3f}": float(step) for step in sensitity_steps}

# Set the optimization parameters
with st.sidebar.expander("Optimization parameters"):
    config["optimization"] = {}

    # Select the optimization method
    method_options = {-1: "Automatic", 0: "Primal simplex", 1: "Dual simplex", 2: "Barrier", 3: "Concurrent", 4: "Deterministic concurrent", 5: "Deterministic concurrent simplex"}
    config["optimization"]["method"] = st.selectbox("Method", method_options.keys(), index=3, format_func=lambda key: method_options[key])

    # Select the barrier convergence tolerance and maximum number of iterations
    if config["optimization"]["method"] == 2:
        config["optimization"]["max_barrier_iterations"] = st.number_input("Maximum iterations", value=2000, min_value=1, max_value=10 ** 6)
        config["optimization"]["barrier_convergence_tolerance"] = st.select_slider("Barrier convergence tolerance", options=[10 ** i for i in range(-6, 1)], value=0.001, disabled=config["optimization"]["method"] != 2)

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
