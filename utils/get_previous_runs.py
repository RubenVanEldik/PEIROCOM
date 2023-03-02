import utils
import validate


def _validate_run(run_name):
    """
    Check if the run has been completed
    """
    assert validate.is_string(run_name)

    # Return True if it has a config.yaml file
    if utils.path("output", run_name, "config.yaml").is_file():
        return True

    # Return True if it has a sensitivity.yaml file
    if utils.path("output", run_name, "sensitivity.yaml").is_file():
        return True

    # Return False if it has neither a config.yaml nor sensitivity.yaml file
    return False


def get_previous_runs(*, include_uncompleted_runs=False):
    """
    Get a list with the names of all previous runs
    """
    assert validate.is_bool(include_uncompleted_runs)

    output_directory = utils.path("output")

    # Return an empty list if there is no output directory
    if not output_directory.is_dir():
        return []

    files_and_directories = output_directory.iterdir()
    directories = [directory.name for directory in files_and_directories if directory.is_dir()]
    directories = sorted(directories, reverse=True)

    # Return a list of all runs
    if include_uncompleted_runs:
        return directories

    # Return a list of all completed runs
    return [directory for directory in directories if _validate_run(directory)]
