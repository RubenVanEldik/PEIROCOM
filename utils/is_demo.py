from .get_env import get_env

if type(get_env("IS_DEMO")) is str:
    is_demo = get_env("IS_DEMO").lower() == "true"
else:
    is_demo = False
