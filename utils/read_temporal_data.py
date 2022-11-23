import datetime
import pytz

import utils
import validate


def read_temporal_data(filepath, *, start_year=None, end_year=None, header=0):
    """
    Returns the temporal data, if specified only for a specific date range
    """
    assert validate.is_filepath(filepath, suffix=".csv", existing=True)
    assert validate.is_integer(start_year, min_value=1982, max_value=2016, required=False)
    assert validate.is_integer(end_year, min_value=1982, max_value=2016, required=False)
    assert validate.is_integer(header, min_value=0) or validate.is_list_like(header)

    temporal_data = utils.read_csv(filepath, parse_dates=True, index_col=0, header=header)

    # Set the time to the beginning and end of the start and end date respectively
    tzinfo = pytz.timezone("UTC")
    start = datetime.datetime(start_year, 1, 1, 0, 0, 0, tzinfo=tzinfo) if start_year else None
    end = datetime.datetime(end_year, 12, 31, 0, 0, 0, tzinfo=tzinfo) if end_year else None

    # Return the temporal data
    return temporal_data[start:end]
