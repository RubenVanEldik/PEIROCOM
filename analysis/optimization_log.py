import streamlit as st

import utils
import validate


def optimization_log(output_directory):
    """
    Show the optimization log
    """
    assert validate.is_directory_path(output_directory)

    st.title("📜 Optimization log")

    # Read the log
    log = utils.read_text(output_directory / "log.txt")

    # Display the log as a code block
    st.code(log)
