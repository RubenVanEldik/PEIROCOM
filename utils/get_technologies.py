import utils
import validate


@utils.cache
def get_technologies(*, technology_type=None):
    """
    Retrieve the generation technologies
    """
    assert validate.is_technology_type(technology_type, required=False)

    # Read the technologies YAML file
    technologies = utils.read_yaml(utils.path("input", "technologies.yaml"))

    # Return the requested technologies if a technology type was specfied
    if technology_type == "generation":
        return technologies["generation"]
    if technology_type == "storage":
        return technologies["storage"]

    # Return all technologies when no technology type was specified
    return {**technologies["generation"], **technologies["storage"]}
