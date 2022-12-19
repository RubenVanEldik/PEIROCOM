import datetime
import gurobipy
import numpy as np
import pandas as pd
import pathlib
import re
import shapely

import chart


def is_bidding_zone(value, *, required=True):
    if value is None:
        return not required

    return bool(re.search("^[A-Z]{2}[0-9a-zA-Z]{2}$", value))


def is_bidding_zone_list(value, *, required=True):
    if value is None:
        return not required

    if type(value) is not list:
        return False

    return all(is_bidding_zone(x) for x in value)


def is_bool(value, *, required=True):
    if value is None:
        return not required

    return type(value) is bool


def is_bidding_zone_dict(value, *, required=True):
    if value is None:
        return not required

    if not type(value) is dict and not isinstance(value, gurobipy.tupledict):
        return False

    return all(is_bidding_zone(x) for x in value.keys())


def is_breakdown_level(value, *, required=True):
    if value is None:
        return not required

    return is_integer(value, min_value=0, max_value=2)


def is_chart(value, *, required=True):
    if value is None:
        return not required

    return isinstance(value, chart.Chart)


def is_climate_zone(value, *, required=True):
    if value is None:
        return not required

    return bool(re.search("^[a-z]+_[0-9A-Z]{2,3}_cf$", value))


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

    if type(value) is not dict:
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
    if not is_integer(value["climate_years"].get("start"), min_value=1982, max_value=2016):
        return False
    if not is_integer(value["climate_years"].get("end"), min_value=1982, max_value=2016):
        return False
    if value["climate_years"]["start"] > value["climate_years"]["end"]:
        return False
    if len(value.get("technologies").get("production")) == 0:
        return False
    if len(value.get("technologies").get("storage")) == 0:
        return False
    if not is_dict(value.get("time_discretization")):
        return False
    if not is_resolution_stages(value["time_discretization"].get("resolution_stages")):
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

    if not type(value) is dict:
        return False

    return bool(value["name"] and value["bidding_zones"])


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

    if not type(value) is dict:
        return False

    return all(is_dataframe(value[x]) for x in value)


def is_date(value, *, required=True):
    if value is None:
        return not required

    return type(value) is datetime.date


def is_datetime(value, *, required=True):
    if value is None:
        return not required

    return type(value) is datetime.datetime


def is_datetime_index(value, *, required=True):
    if value is None:
        return not required

    return type(value) is pd.core.indexes.datetimes.DatetimeIndex


def is_dict(value, *, required=True):
    if value is None:
        return not required

    return type(value) is dict


def is_dict_or_list(value, *, required=True):
    if value is None:
        return not required

    is_list = type(value) is list
    is_dict = type(value) is dict
    return is_list or is_dict


def is_directory_path(value, *, required=True, existing=None):
    if value is None:
        return not required

    if not isinstance(value, pathlib.Path):
        return False
    if existing == False:
        return not value.exists()
    if existing == True:
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
    if existing == False:
        return not value.exists()
    if existing == True:
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

    if not type(value) is float and not isinstance(value, np.float64):
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


def is_interconnection_tuple(value, *, required=True):
    if value is None:
        return not required

    if type(value) is not tuple or len(value) != 2:
        return False

    return is_bidding_zone(value[0]) and (is_bidding_zone(value[1]) or bool(re.search("^(gross|net)_(ex|im)port_limit$", value[1])))


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

    if not type(value) is int:
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

    return isinstance(value, gurobipy.Model)


def is_number(value, *, required=True, min_value=None, max_value=None):
    if value is None:
        return not required

    return is_float(value, min_value=min_value, max_value=max_value) or is_integer(value, min_value=min_value, max_value=max_value)


def is_point(value, *, required=True):
    if value is None:
        return not required

    return type(value) is shapely.geometry.point.Point


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


def is_resolution_stages(value, *, required=True):
    if value is None:
        return not required

    if type(value) is not list or len(value) == 0:
        return False

    return all(is_resolution(resolution) for resolution in value)


def is_scenario(value, *, required=True):
    if value is None:
        return not required

    return value in [directory.name for directory in pathlib.Path("./input/scenarios").iterdir() if directory.is_dir()]


def is_sensitivity_config(value, *, required=True):
    if value is None:
        return not required

    if not type(value) is dict:
        return False

    return value["analysis_type"] in ["curtailment", "climate_years", "technology_scenario", "baseload", "interconnection_capacity", "interconnection_efficiency", "self_sufficiency", "value_propagation"]


def is_series(value, *, required=True):
    if value is None:
        return not required

    return type(value) is pd.core.series.Series


def is_string(value, *, required=True, min_length=0):
    if value is None:
        return not required

    if not type(value) is str:
        return False

    return len(value) >= min_length


def is_technology(value, *, required=True):
    if value is None:
        return not required

    production_technologies = ["pv", "onshore", "offshore"]
    storage_technologies = ["lion", "hydrogen"]
    return value in production_technologies or value in storage_technologies


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

    return value in ["production", "storage"]


def is_url(value, *, required=True):
    if value is None:
        return not required

    url_regex = '^(ftp|https?):\/\/[^ "]+\.\w{2,}'
    return bool(re.search(url_regex, value))


def is_variable(value, *, required=True):
    if value is None:
        return not required

    return isinstance(value, gurobipy.Var)


def is_variable_tupledict(value, *, required=True):
    if value is None:
        return not required

    if not isinstance(value, gurobipy.tupledict):
        return False

    return all(is_variable(x) for x in value.values())
