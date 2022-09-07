import streamlit as st

import utils
import validate


def firm_lcoe(output_directory, resolution, *, country_codes=None, breakdown_level=0):
    """
    Calculate the firm LCOE for a specific run
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_resolution(resolution)
    assert validate.is_country_code_list(country_codes, code_type="nuts_2", required=False)
    assert validate.is_breakdown_level(breakdown_level)

    # Get the capacities and demand
    production_capacity = utils.get_production_capacity(output_directory, resolution, country_codes=country_codes)
    storage_capacity = utils.get_storage_capacity(output_directory, resolution, country_codes=country_codes)
    temporal_results = utils.get_temporal_results(output_directory, resolution, country_codes=country_codes)
    temporal_demand = utils.merge_dataframes_on_column(temporal_results, "demand_MW")
    temporal_baseload = utils.merge_dataframes_on_column(temporal_results, "baseload_MW")
    temporal_export = utils.merge_dataframes_on_column(temporal_results, "net_export_MW")
    temporal_net_demand = temporal_demand - temporal_baseload + temporal_export
    config = utils.read_yaml(output_directory / "config.yaml")

    # Return the LCOE
    return utils.calculate_lcoe(production_capacity, storage_capacity, temporal_net_demand, config=config, breakdown_level=breakdown_level)


def unconstrained_lcoe(output_directory, resolution, *, country_codes=None, breakdown_level=0):
    """
    Calculate the unconstrained_lcoe LCOE for a specific run
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_resolution(resolution)
    assert validate.is_country_code_list(country_codes, code_type="nuts_2", required=False)
    assert validate.is_breakdown_level(breakdown_level)

    # Get the capacities and demand
    production_capacity = utils.get_production_capacity(output_directory, resolution, country_codes=country_codes)
    storage_capacity = utils.get_storage_capacity(output_directory, resolution, country_codes=country_codes)
    temporal_results = utils.get_temporal_results(output_directory, resolution, country_codes=country_codes)
    temporal_demand = utils.merge_dataframes_on_column(temporal_results, "production_total_MW")
    config = utils.read_yaml(output_directory / "config.yaml")

    # Return the LCOE
    return utils.calculate_lcoe(production_capacity, storage_capacity, temporal_demand, config=config, breakdown_level=breakdown_level)


def premium(output_directory, resolution, *, country_codes=None, breakdown_level=0):
    """
    Calculate the firm kWh premium
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_resolution(resolution)
    assert validate.is_country_code_list(country_codes, code_type="nuts_2", required=False)
    assert validate.is_breakdown_level(breakdown_level)

    # Get the capacities and demand
    firm_lcoe_result = firm_lcoe(output_directory, resolution, country_codes=country_codes, breakdown_level=breakdown_level)
    unconstrained_lcoe_result = unconstrained_lcoe(output_directory, resolution, country_codes=country_codes, breakdown_level=0)

    # Return the firm kWh premium
    return firm_lcoe_result / unconstrained_lcoe_result


def relative_curtailment(output_directory, resolution, *, country_codes=None):
    """
    Calculate the relative curtailment
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_resolution(resolution)
    assert validate.is_country_code_list(country_codes, code_type="nuts_2", required=False)

    temporal_results = utils.get_temporal_results(output_directory, resolution, group="all", country_codes=country_codes)
    return temporal_results.curtailed_MW.sum() / temporal_results.production_total_MW.sum()


def production_capacity(output_directory, resolution, *, country_codes=None):
    """
    Return a dictionary with the production capacity per production type
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_resolution(resolution)
    assert validate.is_country_code_list(country_codes, code_type="nuts_2", required=False)

    production_capacity = utils.get_production_capacity(output_directory, resolution, group="all", country_codes=country_codes)
    return production_capacity.to_dict()


def storage_capacity(output_directory, resolution, *, storage_type, country_codes=None):
    """
    Return a dictionary with the storage capacity per storage type for either 'energy' or 'power'
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_resolution(resolution)
    assert validate.is_string(storage_type)
    assert validate.is_country_code_list(country_codes, code_type="nuts_2", required=False)

    storage_capacity = utils.get_storage_capacity(output_directory, resolution, group="all", country_codes=country_codes)

    # Return an empty dictionary if there is no storage
    if storage_capacity is None:
        return {}

    return storage_capacity[storage_type].to_dict()


def self_sufficiency(output_directory, resolution, *, country_codes=None):
    """
    Return the self-sufficiency factor for the selected countries
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_resolution(resolution)
    assert validate.is_country_code_list(country_codes, code_type="nuts_2", required=False)

    temporal_results = utils.get_temporal_results(output_directory, resolution, country_codes=country_codes)
    mean_demand = utils.merge_dataframes_on_column(temporal_results, "demand_MW").mean(axis=1)
    mean_baseload = utils.merge_dataframes_on_column(temporal_results, "baseload_MW").mean(axis=1)
    mean_production = utils.merge_dataframes_on_column(temporal_results, "production_total_MW").mean(axis=1)
    mean_curtailment = utils.merge_dataframes_on_column(temporal_results, "curtailed_MW").mean(axis=1)
    mean_storage_flow = utils.merge_dataframes_on_column(temporal_results, "net_storage_flow_total_MW").mean(axis=1)

    return (mean_baseload + mean_production - mean_curtailment - mean_storage_flow).mean() / mean_demand.mean()
