import streamlit as st

from .is_demo import is_demo


# Set a maximum cache time of 1 minute for the demo
ttl = 60 if is_demo else 10

# Remove the spinner and set the TTL of the Streamlit memo cache
cache = st.experimental_memo(show_spinner=False, ttl=ttl)
