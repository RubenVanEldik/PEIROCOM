import utils
import validate


@utils.cache
def get_technology(technology):
    """
    Retrieve a specific technology
    """
    assert validate.is_technology(technology)

    return utils.get_technologies()[technology]
