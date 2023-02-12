import utils
import validate


@utils.cache
def get_technologies(*, technology_type=None):
    """
    Retrieve the technologies
    """
    assert validate.is_technology_type(technology_type, required=False)

    # Read the technologies YAML file
    technologies = utils.read_yaml(utils.path("input", "technologies.yaml"))

    # Return the requested technologies if a technology type was specfied
    if technology_type == "ires":
        return technologies.get("ires", {})
    if technology_type == "hydropower":
        return technologies.get("hydropower", {})
    if technology_type == "storage":
        return technologies.get("storage", {})

    # Return all technologies when no technology type was specified
    return {**technologies.get("ires", {}), **technologies.get("hydropower", {}), **technologies.get("storage", {})}
