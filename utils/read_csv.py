import pandas as pd

import utils
import validate


@utils.cache
def read_csv(filepath, **kwargs):
    """
    Read, cache, and return a CSV file
    """
    assert validate.is_filepath(filepath, suffix=".csv", existing=True)

    return pd.read_csv(filepath, **kwargs)
