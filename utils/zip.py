import shutil

import validate


def zip(path):
    """
    Create a ZIP file for a given file
    """
    assert validate.is_filepath(path, existing=True) or validate.is_directory_path(path, existing=True)

    shutil.make_archive(str(path), "zip", str(path))
