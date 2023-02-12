import utils
import validate


def sort_technology_names(unsorted_technology_names):
    """
    Sort a list with technology names
    """
    assert validate.is_technology_list(unsorted_technology_names)

    # Create a new list with the sorted technologies
    sorted_technology_names = []
    for technology_name in utils.get_technologies().keys():
        if technology_name in unsorted_technology_names:
            sorted_technology_names.append(technology_name)

    # Return the sorted list
    return sorted_technology_names
