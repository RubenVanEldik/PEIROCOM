import dotenv
import os

import validate


# Load the variables from the .env file
dotenv.load_dotenv(".env")


def get_env(env_name):
    """
    Get the value for a specific environment variable
    """
    assert validate.is_string(env_name)

    # Get the environment variable
    env_value = os.getenv(env_name)

    # Return the environment variable
    return env_value
