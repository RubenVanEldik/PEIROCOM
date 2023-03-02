import pathlib

import validate


def _validate_path_arguments(args):
    """
    Check if all path arguments are valid
    """
    for index, arg in enumerate(args):
        if index == 0 and validate.is_directory_path(arg):
            continue
        if validate.is_string(arg) and "/" not in arg:
            continue
        if validate.is_number(arg):
            continue
        return False
    return True


def path(*args):
    """
    Create a path object with the given arguments
    """
    assert _validate_path_arguments(args)

    # Create the path object
    new_path = pathlib.Path(".")

    # Loop over all arguments, adding them to the path object
    for arg in args:
        # If it's a number, convert the argument to a string
        if validate.is_number(arg):
            arg = str(arg)

        # Add the argument to teh path
        new_path /= arg

    # Return the path object
    return new_path
