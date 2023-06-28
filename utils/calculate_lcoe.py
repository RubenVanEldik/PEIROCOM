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
        fixed_opex = capacity_kW * _calculate_scenario_costs(ires_assumptions[technology], "fixed_opex", technology_scenario)
        crf = utils.calculate_crf(ires_assumptions[technology]["wacc"], ires_assumptions[technology]["economic_lifetime"])
        annualized_costs_ires[technology] = crf * capex + fixed_opex

    return annualized_costs_ires


def _calculate_annualized_dispatchable_costs(dispatchable_technologies, dispatchable_capacity_MW, mean_temporal_data, *, hydrogen_costs, technology_scenario):
    """
    Calculate the annualized dispatchable costs
    """
    assert validate.is_list_like(dispatchable_technologies)
    assert validate.is_series(dispatchable_capacity_MW)
    assert validate.is_series(mean_temporal_data)
    assert validate.is_number(technology_scenario, min_value=-1, max_value=1)
    assert validate.is_number(hydrogen_costs)

    # Read the dispatchable assumptions
    dispatchable_assumptions = utils.get_technologies(technology_type="dispatchable")

    # Calculate the total annual costs
    annualized_costs_dispatchable = pd.Series([], dtype="float64")
    for technology in dispatchable_technologies:
        capacity_kW = dispatchable_capacity_MW[technology] * 1000
        annual_generation_MWh = mean_temporal_data[f"generation_{technology}_MW"] * 8760
        capex = capacity_kW * _calculate_scenario_costs(dispatchable_assumptions[technology], "capex", technology_scenario)
        fixed_opex = capacity_kW * _calculate_scenario_costs(dispatchable_assumptions[technology], "fixed_opex", technology_scenario)
        variable_opex = annual_generation_MWh * _calculate_scenario_costs(dispatchable_assumptions[technology], "variable_opex", technology_scenario)
        relative_fuel_costs = hydrogen_costs if dispatchable_assumptions[technology]["fuel_costs"] == "hydrogen" else dispatchable_assumptions[technology]["fuel_costs"]
        fuel_costs = annual_generation_MWh / dispatchable_assumptions[technology]["efficiency"] * relative_fuel_costs
        crf = utils.calculate_crf(dispatchable_assumptions[technology]["wacc"], dispatchable_assumptions[technology]["economic_lifetime"])
        annualized_costs_dispatchable[technology] = crf * capex + fixed_opex + variable_opex + fuel_costs

    return annualized_costs_dispatchable


def _calculate_annualized_hydropower_costs(hydropower_technologies, hydropower_capacity, mean_temporal_data, *, technology_scenario):
    """
    Calculate the annualized hydropower costs
    """
    assert validate.is_list_like(hydropower_technologies)
    assert validate.is_dataframe(hydropower_capacity)
    assert validate.is_series(mean_temporal_data)
    assert validate.is_number(technology_scenario, min_value=-1, max_value=1)

    # Read the hydropower assumptions
    hydropower_assumptions = utils.get_technologies(technology_type="hydropower")

    # Calculate the total annual hydropower costs
    annualized_costs_hydropower = pd.Series([], dtype="float64")
    for technology in hydropower_technologies:
        # Calculate costs for the turbine capacity
        turbine_capacity_kW = hydropower_capacity.loc[technology, "turbine"] * 1000
        capex = turbine_capacity_kW * _calculate_scenario_costs(hydropower_assumptions[technology], "capex", technology_scenario)
        fixed_opex = turbine_capacity_kW * _calculate_scenario_costs(hydropower_assumptions[technology], "fixed_opex", technology_scenario)
        annual_generation_MWh = mean_temporal_data[f"generation_{technology}_hydropower_MW"] * 8760
        variable_opex = annual_generation_MWh * _calculate_scenario_costs(hydropower_assumptions[technology], "variable_opex", technology_scenario)

        # Calculate the total annualized costs
        crf = utils.calculate_crf(hydropower_assumptions[technology]["wacc"], hydropower_assumptions[technology]["economic_lifetime"])
        annualized_costs_hydropower[technology] = crf * capex + fixed_opex + variable_opex

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
        fixed_opex_energy = capacity_energy_kWh * _calculate_scenario_costs(storage_assumptions[technology], "fixed_opex_energy", technology_scenario)
        fixed_opex_power = capacity_power_kW * _calculate_scenario_costs(storage_assumptions[technology], "fixed_opex_power", technology_scenario)
        fixed_opex = fixed_opex_energy + fixed_opex_power

        # Calculate the total annualized costs
        crf = utils.calculate_crf(storage_assumptions[technology]["wacc"], storage_assumptions[technology]["economic_lifetime"])
        annualized_costs_storage[technology] = crf * capex + fixed_opex

    return annualized_costs_storage


def calculate_lcoe(ires_capacity, dispatchable_capacity, storage_capacity, hydropower_capacity, *, hydrogen_costs, mean_temporal_data, config, breakdown_level=0, annual_costs=False):
    """
    Calculate the average levelized costs of electricity for all market nodes
    """
    assert validate.is_market_node_dict(ires_capacity, required=False)
    assert validate.is_dataframe(dispatchable_capacity, required=False)
    assert validate.is_market_node_dict(storage_capacity, required=False)
    assert validate.is_market_node_dict(hydropower_capacity, required=False)
    assert validate.is_number(hydrogen_costs)
    assert validate.is_dataframe(mean_temporal_data)
    assert validate.is_config(config)
    assert validate.is_breakdown_level(breakdown_level)
    assert validate.is_bool(annual_costs)

    # Get the technology scenario
    technology_scenario = config["technologies"]["scenario"]

    annualized_ires_costs = pd.Series(0, index=config["technologies"]["ires"])
    annualized_dispatchable_costs = pd.Series(0, index=config["technologies"]["dispatchable"])
    annualized_storage_costs = pd.Series(0, index=config["technologies"]["storage"])
    annualized_hydropower_costs = pd.Series(0, index=config["technologies"]["hydropower"])

    for market_node in ires_capacity.keys():
        # Add the annualized costs
        if ires_capacity is not None:
            annualized_ires_costs += _calculate_annualized_ires_costs(config["technologies"]["ires"], ires_capacity[market_node], technology_scenario=technology_scenario)
        if dispatchable_capacity is not None:
            annualized_dispatchable_costs += _calculate_annualized_dispatchable_costs(config["technologies"]["dispatchable"], dispatchable_capacity.loc[market_node], mean_temporal_data.loc[market_node], hydrogen_costs=hydrogen_costs, technology_scenario=technology_scenario)
        if hydropower_capacity is not None:
            annualized_hydropower_costs += _calculate_annualized_hydropower_costs(config["technologies"]["hydropower"], hydropower_capacity[market_node], mean_temporal_data.loc[market_node], technology_scenario=technology_scenario)
        if storage_capacity is not None:
            annualized_storage_costs += _calculate_annualized_storage_costs(config["technologies"]["storage"], storage_capacity[market_node], technology_scenario=technology_scenario)

    # Calculate the annual value of lost load
    if "voll" in config:
        annualized_voll = mean_temporal_data["lost_load_MW"] * 8760 * config["voll"]
    else:
        annualized_voll = mean_temporal_data["lost_load_MW"] * 0

    # Calculate and return the LCOE
    if breakdown_level == 0:
        total_costs = annualized_ires_costs.sum() + annualized_dispatchable_costs.sum() + annualized_storage_costs.sum() + annualized_hydropower_costs.sum() + annualized_voll.sum()
    elif breakdown_level == 1:
        total_costs = pd.Series({"ires": annualized_ires_costs.sum(), "dispatchable": annualized_dispatchable_costs.sum(), "hydropower": annualized_hydropower_costs.sum(), "storage": annualized_storage_costs.sum(), "voll": annualized_voll.sum()})
    elif breakdown_level == 2:
        all_costs = [annualized_ires_costs, annualized_dispatchable_costs, annualized_storage_costs, annualized_hydropower_costs, [annualized_voll.sum()]]
        total_costs = pd.concat([item for item in all_costs if isinstance(item, pd.Series)])
    else:
        raise ValueError("breakdown_level should be between 0, 1, or 2")

    # Convert the costs from Dollar to Euro
    eur_usd = 1.1290  # Source: https://www.federalreserve.gov/releases/h10/20220110/
    total_costs /= eur_usd

    # Return the relative or absolute costs
    annual_electricity_demand = 1 if annual_costs else 8760 * mean_temporal_data.demand_total_MW.sum()
    return total_costs / annual_electricity_demand
