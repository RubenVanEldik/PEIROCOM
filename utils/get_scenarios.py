import utils
import validate


def get_scenarios():
    """
    Get a list with the names of all scenarios
    """

    scenarios_directory = utils.path("input", "scenarios")

    # Return an empty list if there is no output directory
    if not scenarios_directory.is_dir():
        return []

    # Get a list of all directories in input/scenarios
    files_and_directories = scenarios_directory.iterdir()
    directories = [directory.name for directory in files_and_directories if directory.is_dir()]

    # Return a sorted list of all model scenarios
    return sorted(directories)
