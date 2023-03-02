import validate


def validate_files(filenames):
    """
    Check if all files in a list exist
    """
    assert validate.is_filepath_list(filenames)

    return all(filename.is_file() for filename in filenames)
