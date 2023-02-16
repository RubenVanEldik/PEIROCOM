import streamlit as st
import pandas as pd

import utils
import validate


def _calculate_scenario_costs(assumptions, variable, scenario_level):
    """
    Calculate the costs for a given scenario level
    """
    assert validate.is_dict(assumptions)
    assert validate.is_string(variable)
    assert validate.is_number(scenario_level, min_value=-1, max_value=1)

    if scenario_level == -1:
        return assumptions["conservative"][variable]
    elif scenario_level == 0:
        return assumptions["moderate"][variable]
    elif scenario_level == 1:
        return assumptions["advanced"][variable]
    elif scenario_level > 0:
        return (1 - scenario_level) * assumptions["moderate"][variable] + scenario_level * assumptions["advanced"][variable]
    elif scenario_level < 0:
        return (1 + scenario_level) * assumptions["moderate"][variable] - scenario_level * assumptions["conservative"][variable]


def _calculate_annualized_electrolyzer_costs(electrolysis_technologies, electrolyzer_capacity_MW):
    """
    Calculate the annualized electrolyzer costs
    """
    assert validate.is_dict(electrolysis_technologies)
    assert validate.is_series(electrolyzer_capacity_MW)

    # Read the electrolysis assumptions
    electrolysis_assumptions = utils.get_technologies(technology_type="electrolysis")

    # Calculate the total annual costs
    annualized_costs_electrolyzer = pd.Series([], dtype="float64")
    for technology, scenario_level in electrolysis_technologies.items():
        capacity_kW = electrolyzer_capacity_MW[technology] * 1000
        capex = capacity_kW * _calculate_scenario_costs(electrolysis_assumptions[technology], "capex", scenario_level)
        fixed_om = capacity_kW * _calculate_scenario_costs(electrolysis_assumptions[technology], "fixed_om", scenario_level)
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
    return demand_MW.sum() * timestep_hours / share_of_year_modelled


def calculate_lcoh(electrolysis_capacity, electricity_demand, electricity_costs, *, config, breakdown_level=0, annual_costs=False):
    """
    Calculate the average Levelized Costs of Hydrogen for all bidding zones
    """
    assert validate.is_dataframe(electrolysis_capacity)
    assert validate.is_bidding_zone_dict(electricity_demand, required=not annual_costs)
    assert validate.is_number(electricity_costs, required=electricity_demand is not None)
    assert validate.is_config(config)
    assert validate.is_breakdown_level(breakdown_level)
    assert validate.is_bool(annual_costs)

    # Get the electrolysis assumptions
    electrolysis_assumptions = utils.get_technologies(technology_type="electrolysis")

    annualized_electrolyzer_costs = 0
    annualized_electricity_costs = 0
    annual_hydrogen_production = 0
    for bidding_zone in electrolysis_capacity.index:
        # Calculate the annualized electrolyzer costs
        annualized_electrolyzer_costs += _calculate_annualized_electrolyzer_costs(config["technologies"]["electrolysis"], electrolysis_capacity.loc[bidding_zone])

        # Calculate the annual electricity demand and electricity costs for electrolysis
        if electricity_demand is not None:
            annual_electricity_demand_bidding_zone = _calculate_annual_electricity_demand(electricity_demand[bidding_zone], electricity_costs)

            # Calculate the annual hydrogen production
            for electrolysis_technology in electrolysis_assumptions:
                annual_hydrogen_production += annual_electricity_demand_bidding_zone[electrolysis_technology] * electrolysis_assumptions[electrolysis_technology]["efficiency"]

            # Add the annualized electrolyzer and electricity costs
            annualized_electricity_costs += annual_electricity_demand_bidding_zone * electricity_costs
        else:
            annualized_electricity_costs = pd.Series(0, index=electrolysis_assumptions.keys())

    # Calculate and return the LCOH
    if breakdown_level == 0:
        total_costs = annualized_electrolyzer_costs.sum() + annualized_electricity_costs.sum()
    if breakdown_level == 1:
        total_costs = pd.Series({"electrolyzer": annualized_electrolyzer_costs.sum(), "electricity": annualized_electricity_costs.sum()})
    if breakdown_level == 2:
        total_costs = pd.concat([annualized_electrolyzer_costs.rename("electrolyzer"), annualized_electricity_costs.rename("electricity")], axis=1)

    # Convert the costs from Dollar to Euro
    eur_usd = 1.1290  # Source: https://www.federalreserve.gov/releases/h10/20220110/
    total_costs /= eur_usd

    # Return the relative or absolute costs
    if annual_costs:
        return total_costs
    return total_costs / annual_hydrogen_production
