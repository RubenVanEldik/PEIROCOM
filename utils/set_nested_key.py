import validate


def set_nested_key(dictionary, key_string, value):
    """
    Set the value of a nested key, specified as a dot separated string
    """
    assert validate.is_dict(dictionary)
    assert validate.is_string(key_string)

    # Start off pointing at the original dictionary that was passed in
    here = dictionary
    keys = key_string.split(".")

    # For each key in key_string set here to its value
    for key in keys[:-1]:
        if here.get(key) is None:
            here[key] = {}
        here = here[key]

    # Set the final key to the given value
    here[keys[-1]] = value
