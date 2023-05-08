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


def _calculate_annualized_electrolyzer_costs(electrolysis_technologies, electrolyzer_capacity_MW, *, technology_scenario):
    """
    Calculate the annualized electrolyzer costs
    """
    assert validate.is_list_like(electrolysis_technologies)
    assert validate.is_series(electrolyzer_capacity_MW)
    assert validate.is_number(technology_scenario, min_value=-1, max_value=1)

    # Read the electrolysis assumptions
    electrolysis_assumptions = utils.get_technologies(technology_type="electrolysis")

    # Calculate the total annual costs
    annualized_costs_electrolyzer = pd.Series([], dtype="float64")
    for technology in electrolysis_technologies:
        capacity_kW = electrolyzer_capacity_MW[technology] * 1000
        capex = capacity_kW * _calculate_scenario_costs(electrolysis_assumptions[technology], "capex", technology_scenario)
        fixed_opex = capacity_kW * _calculate_scenario_costs(electrolysis_assumptions[technology], "fixed_opex", technology_scenario)
        crf = utils.calculate_crf(electrolysis_assumptions[technology]["wacc"], electrolysis_assumptions[technology]["economic_lifetime"])
        annualized_costs_electrolyzer[technology] = crf * capex + fixed_opex

    return annualized_costs_electrolyzer


def calculate_lcoh(electrolysis_capacity, mean_electricity_demand, electricity_costs, *, config, breakdown_level=0, annual_costs=False):
    """
    Calculate the average Levelized Costs of Hydrogen for all market nodes
    """
    assert validate.is_dataframe(electrolysis_capacity)
    assert validate.is_series(mean_electricity_demand)
    assert validate.is_number(electricity_costs, required=not annual_costs)
    assert validate.is_config(config)
    assert validate.is_breakdown_level(breakdown_level)
    assert validate.is_bool(annual_costs)

    # Get the technology scenario
    technology_scenario = config["technologies"]["scenario"]

    # Get the relevant electrolysis assumptions
    electrolysis_assumptions = utils.get_technologies(technology_type="electrolysis")
    relevant_electrolysis_assumptions = {electrolysis_technology: electrolysis_assumptions[electrolysis_technology] for electrolysis_technology in electrolysis_assumptions if electrolysis_technology in config["technologies"]["electrolysis"]}


    # Calculate the annualized electrolyzer costs
    annualized_electrolyzer_costs = 0
    for market_node in electrolysis_capacity.index:
        annualized_electrolyzer_costs += _calculate_annualized_electrolyzer_costs(config["technologies"]["electrolysis"], electrolysis_capacity.loc[market_node], technology_scenario=technology_scenario)

    # Calculate the annual electricity costs and hydrogen production
    annual_electricity_demand = 8760 * mean_electricity_demand

    # Calculate the annual hydrogen production
    annual_hydrogen_production = 0
    for electrolysis_technology in relevant_electrolysis_assumptions:
        annual_hydrogen_production += annual_electricity_demand[electrolysis_technology] * relevant_electrolysis_assumptions[electrolysis_technology]["efficiency"]

    # Calculate the annualized electricity costs
    if electricity_costs is not None:
        annualized_electricity_costs = annual_electricity_demand.sum() * electricity_costs
    else:
        annualized_electricity_costs = pd.Series(0, index=relevant_electrolysis_assumptions.keys())

    # Calculate and return the LCOH
    if breakdown_level == 0:
        total_costs = annualized_electrolyzer_costs.sum() + annualized_electricity_costs.sum()
    elif breakdown_level == 1:
        total_costs = pd.Series({"electrolyzer": annualized_electrolyzer_costs.sum(), "electricity": annualized_electricity_costs.sum()})
    elif breakdown_level == 2:
        total_costs = pd.concat([annualized_electrolyzer_costs.rename("electrolyzer"), annualized_electricity_costs.rename("electricity")], axis=1)
    else:
        raise ValueError("breakdown_level should be between 0, 1, or 2")

    # Convert the costs from Dollar to Euro
    eur_usd = 1.1290  # Source: https://www.federalreserve.gov/releases/h10/20220110/
    total_costs /= eur_usd

    # Calculate the extra hydrogen costs
    hydrogen_mwh_kg = 0.033333
    total_costs += annual_hydrogen_production * config.get("extra_hydrogen_costs_per_kg", 0) / hydrogen_mwh_kg

    # Return the relative or absolute costs
    if annual_costs:
        return total_costs
    return total_costs / annual_hydrogen_production
