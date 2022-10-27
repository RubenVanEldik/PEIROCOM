from .get_env import get_env


is_demo = get_env("ENVIRONMENT") == "DEMO"
