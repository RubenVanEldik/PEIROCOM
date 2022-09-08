import utils
import validate


def sort_technology_names(unsorted_technology_names):
    """
    Sort a list with technology names
    """
    assert validate.is_technology_list(unsorted_technology_names)

    # Get the production and storage technology names
    production_technology_names = utils.read_yaml(utils.path("input", "technologies", "production.yaml")).keys()
    storage_technology_names = utils.read_yaml(utils.path("input", "technologies", "storage.yaml")).keys()
    all_technology_names = [*production_technology_names, *storage_technology_names]

    # Create a new list with the sorted production technologies
    sorted_technology_names = []
    for technology_name in all_technology_names:
        if technology_name in unsorted_technology_names:
            sorted_technology_names.append(technology_name)

    # Return the sorted list
    return sorted_technology_names
