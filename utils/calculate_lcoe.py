import pandas as pd

import utils
import validate


def _calculate_scenario_costs(assumptions, variable, technology_scenario):
    """
    Calculate the costs for a given technology scenario
    """
    assert validate.is_dict(assumptions)
    assert validate.is_string(variable)
    assert validate.is_number(technology_scenario, min_value=-1, max_value=1)

    if technology_scenario == -1:
        return assumptions["conservative"][variable]
    elif technology_scenario == 0:
        return assumptions["moderate"][variable]
    elif technology_scenario == 1:
        return assumptions["advanced"][variable]
    elif technology_scenario > 0:
        return (1 - technology_scenario) * assumptions["moderate"][variable] + technology_scenario * assumptions["advanced"][variable]
    elif technology_scenario < 0:
        return (1 + technology_scenario) * assumptions["moderate"][variable] - technology_scenario * assumptions["conservative"][variable]


def _calculate_annualized_ires_costs(ires_technologies, ires_capacity_MW, *, technology_scenario):
    """
    Calculate the annualized IRES costs
    """
    assert validate.is_list_like(ires_technologies)
    assert validate.is_dataframe(ires_capacity_MW, column_validator=validate.is_technology)
    assert validate.is_number(technology_scenario, min_value=-1, max_value=1)

    # Read the IRES assumptions
    ires_assumptions = utils.get_technologies(technology_type="ires")

    # Calculate the total annual costs
    annualized_costs_ires = pd.Series([], dtype="float64")
    for technology in ires_technologies:
        capacity_kW = ires_capacity_MW[technology].sum() * 1000
        capex = capacity_kW * _calculate_scenario_costs(ires_assumptions[technology], "capex", technology_scenario)
        fixed_om = capacity_kW * _calculate_scenario_costs(ires_assumptions[technology], "fixed_om", technology_scenario)
        crf = utils.calculate_crf(ires_assumptions[technology]["wacc"], ires_assumptions[technology]["economic_lifetime"])
        annualized_costs_ires[technology] = crf * capex + fixed_om

    return annualized_costs_ires


def _calculate_annualized_dispatchable_costs(dispatchable_technologies, dispatchable_capacity_MW, dispatchable_mean_generation_MW, *, technology_scenario):
    """
    Calculate the annualized dispatchable costs
    """
    assert validate.is_list_like(dispatchable_technologies)
    assert validate.is_series(dispatchable_capacity_MW)
    assert validate.is_series(dispatchable_mean_generation_MW)
    assert validate.is_number(technology_scenario, min_value=-1, max_value=1)

    # Read the dispatchable assumptions
    dispatchable_assumptions = utils.get_technologies(technology_type="dispatchable")

    # Calculate the total annual costs
    annualized_costs_dispatchable = pd.Series([], dtype="float64")
    for technology in dispatchable_technologies:
        capacity_kW = dispatchable_capacity_MW[technology] * 1000
        annual_generation_MWh = dispatchable_mean_generation_MW.sum() * 8760
        capex = capacity_kW * _calculate_scenario_costs(dispatchable_assumptions[technology], "capex", technology_scenario)
        fixed_om = capacity_kW * _calculate_scenario_costs(dispatchable_assumptions[technology], "fixed_om", technology_scenario)
        variable_om = annual_generation_MWh * _calculate_scenario_costs(dispatchable_assumptions[technology], "variable_om", technology_scenario)
        fuel_costs = annual_generation_MWh / dispatchable_assumptions[technology]["efficiency"] * dispatchable_assumptions[technology]["fuel_costs"]
        crf = utils.calculate_crf(dispatchable_assumptions[technology]["wacc"], dispatchable_assumptions[technology]["economic_lifetime"])
        annualized_costs_dispatchable[technology] = crf * capex + fixed_om + variable_om + fuel_costs

    return annualized_costs_dispatchable


def _calculate_annualized_hydropower_costs(hydropower_technologies, hydropower_capacity, *, technology_scenario):
    """
    Calculate the annualized hydropower costs
    """
    assert validate.is_list_like(hydropower_technologies)
    assert validate.is_dataframe(hydropower_capacity)
    assert validate.is_number(technology_scenario, min_value=-1, max_value=1)

    # Read the hydropower assumptions
    hydropower_assumptions = utils.get_technologies(technology_type="hydropower")

    # Calculate the total annual hydropower costs
    annualized_costs_hydropower = pd.Series([], dtype="float64")
    for technology in hydropower_technologies:
        # Calculate costs for the turbine capacity
        turbine_capacity_kW = hydropower_capacity.loc[technology, "turbine"] * 1000
        capex = turbine_capacity_kW * _calculate_scenario_costs(hydropower_assumptions[technology], "capex", technology_scenario)
        fixed_om = turbine_capacity_kW * _calculate_scenario_costs(hydropower_assumptions[technology], "fixed_om", technology_scenario)

        # Calculate the total annualized costs
        crf = utils.calculate_crf(hydropower_assumptions[technology]["wacc"], hydropower_assumptions[technology]["economic_lifetime"])
        annualized_costs_hydropower[technology] = crf * capex + fixed_om

    return annualized_costs_hydropower


def _calculate_annualized_storage_costs(storage_technologies, storage_capacity_MWh, *, technology_scenario):
    """
    Calculate the annualized storage costs
    """
    assert validate.is_list_like(storage_technologies)
    assert validate.is_dataframe(storage_capacity_MWh)
    assert validate.is_number(technology_scenario, min_value=-1, max_value=1)

    # Read the storage assumptions
    storage_assumptions = utils.get_technologies(technology_type="storage")

    # Calculate the total annual storage costs
    annualized_costs_storage = pd.Series([], dtype="float64")
    for technology in storage_technologies:
        capacity_energy_kWh = storage_capacity_MWh.loc[technology, "energy"] * 1000
        capacity_power_kW = storage_capacity_MWh.loc[technology, "power"] * 1000

        # Calculate CAPEX
        capex_energy = capacity_energy_kWh * _calculate_scenario_costs(storage_assumptions[technology], "capex_energy", technology_scenario)
        capex_power = capacity_power_kW * _calculate_scenario_costs(storage_assumptions[technology], "capex_power", technology_scenario)
        capex = capex_energy + capex_power

        # Calculate fixed O&M
        fixed_om_energy = capacity_energy_kWh * _calculate_scenario_costs(storage_assumptions[technology], "fixed_om_energy", technology_scenario)
        fixed_om_power = capacity_power_kW * _calculate_scenario_costs(storage_assumptions[technology], "fixed_om_power", technology_scenario)
        fixed_om = fixed_om_energy + fixed_om_power

        # Calculate the total annualized costs
        crf = utils.calculate_crf(storage_assumptions[technology]["wacc"], storage_assumptions[technology]["economic_lifetime"])
        annualized_costs_storage[technology] = crf * capex + fixed_om

    return annualized_costs_storage


def calculate_lcoe(ires_capacity, dispatchable_capacity, mean_dispatchable_generation, storage_capacity, hydropower_capacity, mean_electricity_demand, *, config, breakdown_level=0):
    """
    Calculate the average levelized costs of electricity for all market nodes
    """
    assert validate.is_market_node_dict(ires_capacity)
    assert validate.is_dataframe(dispatchable_capacity)
    assert validate.is_dataframe(mean_dispatchable_generation)
    assert validate.is_market_node_dict(storage_capacity)
    assert validate.is_market_node_dict(hydropower_capacity)
    assert validate.is_number(mean_electricity_demand)
    assert validate.is_config(config)
    assert validate.is_breakdown_level(breakdown_level)

    # Get the technology scenario
    technology_scenario = config["technologies"]["scenario"]

    annualized_ires_costs = 0
    annualized_dispatchable_costs = 0
    annualized_storage_costs = 0
    annualized_hydropower_costs = 0

    for market_node in ires_capacity.keys():
        # Add the annualized costs
        annualized_ires_costs += _calculate_annualized_ires_costs(config["technologies"]["ires"], ires_capacity[market_node], technology_scenario=technology_scenario)
        annualized_dispatchable_costs += _calculate_annualized_dispatchable_costs(config["technologies"]["dispatchable"], dispatchable_capacity.loc[market_node], mean_dispatchable_generation.loc[market_node], technology_scenario=technology_scenario)
        annualized_hydropower_costs += _calculate_annualized_hydropower_costs(config["technologies"]["hydropower"], hydropower_capacity[market_node], technology_scenario=technology_scenario)
        annualized_storage_costs += _calculate_annualized_storage_costs(config["technologies"]["storage"], storage_capacity[market_node], technology_scenario=technology_scenario)

    # Calculate and return the LCOE
    if breakdown_level == 0:
        total_costs = annualized_ires_costs.sum() + annualized_dispatchable_costs.sum() + annualized_storage_costs.sum() + annualized_hydropower_costs.sum()
    elif breakdown_level == 1:
        total_costs = pd.Series({"ires": annualized_ires_costs.sum(), "dispatchable": annualized_dispatchable_costs.sum(), "hydropower": annualized_hydropower_costs.sum(), "storage": annualized_storage_costs.sum()})
    elif breakdown_level == 2:
        total_costs = pd.concat([annualized_ires_costs, annualized_dispatchable_costs, annualized_storage_costs, annualized_hydropower_costs])
    else:
        raise ValueError("breakdown_level should be between 0, 1, or 2")

    # Convert the costs from Dollar to Euro
    eur_usd = 1.1290  # Source: https://www.federalreserve.gov/releases/h10/20220110/
    total_costs /= eur_usd

    # Return the relative or absolute costs
    annual_electricity_demand = 8760 * mean_electricity_demand
    return total_costs / annual_electricity_demand
