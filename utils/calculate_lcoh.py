import re

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
        fixed_om = capacity_kW * _calculate_scenario_costs(electrolysis_assumptions[technology], "fixed_om", technology_scenario)
        crf = utils.calculate_crf(electrolysis_assumptions[technology]["wacc"], electrolysis_assumptions[technology]["economic_lifetime"])
        annualized_costs_electrolyzer[technology] = crf * capex + fixed_om

    return annualized_costs_electrolyzer


def _calculate_annual_electricity_demand(demand_MW, electricity_costs):
    """
    Calculate the annual electricity demand
    """
    assert validate.is_dataframe(demand_MW)
    assert validate.is_number(electricity_costs) or validate.is_gurobi_variable(electricity_costs)

    demand_start_date = demand_MW.index.min()
    demand_end_date = demand_MW.index.max()
    share_of_year_modelled = (demand_end_date - demand_start_date) / pd.Timedelta(365, "days")
    timestep_hours = (demand_MW.index[1] - demand_MW.index[0]).total_seconds() / 3600
    annual_demand = demand_MW.sum() * timestep_hours / share_of_year_modelled
    return annual_demand.rename(index={row: re.match("demand_(.+)_MW", row)[1] for row in annual_demand.index})


def calculate_lcoh(electrolysis_capacity, electricity_demand, electricity_costs, *, config, breakdown_level=0, annual_costs=False):
    """
    Calculate the average Levelized Costs of Hydrogen for all market nodes
    """
    assert validate.is_dataframe(electrolysis_capacity)
    assert validate.is_market_node_dict(electricity_demand, required=not annual_costs)
    assert validate.is_number(electricity_costs, required=electricity_demand is not None)
    assert validate.is_config(config)
    assert validate.is_breakdown_level(breakdown_level)
    assert validate.is_bool(annual_costs)

    # Get the technology scenario
    technology_scenario = config["technologies"]["scenario"]

    # Get the electrolysis assumptions
    electrolysis_assumptions = utils.get_technologies(technology_type="electrolysis")

    annualized_electrolyzer_costs = 0
    annualized_electricity_costs = 0
    annual_hydrogen_production = 0
    for market_node in electrolysis_capacity.index:
        # Calculate the annualized electrolyzer costs
        annualized_electrolyzer_costs += _calculate_annualized_electrolyzer_costs(config["technologies"]["electrolysis"], electrolysis_capacity.loc[market_node], technology_scenario=technology_scenario)

        # Calculate the annual electricity demand and electricity costs for electrolysis
        if electricity_demand is not None:
            annual_electricity_demand_market_node = _calculate_annual_electricity_demand(electricity_demand[market_node], electricity_costs)

            # Calculate the annual hydrogen production
            for electrolysis_technology in electrolysis_assumptions:
                annual_hydrogen_production += annual_electricity_demand_market_node[electrolysis_technology] * electrolysis_assumptions[electrolysis_technology]["efficiency"]

            # Add the annualized electrolyzer and electricity costs
            annualized_electricity_costs += annual_electricity_demand_market_node * electricity_costs
        else:
            annualized_electricity_costs = pd.Series(0, index=electrolysis_assumptions.keys())

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

    # Return the relative or absolute costs
    if annual_costs:
        return total_costs
    return total_costs / annual_hydrogen_production
