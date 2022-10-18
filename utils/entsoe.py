from entsoe import EntsoePandasClient
import streamlit as st

from .getenv import getenv


class Entsoe:
    """
    A copy of the EntsoePandasClient but with cached methods
    """

    def __init__(self):
        # Raise an error if the API key has not been set
        api_key = getenv("ENTSOE_KEY")
        if not api_key:
            raise KeyError("ENTSOE_KEY variable has not been set")

        # Initialize the client
        client = EntsoePandasClient(api_key=api_key)

        # Loop over all methods
        methods = [method for method in dir(client) if callable(getattr(client, method))]
        for method in methods:
            # Don't include private methods
            if method.startswith("_"):
                continue

            # Add the method with the cache decorator
            setattr(self, method, st.experimental_memo(getattr(client, method), show_spinner=False))


entsoe = Entsoe()
