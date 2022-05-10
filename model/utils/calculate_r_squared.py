from sklearn.linear_model import LinearRegression
import streamlit as st

import validate


@st.experimental_memo(show_spinner=False)
def calculate_r_squared(col1, col2):
    """
    Calculate the R-squared value for two Series
    """
    assert validate.is_series(col1)
    assert validate.is_series(col2)

    # Initialize the linear regression model
    model = LinearRegression()

    # Set the X and y values
    X = col1.to_frame().dropna()
    y = col2.dropna()

    # Fit the regression model and calculate the R-squared value
    model.fit(X, y)
    r_squared = model.score(X, y)

    # Return the R-squared value
    return r_squared
