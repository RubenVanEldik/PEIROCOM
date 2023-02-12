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


def _calculate_annualized_generation_costs(generation_technologies, generation_capacity_MW):
    """
    Calculate the annualized generation costs
    """
    assert validate.is_dict(generation_technologies)
    assert validate.is_dataframe(generation_capacity_MW, column_validator=validate.is_technology)

    # Read the generation assumptions
    generation_assumptions = utils.get_technologies(technology_type="generation")

    # Calculate the total annual generation costs
    annualized_costs_generation = pd.Series([], dtype="float64")
    for technology, scenario_level in generation_technologies.items():
        capacity_kW = generation_capacity_MW[technology].sum() * 1000
        capex = capacity_kW * _calculate_scenario_costs(generation_assumptions[technology], "capex", scenario_level)
        fixed_om = capacity_kW * _calculate_scenario_costs(generation_assumptions[technology], "fixed_om", scenario_level)
        crf = _calculate_crf(generation_assumptions[technology])
        annualized_costs_generation[technology] = crf * capex + fixed_om

    return annualized_costs_generation


def _calculate_annualized_hydropower_costs(hydropower_technologies, hydropower_capacity):
    """
    Calculate the annualized hydropower costs
    """
    assert validate.is_dict(hydropower_technologies)
    assert validate.is_dataframe(hydropower_capacity)

    # Read the hydropower assumptions
    hydropower_assumptions = utils.get_technologies(technology_type="hydropower")

    # Calculate the total annual hydropower costs
    annualized_costs_hydropower = pd.Series([], dtype="float64")
    for technology, scenario_level in hydropower_technologies.items():
        # Calculate costs for the turbine capacity
        turbine_capacity_kW = hydropower_capacity.loc[technology, "turbine"] * 1000
        capex = turbine_capacity_kW * _calculate_scenario_costs(hydropower_assumptions[technology], "capex_power", scenario_level)
        fixed_om = turbine_capacity_kW * _calculate_scenario_costs(hydropower_assumptions[technology], "fixed_om_power", scenario_level)

        # Calculate the total annualized costs
        crf = _calculate_crf(hydropower_assumptions[technology])
        annualized_costs_hydropower[technology] = crf * capex + fixed_om

    return annualized_costs_hydropower


def _calculate_annualized_storage_costs(storage_technologies, storage_capacity_MWh):
    """
    Calculate the annualized storage costs
    """
    assert validate.is_dict(storage_technologies)
    assert validate.is_dataframe(storage_capacity_MWh)

    # Read the storage assumptions
    storage_assumptions = utils.get_technologies(technology_type="storage")

    # Calculate the total annual storage costs
    annualized_costs_storage = pd.Series([], dtype="float64")
    for technology, scenario_level in storage_technologies.items():
        capacity_energy_kWh = storage_capacity_MWh.loc[technology, "energy"] * 1000
        capacity_power_kW = storage_capacity_MWh.loc[technology, "power"] * 1000

        # Calculate CAPEX
        capex_energy = capacity_energy_kWh * _calculate_scenario_costs(storage_assumptions[technology], "capex_energy", scenario_level)
        capex_power = capacity_power_kW * _calculate_scenario_costs(storage_assumptions[technology], "capex_power", scenario_level)
        capex = capex_energy + capex_power

        # Calcalate fixed O&M
        fixed_om_energy = capacity_energy_kWh * _calculate_scenario_costs(storage_assumptions[technology], "fixed_om_energy", scenario_level)
        fixed_om_power = capacity_power_kW * _calculate_scenario_costs(storage_assumptions[technology], "fixed_om_power", scenario_level)
        fixed_om = fixed_om_energy + fixed_om_power

        # Calculate the total annualized costs
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


def calculate_lcoe(generation_capacity, storage_capacity, hydropower_capacity, demand_per_bidding_zone, *, config, breakdown_level=0):
    """
    Calculate the average LCOE for all bidding zones
    """
    assert validate.is_bidding_zone_dict(generation_capacity)
    assert validate.is_bidding_zone_dict(storage_capacity)
    assert validate.is_bidding_zone_dict(hydropower_capacity)
    assert validate.is_dataframe(demand_per_bidding_zone, column_validator=validate.is_bidding_zone)
    assert validate.is_config(config)
    assert validate.is_breakdown_level(breakdown_level)

    annualized_generation_costs = 0
    annualized_storage_costs = 0
    annualized_hydropower_costs = 0
    annual_electricity_demand = 0

    for bidding_zone in demand_per_bidding_zone.columns:
        # Add the annualized generation and storage costs
        annualized_generation_costs += _calculate_annualized_generation_costs(config["technologies"]["generation"], generation_capacity[bidding_zone])
        annualized_hydropower_costs += _calculate_annualized_hydropower_costs(config["technologies"]["hydropower"], hydropower_capacity[bidding_zone])
        annualized_storage_costs += _calculate_annualized_storage_costs(config["technologies"]["storage"], storage_capacity[bidding_zone])

        # Add the annual electricity demand
        annual_electricity_demand += _calculate_annual_demand(demand_per_bidding_zone[bidding_zone])

    # Calculate and return the LCOE
    if breakdown_level == 0:
        total_costs = annualized_generation_costs.sum() + annualized_storage_costs.sum() + annualized_hydropower_costs.sum()
    if breakdown_level == 1:
        total_costs = pd.Series({"generation": annualized_generation_costs.sum(), "hydropower": annualized_hydropower_costs.sum(), "storage": annualized_storage_costs.sum()})
    if breakdown_level == 2:
        total_costs = pd.concat([annualized_generation_costs, annualized_storage_costs, annualized_hydropower_costs])
    eur_usd = 1.1290  # Source: https://www.federalreserve.gov/releases/h10/20220110/
    return (total_costs / annual_electricity_demand) / eur_usd
