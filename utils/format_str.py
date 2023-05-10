import utils
import validate

word_dict = {"ires": "IRES", "lcoe": "LCOE", "hvac": "HVAC", "hvdc": "HVDC", "soc": "SoC", "wacc": "WACC", "capex": "CAPEX", "om": "O&M"}


@utils.cache
def format_str(string):
    """
    Replace underscores with spaces, capitalize the string, and convert the abbreviations into uppercase
    """
    assert validate.is_string(string)

    # Replace underscores with spaces
    string = string.replace("_", " ")

    # Re-add the underscores for the multi-word technologies
    string = string.replace("h2 ccgt", "h2_ccgt")
    string = string.replace("h2 gas turbine", "h2_gas_turbine")

    # Format technology names and abbreviations properly, and capitalize the first word of the string
    word_list = []
    for index, word in enumerate(string.split(" ")):
        if validate.is_technology(word):
            word_list.append(utils.format_technology(word, capitalize=index == 0))
        elif word in word_dict:
            word_list.append(word_dict[word])
        elif index == 0:
            word_list.append(word.capitalize())
        else:
            word_list.append(word)

    return " ".join(word_list)
