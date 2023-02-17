import math
from datetime import datetime, timedelta
import gurobipy as gp
import numpy as np
import pandas as pd
import re
import streamlit as st

import utils
import validate


def optimize(config, *, status, output_directory):
    """
    Create and run the model
    """
    assert validate.is_config(config)
    assert validate.is_directory_path(output_directory)

    # Create a dictionary to store the run duration of the different phases
    duration = {}
    initializing_start = datetime.now()

    # Check if the interconnections should be optimized individually
    include_hydrogen_production = len(config["technologies"]["electrolysis"]) > 0
    optimize_individual_interconnections = config["interconnections"]["optimize_individual_interconnections"] == True and config["interconnections"]["relative_capacity"] != 1

    # Calculate the interval length in hours
    interval_length = pd.Timedelta(config["resolution"]).total_seconds() / 3600

    """
    Step 1: Create the model and set the parameters
    """
    model = gp.Model(config["name"])
    model.setParam("OutputFlag", 0)

    # Set the user defined parameters
    model.setParam("Threads", config["optimization"]["thread_count"])
    model.setParam("Method", config["optimization"]["method"])
    if config["optimization"]["method"] == 2:
        model.setParam("BarConvTol", config["optimization"]["barrier_convergence_tolerance"])
        model.setParam("BarIterLimit", config["optimization"]["max_barrier_iterations"])

    # Disable crossover and set BarHomogeneous and Aggregate
    model.setParam("Crossover", 0)
    model.setParam("BarHomogeneous", 1)  # Don't know what this does, but it speeds up some more complex models
    model.setParam("Aggregate", 0)  # Don't know what this does, but it speeds up some more complex models
    model.setParam("Presolve", 2)  # Use an aggressive presolver
    model.setParam("NumericFocus", 1)

    """
    Step 2: Get the temporal demand data
    """
    status.update("Importing demand data")
    # Get the temporal demand and remove leap days
    demand_filepath = utils.path("input", "scenarios", config["scenario"], "demand.csv")
    temporal_demand_fixed = utils.read_temporal_data(demand_filepath, start_year=config["climate_years"]["start"], end_year=config["climate_years"]["end"]).resample(config["resolution"]).mean()
    temporal_demand_fixed = temporal_demand_fixed[~((temporal_demand_fixed.index.month == 2) & (temporal_demand_fixed.index.day == 29))]
    # Remove all bidding zones that are not part of the optimization
    bidding_zones = utils.get_bidding_zones_for_countries(config["country_codes"])
    temporal_demand_fixed = temporal_demand_fixed[bidding_zones]
    # Create a copy of the fixed demand (later on the mean electrolysis demand will be added to it)
    temporal_demand_assumed = temporal_demand_fixed.copy()

    """
    Step 3: Initialize each bidding zone
    """
    # Create dictionaries to store all the data per bidding zone
    temporal_ires = {}
    temporal_results = {}
    temporal_export = {}
    interconnection_capacity = {}
    ires_capacity = {}
    hydropower_capacity = {}
    storage_capacity = {}
    electrolysis_capacity = pd.DataFrame()

    for index, bidding_zone in enumerate(bidding_zones):
        """
        Step 3A: Import the temporal data
        """
        country_flag = utils.get_country_property(utils.get_country_of_bidding_zone(bidding_zone), "flag")
        status.update(f"{country_flag} Importing IRES data")

        # Get the temporal data and resample to the required resolution
        ires_filepath = utils.path("input", "scenarios", config["scenario"], "ires", f"{bidding_zone}.csv")
        temporal_ires[bidding_zone] = utils.read_temporal_data(ires_filepath, start_year=config["climate_years"]["start"], end_year=config["climate_years"]["end"]).resample(config["resolution"]).mean()
        # Remove the leap days from the dataset that could have been introduced by the resample method
        temporal_ires[bidding_zone] = temporal_ires[bidding_zone][~((temporal_ires[bidding_zone].index.month == 2) & (temporal_ires[bidding_zone].index.day == 29))]
        # Create a temporal_results DataFrame with the demand_total_MW and demand_fixed_MW columns
        temporal_results[bidding_zone] = pd.DataFrame(temporal_demand_fixed[bidding_zone].rename("demand_total_MW"))
        temporal_results[bidding_zone]["demand_fixed_MW"] = temporal_results[bidding_zone].demand_total_MW

        """
        Step 3B: Define the electrolysis variables
        """
        if include_hydrogen_production:
            # Calculate the mean hourly electricity demand for hydrogen production
            # (This is both the hourly mean and the non-weighted mean of the efficiency; the mean of efficiency is used as its mathemetically impossible in this LP to use the variables)
            country_code = utils.get_country_of_bidding_zone(bidding_zone)
            annual_hydrogen_demand_country = config.get("relative_hydrogen_demand", 1) * utils.get_country_property(country_code, "annual_hydrogen_demand")
            number_of_bidding_zones_in_country = len(utils.get_bidding_zones_for_countries([country_code]))
            annual_hydrogen_demand_bidding_zone = annual_hydrogen_demand_country / number_of_bidding_zones_in_country
            mean_electrolysis_efficiency = sum(utils.get_technologies(technology_type="electrolysis")[electrolysis_technology]["efficiency"] for electrolysis_technology in config["technologies"]["electrolysis"]) / len(config["technologies"]["electrolysis"])
            mean_temporal_electrolysis_demand = annual_hydrogen_demand_bidding_zone / mean_electrolysis_efficiency / 8760
            temporal_demand_assumed += mean_temporal_electrolysis_demand

            for electrolysis_technology in config["technologies"]["electrolysis"]:
                status.update(f"{country_flag} Adding {utils.format_technology(electrolysis_technology)} electrolysis")

                # Create the variable for the electrolysis production capacity
                electrolysis_capacity_bidding_zone = model.addVar()
                electrolysis_capacity.loc[bidding_zone, electrolysis_technology] = electrolysis_capacity_bidding_zone

                # Create the temporal electrolysis demand variables
                temporal_electrolysis_demand = model.addVars(temporal_demand_fixed.index)
                temporal_results[bidding_zone][f"demand_{electrolysis_technology}_MW"] = pd.Series(temporal_electrolysis_demand)
                temporal_results[bidding_zone]["demand_total_MW"] += pd.Series(temporal_electrolysis_demand)

                # Ensure that the temporal demand does not exceed the electrolysis capacity
                model.addConstrs(temporal_electrolysis_demand[timestamp] <= electrolysis_capacity_bidding_zone for timestamp in temporal_demand_fixed.index)

        """
        Step 3C: Define IRES capacity variables
        """
        # Create an empty DataFrame for the IRES capacities
        ires_capacity[bidding_zone] = pd.DataFrame(columns=config["technologies"]["ires"])

        temporal_results[bidding_zone]["generation_ires_MW"] = 0
        for ires_technology in config["technologies"]["ires"]:
            status.update(f"{country_flag} Adding {utils.format_technology(ires_technology, capitalize=False)} generation")

            # Create a capacity variable for each climate zone
            climate_zones = [re.match(f"{ires_technology}_(.+)_cf", column).group(1) for column in temporal_ires[bidding_zone].columns if column.startswith(f"{ires_technology}_")]
            ires_potential = utils.get_ires_potential_in_climate_zone(bidding_zone, ires_technology, config=config)
            current_capacity = utils.get_current_ires_capacity_in_climate_zone(bidding_zone, ires_technology, config=config)
            capacities = model.addVars(climate_zones, lb=current_capacity, ub=ires_potential)

            # Add the capacities to the ires_capacity DataFrame and calculate the temporal generation for a specific technology
            temporal_ires_generation = 0
            for climate_zone, capacity in capacities.items():
                ires_capacity[bidding_zone].loc[climate_zone, ires_technology] = capacity
                # Apply is required, otherwise it will throw a ValueError if there are more than a few thousand rows (see https://stackoverflow.com/questions/64801287)
                temporal_ires_generation += temporal_ires[bidding_zone][f"{ires_technology}_{climate_zone}_cf"].apply(lambda cf: cf * capacity)
            temporal_results[bidding_zone][f"generation_{ires_technology}_MW"] = temporal_ires_generation
            temporal_results[bidding_zone]["generation_ires_MW"] += temporal_ires_generation

        """
        Step 3D: Define the hydropower variables and constraints
        """
        # Create a DataFrame for the hydropower capacity in this bidding zone
        hydropower_capacity[bidding_zone] = pd.DataFrame(0, index=config["technologies"]["hydropower"], columns=["turbine", "pump", "reservoir"])

        # Add the total net generation and total reservoir columns to the results DataFrame
        temporal_results[bidding_zone]["generation_total_hydropower_MW"] = 0
        temporal_results[bidding_zone]["energy_stored_total_hydropower_MWh"] = 0

        for hydropower_technology in config["technologies"]["hydropower"]:
            status.update(f"{country_flag} Adding {utils.format_technology(hydropower_technology, capitalize=False)} hydropower")

            # Get the specific hydropower assumptions and calculate the interval length
            hydropower_assumptions = utils.get_technologies(technology_type="hydropower")[hydropower_technology]
            efficiency = hydropower_assumptions["roundtrip_efficiency"] ** 0.5

            # Add the relevant capacity to the hydropower_capacity DataFrame, if the capacity is not defined, set the capacity to 0
            hydropower_capacity_current_technology = utils.read_csv(utils.path("input", "scenarios", config["scenario"], "hydropower", hydropower_technology, "capacity.csv"), index_col=0)
            default_hydropower_capacity = pd.Series(0, index=hydropower_capacity_current_technology.columns)
            installed_hydropower_capacity = hydropower_capacity_current_technology.transpose().get(bidding_zone, default_hydropower_capacity)
            relative_hydropower_capacity = config["technologies"].get("relative_hydropower_capacity", 1)
            hydropower_capacity[bidding_zone].loc[hydropower_technology] = relative_hydropower_capacity * installed_hydropower_capacity

            # Get the turbine, pump, and reservoir capacity
            turbine_capacity = hydropower_capacity[bidding_zone].loc[hydropower_technology, "turbine"]
            pump_capacity = hydropower_capacity[bidding_zone].loc[hydropower_technology, "pump"]
            reservoir_capacity = hydropower_capacity[bidding_zone].loc[hydropower_technology, "reservoir"]

            # Skip this hydropower technology if it does not have any turbine capacity in this bidding zone
            if turbine_capacity == 0:
                temporal_results[bidding_zone][f"generation_{hydropower_technology}_hydropower_MW"] = 0
                temporal_results[bidding_zone][f"energy_stored_{hydropower_technology}_hydropower_MWh"] = 0
                continue

            # Get the temporal hydropower data
            filepath = utils.path("input", "scenarios", config["scenario"], "hydropower", hydropower_technology, f"{bidding_zone}.csv")
            temporal_hydropower_data = utils.read_temporal_data(filepath, start_year=config["climate_years"]["start"], end_year=config["climate_years"]["end"])
            # Calculate the interval length of the hydropower data
            hydropower_interval_length = (temporal_hydropower_data.index[1] - temporal_hydropower_data.index[0]).total_seconds() / 3600
            # Resample the hydropower data to the selected resolution
            temporal_hydropower_data = temporal_hydropower_data.resample(config["resolution"]).mean()
            # Remove the leap days from the dataset that could have been introduced by the resample method
            temporal_hydropower_data = temporal_hydropower_data[~((temporal_hydropower_data.index.month == 2) & (temporal_hydropower_data.index.day == 29))]
            # Find and add the rows that are missing in the previous results (the resample method does not add rows after the last timestamp and some weeks don't start on January 1st)
            for timestamp in temporal_results[bidding_zone].index.difference(temporal_hydropower_data.index):
                temporal_hydropower_data.loc[timestamp] = pd.Series([], dtype="float64")  # Sets None to all columns in the new row
            # Sort the DataFrame on its index (the first days of January, when missing, are added to the end of the DataFrame)
            temporal_hydropower_data = temporal_hydropower_data.sort_index()

            # Calculate the average inflow in MW
            inflow_MW = temporal_hydropower_data["inflow_MWh"].ffill().bfill() / hydropower_interval_length

            # Set the net hydropower generation to the inflow if there is no reservoir capacity
            if reservoir_capacity == 0:
                temporal_results[bidding_zone][f"generation_{hydropower_technology}_hydropower_MW"] = inflow_MW
                temporal_results[bidding_zone]["generation_total_hydropower_MW"] += inflow_MW
                temporal_results[bidding_zone][f"energy_stored_{hydropower_technology}_hydropower_MWh"] = 0
                continue

            # Create temporal variables for the turbine flow
            min_turbine_flow = temporal_hydropower_data.min_generation_MW.ffill().bfill().fillna(0)
            max_turbine_flow = temporal_hydropower_data.max_generation_MW.ffill().bfill().fillna(turbine_capacity)
            turbine_flow = pd.Series(model.addVars(temporal_hydropower_data.index, lb=min_turbine_flow, ub=max_turbine_flow))

            # Create temporal variables for the pump flow
            min_pump_flow = temporal_hydropower_data.min_pumping_MW.ffill().bfill().fillna(0)
            max_pump_flow = temporal_hydropower_data.max_pumping_MW.ffill().bfill().fillna(pump_capacity)
            pump_flow = pd.Series(model.addVars(temporal_hydropower_data.index, lb=min_pump_flow, ub=max_pump_flow))

            # Add the net hydropower generation variables to the temporal_results DataFrame
            net_flow = turbine_flow - pump_flow
            temporal_results[bidding_zone][f"generation_{hydropower_technology}_hydropower_MW"] = net_flow
            temporal_results[bidding_zone]["generation_total_hydropower_MW"] += net_flow

            # Loop over all hours
            reservoir_previous = None
            temporal_reservoir_dict = {}
            for timestamp in temporal_demand_fixed.index:
                # Create the reservoir level variable
                current_reservoir_soc = temporal_hydropower_data.loc[timestamp, "reservoir_soc"]
                if np.isnan(current_reservoir_soc):
                    current_min_reservoir_soc = temporal_hydropower_data.loc[timestamp, "min_reservoir_soc"]
                    current_max_reservoir_soc = temporal_hydropower_data.loc[timestamp, "max_reservoir_soc"]
                    min_reservoir_soc = 0 if np.isnan(current_min_reservoir_soc) else current_min_reservoir_soc
                    max_reservoir_soc = 1 if np.isnan(current_max_reservoir_soc) else current_max_reservoir_soc
                    reservoir_current = model.addVar(lb=min_reservoir_soc, ub=max_reservoir_soc) * reservoir_capacity
                else:
                    reservoir_current = current_reservoir_soc * reservoir_capacity

                # Add the reservoir level constraint with regard to the previous timestamp
                if reservoir_previous:
                    model.addConstr(reservoir_current == reservoir_previous + (inflow_MW[timestamp] - turbine_flow[timestamp] / efficiency + pump_flow[timestamp] * efficiency) * interval_length)

                # Add the current reservoir level to temporal_reservoir_dict
                temporal_reservoir_dict[timestamp] = reservoir_current

                # Update reservoir_previous
                reservoir_previous = reservoir_current

            # Add the temporal reservoir levels to the temporal_results DataFrame
            temporal_reservoir = pd.Series(temporal_reservoir_dict)
            temporal_results[bidding_zone][f"energy_stored_{hydropower_technology}_hydropower_MWh"] = temporal_reservoir
            temporal_results[bidding_zone]["energy_stored_total_hydropower_MWh"] += temporal_reservoir

        """
        Step 3E: Define storage variables and constraints
        """
        # Create a DataFrame for the storage capacity in this bidding zone
        storage_capacity[bidding_zone] = pd.DataFrame(0, index=config["technologies"]["storage"], columns=["energy", "power"])

        # Add the total storage flow and total stored energy columns to the results DataFrame
        temporal_results[bidding_zone]["net_storage_flow_total_MW"] = 0
        temporal_results[bidding_zone]["energy_stored_total_MWh"] = 0

        # Add the variables and constraints for all storage technologies
        for storage_technology in config["technologies"]["storage"]:
            status.update(f"{country_flag} Adding {utils.format_technology(storage_technology, capitalize=False)} storage")

            # Get the specific storage assumptions
            storage_assumptions = utils.get_technologies(technology_type="storage")[storage_technology]
            efficiency = storage_assumptions["roundtrip_efficiency"] ** 0.5

            # Create a variable for the energy and power storage capacity
            storage_capacity[bidding_zone].loc[storage_technology, "energy"] = model.addVar()
            storage_capacity[bidding_zone].loc[storage_technology, "power"] = model.addVar()

            # Create the inflow and outflow variables
            inflow = pd.Series(model.addVars(temporal_demand_fixed.index))
            outflow = pd.Series(model.addVars(temporal_demand_fixed.index))

            # Add the net storage flow variables to the temporal_results DataFrame
            net_flow = inflow - outflow
            temporal_results[bidding_zone][f"net_storage_flow_{storage_technology}_MW"] = net_flow
            temporal_results[bidding_zone]["net_storage_flow_total_MW"] += net_flow

            # Unpack the energy and power capacities for this storage technology
            energy_capacity = storage_capacity[bidding_zone].loc[storage_technology, "energy"]
            power_capacity = storage_capacity[bidding_zone].loc[storage_technology, "power"]

            # Create a variable for each hour for the amount of stored energy
            temporal_energy_stored = pd.Series(model.addVars(temporal_demand_fixed.index))

            # Set the previous energy level to the last energy level
            energy_stored_previous = temporal_energy_stored.tail(1).item()

            # Loop over all hours
            for timestamp in temporal_demand_fixed.index:
                # Create the state of charge variables
                energy_stored_current = temporal_energy_stored[timestamp]

                # Add the SOC constraint with regard to the previous timestamp (if it's the first timestamp it's related to the last timestamp)
                model.addConstr(energy_stored_current == energy_stored_previous + (inflow[timestamp] * efficiency - outflow[timestamp] / efficiency) * interval_length)

                # Add the energy capacity constraints (can't be added when the flow variables are defined because it's a gurobipy.Var)
                model.addConstr(energy_stored_current >= storage_assumptions["soc_min"] * energy_capacity)
                model.addConstr(energy_stored_current <= storage_assumptions["soc_max"] * energy_capacity)

                # Add the power capacity constraints (can't be added when the flow variables are defined because it's a gurobipy.Var)
                model.addConstr(inflow[timestamp] <= power_capacity)
                model.addConstr(outflow[timestamp] <= power_capacity)

                # Update energy_stored_previous
                energy_stored_previous = energy_stored_current

            # Add the temporal energy stored to the temporal_results DataFrame
            temporal_results[bidding_zone][f"energy_stored_{storage_technology}_MWh"] = temporal_energy_stored
            temporal_results[bidding_zone]["energy_stored_total_MWh"] += temporal_energy_stored

        """
        Step 3F: Define the interconnection variables
        """
        # Create empty DataFrames for the interconnections, if they don't exist yet
        if not len(temporal_export):
            temporal_export_columns = pd.MultiIndex.from_tuples([], names=["from", "to"])
            temporal_export["hvac"] = pd.DataFrame(index=temporal_results[bidding_zone].index, columns=temporal_export_columns)
            temporal_export["hvdc"] = pd.DataFrame(index=temporal_results[bidding_zone].index, columns=temporal_export_columns)

        # Create empty DataFrames for the extra interconnection capacity, if they don't exist yet
        if not len(interconnection_capacity):
            interconnection_capacity_index = pd.MultiIndex.from_arrays([[], []], names=("from", "to"))
            interconnection_capacity["hvac"] = pd.DataFrame(index=interconnection_capacity_index, columns=["current", "extra"])
            interconnection_capacity["hvdc"] = pd.DataFrame(index=interconnection_capacity_index, columns=["current", "extra"])

        for connection_type in ["hvac", "hvdc"]:
            status.update(f"{country_flag} Adding {connection_type.upper()} interconnections")
            # Get the export limits
            temporal_export_limits = utils.get_export_limits(bidding_zone, connection_type=connection_type, index=temporal_results[bidding_zone].index, config=config)

            for temporal_export_limit_column_name in temporal_export_limits.columns:
                # Get the current temporal export limits
                temporal_export_limit = temporal_export_limits[temporal_export_limit_column_name]

                # Add the interconnection capacities to the DataFrames and create the temporal interconnection variables
                if optimize_individual_interconnections:
                    # Create a variable for the extra interconnection capacity
                    extra_interconnection_capacity = model.addVar()
                    # Add the mean current and extra interconnection capacity to the interconnection capacity DataFrame
                    interconnection_capacity[connection_type].loc[temporal_export_limit_column_name, "current"] = temporal_export_limit.mean()
                    interconnection_capacity[connection_type].loc[temporal_export_limit_column_name, "extra"] = extra_interconnection_capacity
                    # Add the extra capacity to the temporal export limit
                    temporal_export_limit += extra_interconnection_capacity
                    # Create the variables for the export variables and add the constraint manually (can't use 'ub' because there is a Gurobi variable in the constraint)
                    temporal_export[connection_type][temporal_export_limit_column_name] = pd.Series(model.addVars(temporal_export[connection_type].index))
                    model.addConstrs(temporal_export[connection_type].loc[timestamp, temporal_export_limit_column_name] <= temporal_export_limit.loc[timestamp] for timestamp in temporal_export[connection_type].index)
                else:
                    # Add the mean current and extra interconnection capacity to the interconnection capacity DataFrame
                    interconnection_capacity[connection_type].loc[temporal_export_limit_column_name, "current"] = temporal_export_limit.mean()
                    interconnection_capacity[connection_type].loc[temporal_export_limit_column_name, "extra"] = (config["interconnections"]["relative_capacity"] - 1) * temporal_export_limit.mean()
                    # Multiply the export limits with the relative capacity factor
                    temporal_export_limit *= config["interconnections"]["relative_capacity"]
                    # Create the variables for the export variables
                    temporal_export[connection_type][temporal_export_limit_column_name] = pd.Series(model.addVars(temporal_export[connection_type].index, ub=temporal_export_limit))

    """
    Step 4: Define demand constraints
    """
    for bidding_zone in bidding_zones:
        country_flag = utils.get_country_property(utils.get_country_of_bidding_zone(bidding_zone), "flag")
        status.update(f"{country_flag} Adding demand constraints")

        # Create a dictionary to keep track of the net export per interconnection type
        net_export_per_interconnection_type = {interconnection_type: 0 for interconnection_type in temporal_export}

        # Add a column for the temporal export to each country
        for interconnection_type in temporal_export:
            relevant_temporal_export = [interconnection_bidding_zones for interconnection_bidding_zones in temporal_export[interconnection_type] if bidding_zone in interconnection_bidding_zones]
            for bidding_zone1, bidding_zone2 in relevant_temporal_export:
                # Calculate the export flow
                direction = 1 if bidding_zone1 == bidding_zone else -config["interconnections"]["efficiency"][interconnection_type]
                export_flow = direction * temporal_export[interconnection_type][bidding_zone1, bidding_zone2]

                # Add the export flow to the interconnection type dictionary
                net_export_per_interconnection_type[interconnection_type] += export_flow

                # Add the export flow to the relevant bidding zone column
                other_bidding_zone = bidding_zone1 if bidding_zone2 == bidding_zone else bidding_zone2
                column_name = f"net_export_{other_bidding_zone}_MW"
                if column_name not in temporal_results:
                    temporal_results[bidding_zone][column_name] = 0
                temporal_results[bidding_zone][column_name] += export_flow

        # Add a column for each of the interconnection types
        for interconnection_type in net_export_per_interconnection_type:
            temporal_results[bidding_zone][f"net_export_{interconnection_type}_MW"] = net_export_per_interconnection_type[interconnection_type]

        # Add a column for the total temporal export
        temporal_results[bidding_zone]["net_export_MW"] = 0
        for column_name in temporal_results[bidding_zone]:
            if re.search("^net_export_[A-Z]{2}[0-9a-zA-Z]{2}_MW$", column_name):
                temporal_results[bidding_zone]["net_export_MW"] += temporal_results[bidding_zone][column_name]

        # Add the demand constraint
        temporal_results[bidding_zone].apply(lambda row: model.addConstr(row.generation_ires_MW + row.generation_total_hydropower_MW - row.net_storage_flow_total_MW - row.net_export_MW >= row.demand_total_MW), axis=1)

        # Calculate the curtailed energy per hour
        curtailed_MW = temporal_results[bidding_zone].generation_ires_MW + temporal_results[bidding_zone].generation_total_hydropower_MW - temporal_results[bidding_zone].demand_total_MW - temporal_results[bidding_zone].net_storage_flow_total_MW - temporal_results[bidding_zone].net_export_MW
        temporal_results[bidding_zone].insert(temporal_results[bidding_zone].columns.get_loc("generation_ires_MW"), "curtailed_MW", curtailed_MW)

    """
    Step 5: Define interconnection capacity constraint if the individual interconnections are optimized
    """
    if optimize_individual_interconnections:
        total_current_capacity = sum(interconnection_capacity[connection_type]["current"].sum() for connection_type in ["hvac", "hvdc"])
        total_extra_capacity = sum(interconnection_capacity[connection_type]["extra"].sum() for connection_type in ["hvac", "hvdc"])
        if total_current_capacity > 0:
            model.addConstr((1 + (total_extra_capacity / total_current_capacity)) == config["interconnections"]["relative_capacity"])

    """
    Step 6: Define the self-sufficiency and hydrogen constraints per country
    """
    for country_code in config["country_codes"]:
        country_flag = utils.get_country_property(country_code, "flag")
        status.update(f"{country_flag} Adding self-sufficiency constraint")

        # Set the variables required to calculate the cumulative results in the country
        sum_demand_total = 0
        sum_ires_generation = 0
        sum_hydropower_generation = 0
        sum_curtailed = 0
        sum_storage_flow = 0
        sum_hydrogen_production = 0

        # Loop over all bidding zones in the country
        for bidding_zone in utils.get_bidding_zones_for_countries([country_code]):
            # Calculate the total demand and non-curtailed generation in this country
            sum_demand_total += temporal_demand_assumed[bidding_zone].sum()
            # The Gurobi .quicksum method is significantly faster than Panda's .sum method
            sum_ires_generation += gp.quicksum(temporal_results[bidding_zone].generation_ires_MW)
            sum_hydropower_generation += gp.quicksum(temporal_results[bidding_zone].generation_total_hydropower_MW)
            sum_curtailed += gp.quicksum(temporal_results[bidding_zone].curtailed_MW)
            sum_storage_flow += gp.quicksum(temporal_results[bidding_zone].net_storage_flow_total_MW)

            # Calculate the total hydrogen production
            for electrolysis_technology in config["technologies"]["electrolysis"]:
                electrolyzer_efficiency = utils.get_technologies(technology_type="electrolysis")[electrolysis_technology]["efficiency"]
                sum_hydrogen_production += gp.quicksum(temporal_results[bidding_zone][f"demand_{electrolysis_technology}_MW"]) * interval_length * electrolyzer_efficiency

        # Add the self-sufficiency constraints if there is any demand in the country
        if sum_demand_total > 0:
            self_sufficiency = (sum_ires_generation + sum_hydropower_generation - sum_curtailed - sum_storage_flow) / sum_demand_total
            model.addConstr(self_sufficiency >= config["interconnections"]["min_self_sufficiency"])
            model.addConstr(self_sufficiency <= config["interconnections"]["max_self_sufficiency"])

        # Add the hydrogen constraint to ensure that the temporal hydrogen production equals the total hydrogen demand
        if include_hydrogen_production:
            annual_hydrogen_demand = config.get("relative_hydrogen_demand", 1) * utils.get_country_property(country_code, "annual_hydrogen_demand")
            number_of_years_modeled = 1 + (config["climate_years"]["end"] - config["climate_years"]["start"])
            model.addConstr(sum_hydrogen_production == annual_hydrogen_demand * number_of_years_modeled)

    """
    Step 7: Define the storage costs constraint
    """
    if config.get("fixed_storage") is not None:
        status.update("Adding the storage costs constraint")

        # Calculate the storage costs
        temporal_total_demand = utils.merge_dataframes_on_column(temporal_results, "demand_total_MW")
        storage_costs = utils.calculate_lcoe(ires_capacity, storage_capacity, hydropower_capacity, temporal_total_demand, config=config, breakdown_level=1)["storage"]

        # Add a constraint so the storage costs are either smaller or larger than the fixed storage costs
        fixed_storage_costs = config["fixed_storage"]["costs"]
        if config["fixed_storage"]["direction"] == "gte":
            model.addConstr(storage_costs >= fixed_storage_costs)
        elif config["fixed_storage"]["direction"] == "lte":
            model.addConstr(storage_costs <= fixed_storage_costs)

    """
    Step 8: Set objective function
    """
    status.update("Setting the objective function")

    # Calculate the annual electricity costs
    annual_electricity_costs = utils.calculate_lcoe(ires_capacity, storage_capacity, hydropower_capacity, None, config=config, annual_costs=True)

    # Calculate the annual electrolyzer costs (don't include electricity costs as this is already included in the electricity costs calculation above)
    if include_hydrogen_production:
        annual_electrolyzer_costs = utils.calculate_lcoh(electrolysis_capacity, None, None, config=config, breakdown_level=1, annual_costs=True).electrolyzer
    else:
        annual_electrolyzer_costs = 0

    # Set the objective to the annual system costs
    annualized_system_costs = annual_electricity_costs + annual_electrolyzer_costs
    model.setObjective(annualized_system_costs, gp.GRB.MINIMIZE)

    # Add the initializing duration to the dictionary
    initializing_end = datetime.now()
    duration["initializing"] = round((initializing_end - initializing_start).total_seconds())

    """
    Step 9: Solve model
    """
    # Set the status message and create
    status.update("Optimizing")
    optimizing_start = datetime.now()

    # Create the optimization log expander
    with st.expander("Optimization log"):
        # Create three columns for statistics
        col1, col2, col3 = st.columns(3)
        stat1 = col1.empty()
        stat2 = col2.empty()
        stat3 = col3.empty()

        log_messages = []
        info = st.empty()

    def optimization_callback(model, where):
        """
        Show the intermediate results
        """
        if where == gp.GRB.Callback.BARRIER:
            iteration = model.cbGet(gp.GRB.Callback.BARRIER_ITRCNT)
            objective_value = model.cbGet(gp.GRB.Callback.BARRIER_PRIMOBJ)
            barrier_convergence = model.cbGet(gp.GRB.Callback.BARRIER_PRIMOBJ) / model.cbGet(gp.GRB.Callback.BARRIER_DUALOBJ) - 1
            stat1.metric("Iteration (barrier)", f"{iteration:,}")
            stat2.metric("Objective", f"{objective_value:,.2E}")
            stat3.metric("Convergence", f"{barrier_convergence:.2E}")
        if where == gp.GRB.Callback.SIMPLEX and model.cbGet(gp.GRB.Callback.SPX_ITRCNT) % 1000 == 0:
            iteration = model.cbGet(int(gp.GRB.Callback.SPX_ITRCNT))
            objective_value = model.cbGet(gp.GRB.Callback.SPX_OBJVAL)
            infeasibility = model.cbGet(gp.GRB.Callback.SPX_PRIMINF)
            stat1.metric("Iteration (simplex)", f"{int(iteration):,}")
            stat2.metric("Objective", f"{objective_value:,.2E}")
            stat3.metric("Infeasibility", f"{infeasibility:.2E}")
        if where == gp.GRB.Callback.MESSAGE:
            log_message = model.cbGet(gp.GRB.Callback.MSG_STRING)
            log_messages.append(log_message)

            # Show the log message in the UI or console
            info.code("".join(log_messages))

    def run_optimization(model):
        """
        Run the optimization model recursively
        """
        # Reset the model if there is already a solution
        if model.status != 1:
            model.reset()

        # Run the model
        model.optimize(optimization_callback)

        # Rerun the model with DualReductions disabled if the model is infeasible or unbound
        if model.status == gp.GRB.INF_OR_UNBD:
            model.setParam("DualReductions", 0)
            return run_optimization(model)

        # Rerun the model with an increased numeric focus if there are numeric issues
        if model.status in [gp.GRB.INF_OR_UNBD, gp.GRB.NUMERIC]:
            current_numeric_focus = model.getParamInfo("NumericFocus")[2]
            max_numeric_focus = model.getParamInfo("NumericFocus")[4]
            if current_numeric_focus < max_numeric_focus:
                model.setParam("NumericFocus", current_numeric_focus + 1)
                return run_optimization(model)

    # Run the optimization
    run_optimization(model)

    # Store the LP model and optimization log
    utils.write_text(output_directory / "log.txt", "".join(log_messages))
    if config["optimization"]["store_model"]:
        model.write(f"{output_directory}/model.mps")
        model.write(f"{output_directory}/parameters.prm")

    # Store the quality attributes
    quality = {}
    for column_name, appendix in [("value", ""), ("sum", "Sum"), ("index", "Index")]:
        quality[column_name] = {}
        for quality_attribute in ["BoundVio", "ConstrVio", "ConstrResidual", "DualVio", "DualResidual", "ComplVio"]:
            try:
                quality[column_name][quality_attribute] = model.getAttr(f"{quality_attribute}{appendix}")
            except AttributeError:
                quality[column_name][quality_attribute] = None
    pd.DataFrame(quality).to_csv(output_directory / "quality.csv")

    # Add the optimizing duration to the dictionary
    optimizing_end = datetime.now()
    duration["optimizing"] = round((optimizing_end - optimizing_start).total_seconds())

    """
    Step 10: Check if the model could be solved
    """
    if model.status == gp.GRB.OPTIMAL:
        error_message = None
    elif model.status == gp.GRB.INFEASIBLE:
        error_message = "The model was infeasible"
    elif model.status == gp.GRB.UNBOUNDED:
        error_message = "The model was unbounded"
    elif model.status == gp.GRB.INF_OR_UNBD:
        error_message = "The model was either infeasible or unbounded"
    elif model.status == gp.GRB.CUTOFF:
        error_message = "The optimal objective for the model was worse than the value specified in the Cutoff parameter"
    elif model.status == gp.GRB.ITERATION_LIMIT:
        error_message = "The optimization terminated because the total number of iterations performed exceeded the value specified in the IterationLimit or BarIterLimit parameter"
    elif model.status == gp.GRB.NODE_LIMIT:
        error_message = "The optimization terminated because the total number of branch-and-cut nodes explored exceeded the value specified in the NodeLimit parameter"
    elif model.status == gp.GRB.TIME_LIMIT:
        error_message = f"The optimization terminated due to the time limit in {timedelta(seconds=model.Runtime)}"
    elif model.status == gp.GRB.SOLUTION_LIMIT:
        error_message = "The optimization terminated because the number of solutions found reached the value specified in the SolutionLimit parameter"
    elif model.status == gp.GRB.INTERRUPTED:
        error_message = "The optimization was terminated by the user"
    elif model.status == gp.GRB.NUMERIC:
        error_message = "The optimization was terminated due to unrecoverable numerical difficulties"
    elif model.status == gp.GRB.SUBOPTIMAL:
        error_message = "Unable to satisfy optimality tolerances"
    else:
        error_message = "The model could not be solved for an unknown reason"

    # Don't store the results if the optimization ended with an error
    if error_message is not None:
        return {"duration": duration, "error_message": error_message}

    """
    Step 11: Store the results
    """
    storing_start = datetime.now()

    # Make the temporal subdirectories
    (output_directory / "temporal").mkdir()
    for sub_directory in ["bidding_zones", "interconnections"]:
        (output_directory / "temporal" / sub_directory).mkdir()

    # Make the capacity subdirectories
    (output_directory / "capacity").mkdir()
    for sub_directory in ["ires", "storage", "hydropower", "interconnections"]:
        (output_directory / "capacity" / sub_directory).mkdir()

    # Store the actual values per bidding zone for the temporal results and capacities
    for bidding_zone in bidding_zones:
        country_flag = utils.get_country_property(utils.get_country_of_bidding_zone(bidding_zone), "flag")
        status.update(f"{country_flag} Converting and storing the results")
        # Convert the temporal results variables
        temporal_results_bidding_zone = utils.convert_variables_recursively(temporal_results[bidding_zone])
        # Store the temporal results to a CSV file
        temporal_results_bidding_zone.to_csv(output_directory / "temporal" / "bidding_zones" / f"{bidding_zone}.csv")

        # Convert and store the IRES capacity
        ires_capacity_bidding_zone = utils.convert_variables_recursively(ires_capacity[bidding_zone])
        ires_capacity_bidding_zone.to_csv(output_directory / "capacity" / "ires" / f"{bidding_zone}.csv")

        # Convert and store the storage capacity
        storage_capacity_bidding_zone = utils.convert_variables_recursively(storage_capacity[bidding_zone])
        storage_capacity_bidding_zone.to_csv(output_directory / "capacity" / "storage" / f"{bidding_zone}.csv")

        # Convert and store the storage capacity
        hydropower_capacity[bidding_zone].to_csv(output_directory / "capacity" / "hydropower" / f"{bidding_zone}.csv")

    # Convert and store the electrolysis capacity if hydrogen production is included
    if include_hydrogen_production:
        electrolysis_capacity = utils.convert_variables_recursively(electrolysis_capacity)
        electrolysis_capacity.to_csv(output_directory / "capacity" / "electrolysis.csv")

    # Store the actual values per connection type for the temporal export
    for connection_type in ["hvac", "hvdc"]:
        status.update(f"Converting and storing the {connection_type.upper()} interconnection results")
        # Convert and store the temporal interconnection flows
        temporal_export_connection_type = utils.convert_variables_recursively(temporal_export[connection_type])
        temporal_export_connection_type.to_csv(output_directory / "temporal" / "interconnections" / f"{connection_type}.csv")
        # Convert and store the interconnection capacities
        interconnection_capacity_connection_type = utils.convert_variables_recursively(interconnection_capacity[connection_type])
        interconnection_capacity_connection_type.to_csv(output_directory / "capacity" / "interconnections" / f"{connection_type}.csv")

    # Add the storing duration to the dictionary
    storing_end = datetime.now()
    duration["storing"] = round((storing_end - storing_start).total_seconds())

    # Return with the duration dictionary
    return {"duration": duration}
