import datetime
import pytz
import pandas as pd

import utils
import validate


def read_temporal_data(filepath, *, start_year=None, end_year=None, timezone=None, header=0):
    """
    Returns the temporal data, if specified only for a specific date range
    """
    assert validate.is_filepath(filepath, suffix=".csv", existing=True)
    assert validate.is_integer(start_year, min_value=1982, max_value=2016, required=False)
    assert validate.is_integer(end_year, min_value=1982, max_value=2016, required=False)
    assert validate.is_string(timezone, required=False)
    assert validate.is_integer(header, min_value=0) or validate.is_list_like(header)

    temporal_data = utils.read_csv(filepath, parse_dates=True, index_col=0, header=header)

    # Set the index to a UTC DatetimeIndex if its not yet a DatetimeIndex
    if type(temporal_data.index) != pd.core.indexes.datetimes.DatetimeIndex:
        print(f"The {filepath} index does not contain a timestamp")
        temporal_data = temporal_data.set_index(pd.to_datetime(temporal_data.index, utc=True))

    # Set or convert the timezone if specified
    if timezone is not None:
        if temporal_data.index.tz is None:
            temporal_data.index = temporal_data.index.tz_localize(timezone)
        elif timezone != temporal_data.index.tz:
            temporal_data.index = temporal_data.index.tz_convert(timezone)
    elif temporal_data.index.tz is None:
        # Throw an error if the CSV file has no timezone and no timezone was specified
        raise TypeError("The data has not timezone and no timezone was specified")

    # Set the time to the beginning and end of the start and end date respectively
    start = datetime.datetime(start_year, 1, 1, 0, 0, tzinfo=temporal_data.index.tz) if start_year else None
    end = datetime.datetime(end_year, 12, 31, 23, 59, tzinfo=temporal_data.index.tz) if end_year else None

    # Return the temporal data
    return temporal_data[start:end]
