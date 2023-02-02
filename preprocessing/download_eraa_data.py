import streamlit as st
import openpyxl

import utils
import validate


def download_eraa_data(url, filepath, excel_filenames):
    """
    Download the ZIP file and convert the formulas in the Excel workbooks to values
    """
    assert validate.is_url(url)
    assert validate.is_filepath(filepath) or validate.is_directory_path(filepath)
    assert validate.is_filepath_list(excel_filenames)

    # Download file
    utils.download_file(url, filepath, unzip=True, show_progress=True)

    # Convert the Excel formulas to values
    with st.spinner("Converting the Excel formulas to values"):
        for filename in excel_filenames:
            openpyxl.load_workbook(filename, data_only=True).save(filename)

    # Rerun everything from the top
    st.experimental_rerun()
