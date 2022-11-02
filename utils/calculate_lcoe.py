import pandas as pd

import utils
import validate


def _calculate_crf(assumptions):
    """
    Calculate the Capital Recovery Factor for a specic set of technology assumptions
    """
    assert validate.is_dict(assumptions)

    wacc = assumptions["wacc"]
    economic_lifetime = assumptions["economic_lifetime"]
    return wacc / (1 - (1 + wacc) ** (-economic_lifetime))


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


def _calculate_annualized_production_costs(production_technologies, production_capacity_MW):
    """
    Calculate the annualized production costs
    """
    assert validate.is_dict(production_technologies)
    assert validate.is_dataframe(production_capacity_MW, column_validator=validate.is_technology)

    # Read the production assumptions
    production_assumptions = utils.read_yaml(utils.path("input", "technologies", "production.yaml"))

    # Calculate the total annual production costs
    annualized_costs_production = pd.Series([], dtype="float64")
    for technology, scenario_level in production_technologies.items():
        capacity_kW = production_capacity_MW[technology].sum() * 1000
        capex = capacity_kW * _calculate_scenario_costs(production_assumptions[technology], "capex", scenario_level)
        fixed_om = capacity_kW * _calculate_scenario_costs(production_assumptions[technology], "fixed_om", scenario_level)
        crf = _calculate_crf(production_assumptions[technology])
        annualized_costs_production[technology] = crf * capex + fixed_om

    return annualized_costs_production


def _calculate_annualized_storage_costs(storage_technologies, storage_capacity_MWh):
    """
    Calculate the annualized storage costs
    """
    assert validate.is_dict(storage_technologies)
    assert validate.is_dataframe(storage_capacity_MWh)

    # Read the storage assumptions
    storage_assumptions = utils.read_yaml(utils.path("input", "technologies", "storage.yaml"))

    # Calculate the total annual storage costs
    annualized_costs_storage = pd.Series([], dtype="float64")
    for technology, scenario_level in storage_technologies.items():
        capacity_energy_kWh = storage_capacity_MWh.loc[technology, "energy"] * 1000
        capacity_power_kW = storage_capacity_MWh.loc[technology, "power"] * 1000

        capex_energy = capacity_energy_kWh * _calculate_scenario_costs(storage_assumptions[technology], "energy_capex", scenario_level)
        capex_power = capacity_power_kW * _calculate_scenario_costs(storage_assumptions[technology], "power_capex", scenario_level)
        capex = capex_energy + capex_power
        fixed_om = capex * storage_assumptions[technology]["fixed_om"]
        crf = _calculate_crf(storage_assumptions[technology])
        annualized_costs_storage[technology] = crf * capex + fixed_om

    return annualized_costs_storage


def _calculate_annual_demand(demand_MW):
    """
    Calculate the annual electricity demand
    """
    assert validate.is_series(demand_MW)

    demand_start_date = demand_MW.index.min()
    demand_end_date = demand_MW.index.max()
    share_of_year_modelled = (demand_end_date - demand_start_date) / pd.Timedelta(365, "days")
    timestep_hours = (demand_MW.index[1] - demand_MW.index[0]).total_seconds() / 3600
    return demand_MW.sum() * timestep_hours / share_of_year_modelled


def calculate_lcoe(production_capacities, storage_capacities, demand_per_bidding_zone, *, config, breakdown_level=0):
    """
    Calculate the average LCOE for all bidding zones
    """
    assert validate.is_bidding_zone_dict(production_capacities)
    assert validate.is_bidding_zone_dict(storage_capacities, required=False)
    assert validate.is_dataframe(demand_per_bidding_zone, column_validator=validate.is_bidding_zone)
    assert validate.is_config(config)
    assert validate.is_breakdown_level(breakdown_level)

    annualized_production_costs = 0
    annualized_storage_costs = 0
    annual_electricity_demand = 0

    for bidding_zone in demand_per_bidding_zone.columns:
        # Add the annualized production and storage costs
        annualized_production_costs += _calculate_annualized_production_costs(config["technologies"]["production"], production_capacities[bidding_zone])
        annualized_storage_costs += _calculate_annualized_storage_costs(config["technologies"]["storage"], storage_capacities[bidding_zone])

        # Add the annual electricity demand
        annual_electricity_demand += _calculate_annual_demand(demand_per_bidding_zone[bidding_zone])

    # Calculate and return the LCOE
    if breakdown_level == 0:
        total_costs = annualized_production_costs.sum() + annualized_storage_costs.sum()
    if breakdown_level == 1:
        total_costs = pd.Series({"production": annualized_production_costs.sum(), "storage": annualized_storage_costs.sum()})
    if breakdown_level == 2:
        total_costs = pd.concat([annualized_production_costs, annualized_storage_costs])
    eur_usd = 1.1290  # Source: https://www.federalreserve.gov/releases/h10/20220110/
    return (total_costs / annual_electricity_demand) / eur_usd
