from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures

import validate


def calculate_regression_line(col1, col2, *, degree):
    """
    Calculate the X and Y values for a polynomial regression line
    """
    assert validate.is_series(col1)
    assert validate.is_series(col2)
    assert validate.is_integer(degree)

    # Set the X and y values
    X = col1.to_frame()
    y = col2

    # Transform the X values to fit a polynomial
    model_poly = PolynomialFeatures(degree=degree)
    X_poly = model_poly.fit_transform(X)

    # Initialize and fit the linear regression model
    model_linear = LinearRegression()
    model_linear.fit(X_poly, y)

    # Return the x-values and y-values of the regression line
    x_values, y_values = map(list, zip(*sorted(zip(col1, model_linear.predict(X_poly)))))
    return x_values, y_values
