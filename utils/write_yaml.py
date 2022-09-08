import yaml

import validate


def write_yaml(filepath, data, *, exist_ok=False, sort_keys=False):
    """
    Store a dictionary or list as .yaml file
    """
    assert validate.is_filepath(filepath, suffix=".yaml", existing=None if exist_ok else False)
    assert validate.is_dict_or_list(data)
    assert validate.is_bool(exist_ok)

    # Read and parse the file
    with open(filepath, "w") as f:
        return yaml.dump(data, f, Dumper=yaml.Dumper, sort_keys=sort_keys)
