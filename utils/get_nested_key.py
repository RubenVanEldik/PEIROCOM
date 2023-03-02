import validate


def get_nested_key(dictionary, key_string):
    """
    Return the value of a nested key, specified as a dot separated string
    """
    assert validate.is_dict(dictionary)
    assert validate.is_string(key_string)

    # Start off pointing at the original dictionary that was passed in
    here = dictionary
    keys = key_string.split(".")

    # For each key in key_string set here to its value
    for key in keys:
        if here.get(key) is None:
            raise ValueError(f"Can not find '{key}' in '{key_string}'")
        here = here[key]

    # Return the final nested value
    return here
