import datetime
import pathlib
import re

import gurobipy as gp
import numpy as np
import pandas as pd
import shapely

import chart


def is_market_node(value, *, required=True):
    if value is None:
        return not required

    return bool(re.search("^[A-Z]{2}[0-9a-zA-Z]{2}$", value))


def is_market_node_list(value, *, required=True):
    if value is None:
        return not required

    if not isinstance(value, list):
        return False

    return all(is_market_node(x) for x in value)


def is_bool(value, *, required=True):
    if value is None:
        return not required

    return isinstance(value, bool)


def is_market_node_dict(value, *, required=True):
    if value is None:
        return not required

    if not isinstance(value, (dict, gp.tupledict)):
        return False

    return all(is_market_node(x) for x in value.keys())


def is_breakdown_level(value, *, required=True):
    if value is None:
        return not required

    return is_integer(value, min_value=0, max_value=2)


def is_chart(value, *, required=True):
    if value is None:
        return not required

    return isinstance(value, chart.Chart)


def is_color(value, *, required=True):
    if value is None:
        return not required

    return bool(re.search("^#([A-F0-9]{6}|[A-F0-9]{8})$", value))


def is_color_format(value, *, required=True):
    if value is None:
        return not required

    return value in ["hex", "rgb", "rgba"]


def is_color_name(value, *, required=True):
    if value is None:
        return not required

    # Don't use utils.read_csv because it might create a circular import
    colors = ["slate", "gray", "zinc", "neutral", "stone", "red", "orange", "amber", "yellow", "lime", "green", "emerald", "teal", "cyan", "sky", "blue", "indigo", "violet", "purple", "fuchsia", "pink", "rose"]
    return value in colors


def is_color_value(value, *, required=True):
    if value is None:
        return not required

    return value in [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]


def is_config(value, *, required=True):
    if value is None:
        return not required

    if not isinstance(value, dict):
        return False

    if not is_string(value.get("name")):
        return False
    if not is_scenario(value.get("scenario")):
        return False
    if not is_country_code_list(value.get("country_codes"), code_type="nuts2"):
        return False
    if len(value.get("country_codes")) == 0:
        return False
    if not is_dict(value.get("climate_years")):
        return False
    if not is_integer(value["climate_years"].get("start")):
        return False
    if not is_integer(value["climate_years"].get("end")):
        return False
    if value["climate_years"]["start"] > value["climate_years"]["end"]:
        return False
    if not is_resolution(value.get("resolution")):
        return False
    if len(value.get("technologies").get("ires")) == 0:
        return False
    if len(value.get("technologies").get("storage")) == 0:
        return False
    if not value.get("optimization"):
        return False
    if not is_integer(value["optimization"].get("method"), min_value=-1, max_value=6):
        return False
    if not is_integer(value["optimization"].get("thread_count"), min_value=1):
        return False
    return True


def is_country_code(value, *, required=True, code_type):
    if value is None:
        return not required

    if code_type == "nuts2":
        return bool(re.search("^[A-Z]{2}$", value))
    if code_type == "alpha3":
        return bool(re.search("^[A-Z]{3}$", value))
    return False


def is_country_code_list(value, *, required=True, code_type):
    if value is None:
        return not required

    if not is_list_like(value):
        return False

    return all(is_country_code(code, code_type=code_type) for code in value)


def is_country_code_type(value, *, required=True):
    if value is None:
        return not required

    return value == "nuts2" or value == "alpha3"


def is_country_obj(value, *, required=True):
    if value is None:
        return not required

    if not isinstance(value, dict):
        return False

    return bool(value["name"] and value["market_nodes"])


def is_country_obj_list(value, *, required=True):
    if value is None:
        return not required

    if not is_list_like(value) or len(value) == 0:
        return False

    return all(is_country_obj(x) for x in value)


def is_dataframe(value, *, required=True, column_validator=None):
    if value is None:
        return not required

    if not isinstance(value, pd.DataFrame):
        return False

    if column_validator:
        return all(column_validator(column_name) for column_name in value.columns)

    return True


def is_dataframe_dict(value, *, required=True):
    if value is None:
        return not required

    if not isinstance(value, dict):
        return False

    return all(is_dataframe(value[x]) for x in value)


def is_date(value, *, required=True):
    if value is None:
        return not required

    return isinstance(value, datetime.date)


def is_datetime(value, *, required=True):
    if value is None:
        return not required

    return isinstance(value, datetime.datetime)


def is_datetime_index(value, *, required=True):
    if value is None:
        return not required

    return isinstance(value, pd.core.indexes.datetimes.DatetimeIndex)


def is_dict(value, *, required=True):
    if value is None:
        return not required

    return isinstance(value, dict)


def is_dict_or_list(value, *, required=True):
    if value is None:
        return not required

    return isinstance(value, (list, dict))


def is_directory_path(value, *, required=True, existing=None):
    if value is None:
        return not required

    if not isinstance(value, pathlib.Path):
        return False
    if existing is False:
        return not value.exists()
    if existing is True:
        return value.is_dir()

    return True


def is_aggregation_level(value, *, required=True):
    if value is None:
        return not required

    return value in ["all", "country"]


def is_filepath(value, *, required=True, suffix=None, existing=None):
    if value is None:
        return not required

    if not isinstance(value, pathlib.Path):
        return False
    if suffix and value.suffix != suffix:
        return False
    if existing is False:
        return not value.exists()
    if existing is True:
        return value.is_file()

    return True


def is_filepath_list(value, *, required=True, suffix=None):
    if value is None:
        return not required

    if not is_list_like(value):
        return False

    return all(is_filepath(filepath, suffix=suffix) for filepath in value)


def is_float(value, *, required=True, min_value=None, max_value=None):
    if value is None:
        return not required

    if not isinstance(value, (float, np.float64)):
        return False

    if min_value is not None and value < min_value:
        return False

    if max_value is not None and value > max_value:
        return False

    return True


def is_func(value, *, required=True):
    if value is None:
        return not required

    return callable(value)


def is_gurobi_variable(value, *, required=True):
    if value is None:
        return not required

    return isinstance(value, (gp.Var, gp.LinExpr, gp.QuadExpr))


def is_gurobi_variable_tupledict(value, *, required=True):
    if value is None:
        return not required

    if not isinstance(value, gp.tupledict):
        return False

    return all(is_gurobi_variable(x) for x in value.values())


def is_interconnection_tuple(value, *, required=True):
    if value is None:
        return not required

    if not isinstance(value, tuple) or len(value) != 2:
        return False

    return is_market_node(value[0]) and (is_market_node(value[1]) or bool(re.search("^(gross|net)_(ex|im)port_limit$", value[1])))


def is_interconnection_type(value, *, required=True):
    if value is None:
        return not required

    return value in ["hvac", "hvdc", "limits"]


def is_interconnection_direction(value, *, required=True):
    if value is None:
        return not required

    return value in ["import", "export"]


def is_integer(value, *, required=True, min_value=None, max_value=None):
    if value is None:
        return not required

    if not isinstance(value, (int, np.int64)):
        return False

    if min_value is not None and value < min_value:
        return False

    if max_value is not None and value > max_value:
        return False

    return True


def is_list_like(value, *, required=True):
    if value is None:
        return not required

    return pd.api.types.is_list_like(value)


def is_model(value, *, required=True):
    if value is None:
        return not required

    return isinstance(value, gp.Model)


def is_number(value, *, required=True, min_value=None, max_value=None):
    if value is None:
        return not required

    return is_float(value, min_value=min_value, max_value=max_value) or is_integer(value, min_value=min_value, max_value=max_value)


def is_point(value, *, required=True):
    if value is None:
        return not required

    return isinstance(value, shapely.geometry.point.Point)


def is_resolution(value, *, required=True):
    if value is None:
        return not required

    if not is_string(value):
        return False

    try:
        pd.tseries.frequencies.to_offset(value)
        return True
    except ValueError:
        return False


def is_scenario(value, *, required=True):
    if value is None:
        return not required

    return value in [directory.name for directory in pathlib.Path("./input/scenarios").iterdir() if directory.is_dir()]


def is_sensitivity_config(value, *, required=True):
    if value is None:
        return not required

    if not isinstance(value, dict):
        return False

    return value["analysis_type"] in ["curtailment", "climate_years", "technology_scenario", "hydrogen_demand", "extra_hydrogen_costs", "dispatchable_generation", "hydropower_capacity", "interconnection_capacity", "interconnection_efficiency", "min_self_sufficiency", "max_self_sufficiency", "barrier_convergence_tolerance"]


def is_series(value, *, required=True):
    if value is None:
        return not required

    return isinstance(value, pd.core.series.Series)


def is_string(value, *, required=True, min_length=0):
    if value is None:
        return not required

    if not isinstance(value, str):
        return False

    return len(value) >= min_length


def is_technology(value, *, required=True):
    if value is None:
        return not required

    if value in ["pv", "onshore", "offshore"]:
        return True
    if value in ["nuclear", "h2_ccgt", "h2_gas_turbine"]:
        return True
    if value in ["run_of_river", "reservoir", "pumped_storage_open", "pumped_storage_closed"]:
        return True
    if value in ["lion"]:
        return True
    if value in ["pem"]:
        return True

    return False


def is_technology_list(value, *, required=True):
    if value is None:
        return not required

    if not is_list_like(value) or len(value) == 0:
        return False

    return all(is_technology(x) for x in value)


def is_technology_scenario(value, *, required=True):
    if value is None:
        return not required

    return value in ["conservative", "moderate", "advanced"]


def is_technology_type(value, *, required=True):
    if value is None:
        return not required

    return value in ["ires", "dispatchable", "hydropower", "storage", "electrolysis"]


def is_url(value, *, required=True):
    if value is None:
        return not required

    url_regex = r'^(ftp|https?):\/\/[^ "]+\.\w{2,}'
    return bool(re.search(url_regex, value))
