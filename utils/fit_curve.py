import numpy as np
import pandas as pd
import scipy

import validate


def fit_curve(independent_variables, dependent_variables, *, function, return_parameters=False, num_points=200):
    """
    Fit a curve for a given series and function
    """
    assert validate.is_series(independent_variables)
    assert validate.is_series(dependent_variables)
    assert validate.is_func(function)
    assert validate.is_bool(return_parameters)
    assert validate.is_integer(num_points, min_value=2)

    # Fit the model with the given function
    parameters, covariance = scipy.optimize.curve_fit(function, independent_variables, dependent_variables, maxfev=10 ** 4)

    # Generate the curve
    curve_index = np.linspace(independent_variables.min(), independent_variables.max(), num_points)
    curve = pd.Series(curve_index, index=curve_index).apply(function, args=list(parameters))

    # Return the parameters, if explicitly specified
    if return_parameters:
        return curve, parameters

    return curve
