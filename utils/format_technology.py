import utils
import validate


def format_technology(key, *, capitalize=True):
    """
    Format the name of a specific technology
    """
    assert validate.is_technology(key) or validate.is_technology_type(key)
    assert validate.is_bool(capitalize)

    if validate.is_technology_type(key):
        technology_name = key
    else:
        # Get a dictionary with all technologies
        technologies = utils.get_technologies()

        # Get the technology name
        technology_name = technologies[key]["name"]

    # Return a formatted technology name
    return (technology_name[0].upper() + technology_name[1:]) if capitalize else technology_name
