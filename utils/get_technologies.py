import utils
import validate


def get_technologies(*, technology_type=None):
    """
    Retrieve the production technologies
    """
    assert validate.is_technology_type(technology_type, required=False)

    # Read the technologies YAML file
    technologies = utils.read_yaml(utils.path("input", "technologies.yaml"))

    # Return the requested technologies if a technology type was specfied
    if technology_type == "production":
        return technologies["production"]
    if technology_type == "storage":
        return technologies["storage"]

    # Return all technologies when no technology type was specified
    return {**technologies["production"], **technologies["storage"]}
