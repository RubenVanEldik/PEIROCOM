import utils
import validate


@utils.cache
def read_text(filepath):
    """
    Read a text file
    """
    assert validate.is_filepath(filepath, existing=True)

    with open(filepath) as f:
        text = f.read()

    return text
