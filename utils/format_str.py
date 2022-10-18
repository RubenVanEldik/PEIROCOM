import streamlit as st

import utils
import validate


@st.experimental_memo(show_spinner=False)
def format_str(str):
    """
    Replace underscores with spaces, capitalize the string, and convert the abbreviations into uppercase
    """
    assert validate.is_string(str)

    # Replace underscores with spaces
    str = str.replace("_", " ")

    # Format technology names and bbreviations properly, and capitalize the first word of the string
    word_list = []
    for index, word in enumerate(str.split(" ")):
        if validate.is_technology(word):
            word_list.append(utils.format_technology(word, capitalize=index == 0))
        elif word in ["lcoe", "hvac", "hvdc"]:
            word_list.append(word.upper())
        elif index == 0:
            word_list.append(word.capitalize())
        else:
            word_list.append(word)

    return " ".join(word_list)
