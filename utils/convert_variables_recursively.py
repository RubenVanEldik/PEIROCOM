import gurobipy as gp
import pandas as pd


def convert_variables_recursively(data):
    """
    Store a dictionary or list as .yaml file
    """
    if type(data) is dict or type(data) is gp.tupledict:
        for key, value in data.items():
            data[key] = convert_variables_recursively(value)
        return data
    if type(data) is list:
        return [convert_variables_recursively(value) for value in data]
    if type(data) is pd.core.frame.DataFrame:
        return data.applymap(convert_variables_recursively)
    if type(data) is pd.core.series.Series:
        return data.apply(convert_variables_recursively)
    if type(data) is gp.Var:
        return data.X
    if type(data) in [gp.LinExpr, gp.QuadExpr]:
        return data.getValue()
    return data
