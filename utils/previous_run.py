import pandas as pd

from .cache import cache # Can't use utils as utils is only partially intiialized and will thus throw an AttributeError
import utils
import validate

@cache
def firm_lcoe(output_directory, *, country_codes=None, breakdown_level=0):
    """
    Calculate the firm LCOE for a specific run
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)
    assert validate.is_breakdown_level(breakdown_level)

    # Get the capacities and demand
    config = utils.read_yaml(output_directory / "config.yaml")
    ires_capacity = utils.get_ires_capacity(output_directory, country_codes=country_codes)
    dispatchable_capacity = utils.get_dispatchable_capacity(output_directory, country_codes=country_codes)
    storage_capacity = utils.get_storage_capacity(output_directory, country_codes=country_codes)
    hydropower_capacity = utils.get_hydropower_capacity(output_directory, country_codes=country_codes)
    electrolysis_capacity = utils.get_electrolysis_capacity(output_directory, country_codes=country_codes)
    mean_temporal_results = utils.get_mean_temporal_results(output_directory, country_codes=country_codes)
    mean_temporal_results["demand_total_MW"] = mean_temporal_results.demand_total_MW + mean_temporal_results.net_export_MW
    mean_electrolysis_demand = pd.Series({electrolysis_technology: mean_temporal_results[f"demand_{electrolysis_technology}_MW"].sum() for electrolysis_technology in electrolysis_capacity.columns})

    # Calculate the real electricity costs recursively (this is required because the LCOE and LCOH are dependent upon each other)
    previous_electricity_costs = 0
    while True:
        # Calculate the hydrogen and electricity costs
        hydrogen_costs = utils.calculate_lcoh(electrolysis_capacity, mean_electrolysis_demand, electricity_costs=previous_electricity_costs, config=config, breakdown_level=0).mean()
        electricity_costs = utils.calculate_lcoe(ires_capacity, dispatchable_capacity, storage_capacity, hydropower_capacity, mean_temporal_data=mean_temporal_results, hydrogen_costs=hydrogen_costs, config=config, breakdown_level=0)

        # Return the electricity costs (with the selected breakdown level) if the improvement is less than 1E-12
        if abs(previous_electricity_costs / electricity_costs - 1) < 10 ** -12:
            return utils.calculate_lcoe(ires_capacity, dispatchable_capacity, storage_capacity, hydropower_capacity, mean_temporal_data=mean_temporal_results, hydrogen_costs=hydrogen_costs, config=config, breakdown_level=breakdown_level)

        # Update the previous electricity costs
        previous_electricity_costs = electricity_costs


@cache
def unconstrained_lcoe(output_directory, *, country_codes=None, breakdown_level=0):
    """
    Calculate the unconstrained_lcoe LCOE for a specific run
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)
    assert validate.is_breakdown_level(breakdown_level)

    # Get the capacities and demand
    config = utils.read_yaml(output_directory / "config.yaml")
    ires_capacity = utils.get_ires_capacity(output_directory, country_codes=country_codes)
    mean_temporal_results = utils.get_mean_temporal_results(output_directory, country_codes=country_codes)
    mean_temporal_results["demand_total_MW"] = mean_temporal_results.generation_ires_MW

    return utils.calculate_lcoe(ires_capacity, None, None, None, mean_temporal_data=mean_temporal_results, hydrogen_costs=0, config=config, breakdown_level=breakdown_level)


@cache
def annual_costs(output_directory, *, country_codes=None, breakdown_level=0):
    """
    Calculate the annual costs for a specific run
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)
    assert validate.is_breakdown_level(breakdown_level)

    # Calculate the annual electricity costs
    config = utils.read_yaml(output_directory / "config.yaml")
    ires_capacity = utils.get_ires_capacity(output_directory, country_codes=country_codes)
    dispatchable_capacity = utils.get_dispatchable_capacity(output_directory, country_codes=country_codes)
    storage_capacity = utils.get_storage_capacity(output_directory, country_codes=country_codes)
    hydropower_capacity = utils.get_hydropower_capacity(output_directory, country_codes=country_codes)
    mean_temporal_results = utils.get_mean_temporal_results(output_directory, country_codes=country_codes)
    hydrogen_costs = lcoh(output_directory, country_codes=country_codes)
    annual_costs = utils.calculate_lcoe(ires_capacity, dispatchable_capacity, storage_capacity, hydropower_capacity, hydrogen_costs=hydrogen_costs, mean_temporal_data=mean_temporal_results, config=config, breakdown_level=breakdown_level, annual_costs=True)

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


@cache
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


@cache
def relative_curtailment(output_directory, *, country_codes=None):
    """
    Calculate the relative curtailment
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)

    mean_temporal_results = utils.get_mean_temporal_results(output_directory, group="all", country_codes=country_codes)
    return mean_temporal_results.curtailed_MW / (mean_temporal_results.generation_ires_MW + mean_temporal_results.generation_dispatchable_MW + mean_temporal_results.generation_total_hydropower_MW)


@cache
def lcoh(output_directory, *, country_codes=None, breakdown_level=0, electrolysis_technology=None):
    """
    Calculate the LCOH for a specific run
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)
    assert validate.is_breakdown_level(breakdown_level)
    assert validate.is_technology(electrolysis_technology, required=False)

    # Get the capacities and electrolysis demand and electricity costs
    config = utils.read_yaml(output_directory / "config.yaml")
    electrolysis_capacity = utils.get_electrolysis_capacity(output_directory, country_codes=country_codes)
    mean_temporal_results = utils.get_mean_temporal_results(output_directory, group="all", country_codes=country_codes)
    electricity_costs = firm_lcoe(output_directory, country_codes=country_codes, breakdown_level=breakdown_level)

    # Filter the electrolysis capacity is a specific technology was given
    if electrolysis_technology is not None:
        electrolysis_capacity = electrolysis_capacity[[electrolysis_technology]]

    # Create a Series with the mean electrolysis demand per technology
    mean_electrolysis_demand = pd.Series({electrolysis_technology: mean_temporal_results[f"demand_{electrolysis_technology}_MW"].sum() for electrolysis_technology in electrolysis_capacity.columns})

    # Return the LCOE
    return utils.calculate_lcoh(electrolysis_capacity, mean_electrolysis_demand, electricity_costs, config=config, breakdown_level=breakdown_level)


@cache
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


@cache
def ires_capacity(output_directory, *, country_codes=None):
    """
    Get the grouped IRES capacity for a specific output_directory
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)

    return utils.get_ires_capacity(output_directory, group="all", country_codes=country_codes)


@cache
def dispatchable_capacity(output_directory, *, country_codes=None):
    """
    Get the grouped dispatchable capacity for a specific output_directory
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)

    return utils.get_dispatchable_capacity(output_directory, group="all", country_codes=country_codes)


@cache
def hydropower_capacity(output_directory, *, country_codes=None):
    """
    Get the grouped hydropower capacity for a specific output_directory
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)

    return utils.get_hydropower_capacity(output_directory, group="all", country_codes=country_codes)


@cache
def storage_capacity(output_directory, *, country_codes=None):
    """
    Get the grouped storage capacity for a specific output_directory
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)

    return utils.get_storage_capacity(output_directory, group="all", country_codes=country_codes)


@cache
def self_sufficiency(output_directory, *, country_codes=None):
    """
    Return the self-sufficiency factor for the selected countries
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_country_code_list(country_codes, code_type="nuts2", required=False)

    mean_temporal_results = utils.get_mean_temporal_results(output_directory, group="all", country_codes=country_codes)
    mean_demand = mean_temporal_results.demand_total_MW
    mean_ires_generation = mean_temporal_results.generation_ires_MW
    mean_dispatchable_generation = mean_temporal_results.generation_dispatchable_MW
    mean_hydropower_generation = mean_temporal_results.generation_total_hydropower_MW
    mean_curtailment = mean_temporal_results.curtailed_MW
    mean_storage_flow = mean_temporal_results.net_storage_flow_total_MW

    return (mean_ires_generation + mean_dispatchable_generation + mean_hydropower_generation - mean_curtailment - mean_storage_flow) / mean_demand
