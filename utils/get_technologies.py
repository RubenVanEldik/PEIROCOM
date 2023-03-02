import utils
import validate


@utils.cache
def get_technologies(*, technology_type=None):
    """
    Retrieve the technologies
    """
    assert validate.is_technology_type(technology_type, required=False)

    # Read the technologies YAML file
    technology_types = utils.read_yaml(utils.path("input", "technologies.yaml"))

    # Return the requested technologies if a technology type was specified or all if none was specified
    if technology_type == "ires":
        technologies = technology_types.get("ires", {})
    elif technology_type == "hydropower":
        technologies = technology_types.get("hydropower", {})
    elif technology_type == "storage":
        technologies = technology_types.get("storage", {})
    elif technology_type == "electrolysis":
        technologies = technology_types.get("electrolysis", {})
    else:
        technologies = {**technology_types.get("ires", {}), **technology_types.get("hydropower", {}), **technology_types.get("storage", {}), **technology_types.get("electrolysis", {})}

    del technologies["color"]

    return technologies
