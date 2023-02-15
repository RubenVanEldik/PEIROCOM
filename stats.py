import utils
import validate


def firm_lcoe(output_directory, *, country_codes=None, breakdown_level=0):
    """
    Calculate the firm LCOE for a specific run
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)
    assert validate.is_breakdown_level(breakdown_level)

    # Get the capacities and demand
    ires_capacity = utils.get_ires_capacity(output_directory, country_codes=country_codes)
    storage_capacity = utils.get_storage_capacity(output_directory, country_codes=country_codes)
    hydropower_capacity = utils.get_hydropower_capacity(output_directory, country_codes=country_codes)
    temporal_results = utils.get_temporal_results(output_directory, country_codes=country_codes)
    temporal_demand = utils.merge_dataframes_on_column(temporal_results, "demand_total_MW")
    temporal_export = utils.merge_dataframes_on_column(temporal_results, "net_export_MW")
    temporal_net_demand = temporal_demand + temporal_export
    config = utils.read_yaml(output_directory / "config.yaml")

    # Return the LCOE
    return utils.calculate_lcoe(ires_capacity, storage_capacity, hydropower_capacity, temporal_net_demand, config=config, breakdown_level=breakdown_level)


def unconstrained_lcoe(output_directory, *, country_codes=None, breakdown_level=0):
    """
    Calculate the unconstrained_lcoe LCOE for a specific run
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)
    assert validate.is_breakdown_level(breakdown_level)

    # Get the capacities and demand
    ires_capacity = utils.get_ires_capacity(output_directory, country_codes=country_codes)
    storage_capacity = utils.get_storage_capacity(output_directory, country_codes=country_codes)
    hydropower_capacity = utils.get_hydropower_capacity(output_directory, country_codes=country_codes)
    temporal_results = utils.get_temporal_results(output_directory, country_codes=country_codes)
    temporal_demand = utils.merge_dataframes_on_column(temporal_results, "generation_ires_MW") + utils.merge_dataframes_on_column(temporal_results, "generation_total_hydropower_MW")
    config = utils.read_yaml(output_directory / "config.yaml")

    # Set the storage capacity to zero
    for bidding_zone in storage_capacity:
        storage_capacity[bidding_zone] = 0 * storage_capacity[bidding_zone]

    # Return the LCOE
    return utils.calculate_lcoe(ires_capacity, storage_capacity, hydropower_capacity, temporal_demand, config=config, breakdown_level=breakdown_level)


def premium(output_directory, *, country_codes=None, breakdown_level=0):
    """
    Calculate the firm kWh premium
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)
    assert validate.is_breakdown_level(breakdown_level)

    # Get the capacities and demand
    firm_lcoe_result = firm_lcoe(output_directory, country_codes=country_codes, breakdown_level=breakdown_level)
    unconstrained_lcoe_result = unconstrained_lcoe(output_directory, country_codes=country_codes, breakdown_level=0)

    # Return the firm kWh premium
    return firm_lcoe_result / unconstrained_lcoe_result


def relative_curtailment(output_directory, *, country_codes=None):
    """
    Calculate the relative curtailment
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)

    temporal_results = utils.get_temporal_results(output_directory, group="all", country_codes=country_codes)
    return temporal_results.curtailed_MW.sum() / (temporal_results.generation_ires_MW.sum() + temporal_results.generation_total_hydropower_MW.sum())


def ires_capacity(output_directory, *, country_codes=None):
    """
    Get the grouped IRES capacity for a specific output_directory
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)

    return utils.get_ires_capacity(output_directory, group="all", country_codes=country_codes)


def hydropower_capacity(output_directory, *, country_codes=None):
    """
    Get the grouped hydropower capacity for a specific output_directory
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)

    return utils.get_hydropower_capacity(output_directory, group="all", country_codes=country_codes)


def storage_capacity(output_directory, *, country_codes=None):
    """
    Get the grouped storage capacity for a specific output_directory
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)

    return utils.get_storage_capacity(output_directory, group="all", country_codes=country_codes)


def self_sufficiency(output_directory, *, country_codes=None):
    """
    Return the self-sufficiency factor for the selected countries
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)

    temporal_results = utils.get_temporal_results(output_directory, country_codes=country_codes)
    mean_demand = utils.merge_dataframes_on_column(temporal_results, "demand_total_MW").mean(axis=1)
    mean_ires_generation = utils.merge_dataframes_on_column(temporal_results, "generation_ires_MW").mean(axis=1)
    mean_hydropower_generation = utils.merge_dataframes_on_column(temporal_results, "generation_total_hydropower_MW").mean(axis=1)
    mean_curtailment = utils.merge_dataframes_on_column(temporal_results, "curtailed_MW").mean(axis=1)
    mean_storage_flow = utils.merge_dataframes_on_column(temporal_results, "net_storage_flow_total_MW").mean(axis=1)

    return (mean_ires_generation + mean_hydropower_generation - mean_curtailment - mean_storage_flow).mean() / mean_demand.mean()
