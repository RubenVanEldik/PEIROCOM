import streamlit as st

import utils

# Show Utrecht University logo
st.image("./images/logo.png")

# Show the README introduction
st.markdown(utils.read_text(utils.path("README.md")))


st.markdown(
    """
<style>
    .element-container button + div {
        justify-content: center;
        margin-bottom: 1rem;
    }

    .element-container img {
        width: 22rem;

    }
	.stMarkdown{
		text-align: center;
	}

    .stMarkdown h3 {
        font-size: 1.5rem;
    }

    .stMarkdown p {
        width: 90%;
        margin-left: auto;
        margin-right: auto;
        font-size: 1.1rem;
    }
</style>
""",
    unsafe_allow_html=True,
)
