import shutil

import validate


def unzip(filepath, *, remove_zip_file=False):
    """
    Unzip a file for a given filepath and delete the ZIP file
    """
    assert validate.is_filepath(filepath, suffix=".zip", existing=True)
    assert validate.is_bool(remove_zip_file)

    # Unpack the ZIP file
    shutil.unpack_archive(str(filepath), filepath.parent / filepath.stem)

    # Remove the ZIP file if specified
    if remove_zip_file == True:
        filepath.unlink()
