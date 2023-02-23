import streamlit as st

import analysis
import utils

# Set the page config
st.set_page_config(page_title="Analysis - PEIROCOM", page_icon="📈")


def run():
    # Get the previous runs
    previous_runs = utils.get_previous_runs()

    # Show a warning and return the function if there are no completed runs
    if not previous_runs:
        st.sidebar.warning("There are no previous runs to analyze")
        return

    # Select the run to analyze
    selected_run = st.sidebar.selectbox("Previous runs", previous_runs)
    output_directory = utils.path("output", selected_run)
    is_sensitivity_analysis = (output_directory / "sensitivity.yaml").is_file()

    # Unzip all ZIP files in the output directory
    zipped_files = list(output_directory.glob("**/*.zip"))
    if len(zipped_files) > 0:
        unzip_button = st.sidebar.empty()
        if unzip_button.button("Unzip files"):
            progress_bar = st.sidebar.progress(0.0)
            for index, zip_filename in enumerate(zipped_files):
                utils.unzip(zip_filename, remove_zip_file=True)
                progress_bar.progress((index + 1) / len(zipped_files))
            progress_bar.empty()
            unzip_button.empty()
        else:
            return

    # Get the config
    if is_sensitivity_analysis:
        # Get the config for the first step
        sensitivity_config = utils.read_yaml(output_directory / "sensitivity.yaml")
        first_step = next(iter(sensitivity_config["steps"]))
        config = utils.read_yaml(output_directory / first_step / "config.yaml")
    else:
        config = utils.read_yaml(output_directory / "config.yaml")

    # Set the analysis type options
    analysis_type_options = ["statistics", "temporal_results", "countries", "correlation", "duration_curve", "interconnection_capacity"]
    if is_sensitivity_analysis:
        # Add a Streamlit placeholder for if the sensitivity step should be specified
        sensitivity_step_placeholder = st.sidebar.empty()

        # Ask which analysis type should be used
        analysis_type_options.extend(["sensitivity", "optimization_log"])
        analysis_type = st.sidebar.radio("Type of analysis", analysis_type_options, index=len(analysis_type_options) - 2, format_func=utils.format_str)

        # If its not a sensitivity analysis, ask for which sensitivity step the data should be shown
        if analysis_type != "sensitivity":
            output_directory /= sensitivity_step_placeholder.selectbox("Step", sensitivity_config["steps"])

        # Run the analysis
        getattr(analysis, analysis_type)(output_directory)
    else:
        analysis_type_options.append("optimization_log")
        # Ask which analysis type should be used
        analysis_type = st.sidebar.radio("Type of analysis", analysis_type_options, format_func=utils.format_str)

        # Run the analysis
        getattr(analysis, analysis_type)(output_directory)


run()
