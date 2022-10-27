import yaml

import utils
import validate


@utils.cache
def read_yaml(filepath):
    """
    Returns the content of a .yaml file as python list or dictionary
    """
    assert validate.is_filepath(filepath, suffix=".yaml", existing=True)

    # Read and parse the file
    with open(filepath) as f:
        return yaml.load(f, Loader=yaml.SafeLoader)
