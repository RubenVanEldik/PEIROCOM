import pandas as pd

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
    mean_temporal_results = utils.get_mean_temporal_results(output_directory, group="all", country_codes=country_codes)
    mean_electricity_demand = (mean_temporal_results.demand_total_MW + mean_temporal_results.net_export_MW)
    config = utils.read_yaml(output_directory / "config.yaml")

    # Return the LCOE
    return utils.calculate_lcoe(ires_capacity, storage_capacity, hydropower_capacity, mean_electricity_demand, config=config, breakdown_level=breakdown_level)


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
    mean_temporal_results = utils.get_mean_temporal_results(output_directory, group="all", country_codes=country_codes)
    mean_demand = (mean_temporal_results.generation_ires_MW + mean_temporal_results.generation_total_hydropower_MW)
    config = utils.read_yaml(output_directory / "config.yaml")

    # Set the storage capacity to zero
    for market_node in storage_capacity:
        storage_capacity[market_node] = 0 * storage_capacity[market_node]

    # Return the LCOE
    return utils.calculate_lcoe(ires_capacity, storage_capacity, hydropower_capacity, mean_demand, config=config, breakdown_level=breakdown_level)


def annual_costs(output_directory, *, country_codes=None, breakdown_level=0):
    """
    Calculate the annual costs for a specific run
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)
    assert validate.is_breakdown_level(breakdown_level)

    # Calculate the annual electricity costs
    ires_capacity = utils.get_ires_capacity(output_directory, country_codes=country_codes)
    storage_capacity = utils.get_storage_capacity(output_directory, country_codes=country_codes)
    hydropower_capacity = utils.get_hydropower_capacity(output_directory, country_codes=country_codes)
    config = utils.read_yaml(output_directory / "config.yaml")
    annual_costs = utils.calculate_lcoe(ires_capacity, storage_capacity, hydropower_capacity, 1 / 8760, config=config, breakdown_level=breakdown_level)

    # Calculate the annual electrolyzer costs
    electrolysis_capacity = utils.get_electrolysis_capacity(output_directory, country_codes=country_codes)
    annual_electrolyzer_costs = utils.calculate_lcoh(electrolysis_capacity, None, None, config=config, breakdown_level=breakdown_level, annual_costs=True)

    # Add the electrolyzer to the other costs
    if breakdown_level == 0:
        annual_costs += annual_electrolyzer_costs
    if breakdown_level == 1:
        annual_costs['electrolysis'] = annual_electrolyzer_costs.electrolyzer
    if breakdown_level == 2:
        annual_costs = annual_costs.append(annual_electrolyzer_costs.electrolyzer)

    # Return the annual costs
    return annual_costs


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

    mean_temporal_results = utils.get_mean_temporal_results(output_directory, group="all", country_codes=country_codes)
    return mean_temporal_results.curtailed_MW / (mean_temporal_results.generation_ires_MW + mean_temporal_results.generation_total_hydropower_MW)


def lcoh(output_directory, *, country_codes=None, breakdown_level=0, electrolysis_technology):
    """
    Calculate the LCOH for a specific run
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)
    assert validate.is_breakdown_level(breakdown_level)
    assert validate.is_technology(electrolysis_technology)

    # Get the capacities and electrolysis demand and electricity costs
    config = utils.read_yaml(output_directory / "config.yaml")
    electrolysis_capacity = utils.get_electrolysis_capacity(output_directory, country_codes=country_codes)[[electrolysis_technology]]
    mean_temporal_results = utils.get_mean_temporal_results(output_directory, group="all", country_codes=country_codes)
    annual_electrolysis_demand = pd.Series({electrolysis_technology: mean_temporal_results[f"demand_{electrolysis_technology}_MW"]})
    electricity_costs = firm_lcoe(output_directory, country_codes=country_codes, breakdown_level=breakdown_level)

    # Return the LCOE
    return utils.calculate_lcoh(electrolysis_capacity, annual_electrolysis_demand, electricity_costs, config=config, breakdown_level=breakdown_level)


def electrolyzer_capacity_factor(output_directory, *, country_codes=None, breakdown_level=0, electrolysis_technology):
    """
    Calculate the electrolyzer capacity factor for a specific run
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)
    assert validate.is_breakdown_level(breakdown_level)
    assert validate.is_technology(electrolysis_technology)

    # Get the capacities and electrolysis demand
    electrolysis_capacity = utils.get_electrolysis_capacity(output_directory, group="all", country_codes=country_codes)[electrolysis_technology]
    mean_temporal_results = utils.get_mean_temporal_results(output_directory, group="all", country_codes=country_codes)
    mean_electrolysis_demand = mean_temporal_results[f"demand_{electrolysis_technology}_MW"]

    return mean_electrolysis_demand / electrolysis_capacity


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

    mean_temporal_results = utils.get_mean_temporal_results(output_directory, group="all", country_codes=country_codes)
    mean_demand = mean_temporal_results.demand_total_MW
    mean_ires_generation = mean_temporal_results.generation_ires_MW
    mean_hydropower_generation = mean_temporal_results.generation_total_hydropower_MW
    mean_curtailment = mean_temporal_results.curtailed_MW
    mean_storage_flow = mean_temporal_results.net_storage_flow_total_MW

    return (mean_ires_generation + mean_hydropower_generation - mean_curtailment - mean_storage_flow) / mean_demand
