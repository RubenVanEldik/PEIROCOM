import pandas as pd

import validate


def merge_dataframes_on_column(dfs, column, *, is_sorted=False):
    """
    Create one DataFrame from a dictionary of DataFrames by selecting only one column per DataFrame
    """
    assert validate.is_dataframe_dict(dfs)
    assert validate.is_string(column)
    assert validate.is_bool(is_sorted)

    # Initialize a new DataFrame
    df = pd.DataFrame()

    # Add each (sorted) column to the new DataFrame
    for key in dfs:
        if is_sorted:
            col = dfs[key].sort_values(column, ascending=False)[column]
            df[key] = col.tolist()
        else:
            df[key] = dfs[key][column]

    return df
