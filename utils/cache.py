import streamlit as st

# Remove the spinner and set the TTL of the Streamlit memo cache
cache = st.cache_data(show_spinner=False, ttl=120)
