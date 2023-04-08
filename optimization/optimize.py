import re
from datetime import datetime, timedelta

import gurobipy as gp
import numpy as np
import pandas as pd
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
    duration = pd.Series(dtype="float64")
    initializing_start = datetime.now()

    # Check if the interconnections should be optimized individually
    optimize_individual_interconnections = config["interconnections"]["optimize_individual_interconnections"] is True and config["interconnections"]["relative_capacity"] != 1

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
    temporal_demand_electricity = utils.read_temporal_data(demand_filepath, start_year=config["climate_years"]["start"], end_year=config["climate_years"]["end"]).resample(config["resolution"]).mean()
    temporal_demand_electricity = temporal_demand_electricity[~((temporal_demand_electricity.index.month == 2) & (temporal_demand_electricity.index.day == 29))]
    # Remove all market nodes that are not part of the optimization
    market_nodes = utils.get_market_nodes_for_countries(config["country_codes"])
    temporal_demand_electricity = temporal_demand_electricity[market_nodes]


    """
    Step 3: Initialize each market node
    """
    # Create the variables to store the various data per market node
    temporal_results = {}
    temporal_export = {}
    interconnection_capacity = {}
    ires_capacity = {}
    dispatchable_capacity = pd.DataFrame(index=market_nodes, columns=config["technologies"]["dispatchable"])
    dispatchable_generation_mean = pd.DataFrame(index=market_nodes, columns=config["technologies"]["dispatchable"])
    hydropower_capacity = {}
    storage_capacity = {}
    electrolysis_capacity = pd.DataFrame(index=market_nodes, columns=config["technologies"]["electrolysis"])  # The index is required for the case when no electrolysis technologies are defined

    for index, market_node in enumerate(market_nodes):
        """
        Step 3A: Import the temporal data
        """
        country_flag = utils.get_country_property(utils.get_country_of_market_node(market_node), "flag")
        status.update(f"{country_flag} Importing IRES data")

        # Get the temporal data and resample to the required resolution
        ires_filepath = utils.path("input", "scenarios", config["scenario"], "ires", f"{market_node}.csv")
        ires_capacity_factors = utils.read_temporal_data(ires_filepath, start_year=config["climate_years"]["start"], end_year=config["climate_years"]["end"]).resample(config["resolution"]).mean()
        # Remove the leap days from the dataset that could have been introduced by the resample method
        ires_capacity_factors = ires_capacity_factors[~((ires_capacity_factors.index.month == 2) & (ires_capacity_factors.index.day == 29))]
        # Create a temporal_results DataFrame with the demand_total_MW and demand_electricity_MW columns
        temporal_results[market_node] = pd.DataFrame(temporal_demand_electricity[market_node].rename("demand_total_MW"))
        temporal_results[market_node]["demand_electricity_MW"] = temporal_results[market_node].demand_total_MW

        """
        Step 3B: Define the electrolysis variables
        """
        for electrolysis_technology in config["technologies"]["electrolysis"]:
            status.update(f"{country_flag} Adding {utils.format_technology(electrolysis_technology)} electrolysis")

            # Create the variable for the electrolysis production capacity
            electrolysis_capacity_market_node = model.addVar()
            electrolysis_capacity.loc[market_node, electrolysis_technology] = electrolysis_capacity_market_node

            # Create the temporal electrolysis demand variables
            temporal_electrolysis_demand = model.addVars(temporal_demand_electricity.index)
            temporal_results[market_node][f"demand_{electrolysis_technology}_MW"] = pd.Series(temporal_electrolysis_demand)
            temporal_results[market_node]["demand_total_MW"] += pd.Series(temporal_electrolysis_demand)

            # Ensure that the temporal demand does not exceed the electrolysis capacity
            model.addConstrs(temporal_electrolysis_demand[timestamp] <= electrolysis_capacity_market_node for timestamp in temporal_demand_electricity.index)

        """
        Step 3C: Define IRES capacity variables
        """
        # Create an empty DataFrame for the IRES capacities
        ires_capacity[market_node] = pd.DataFrame(columns=config["technologies"]["ires"])

        temporal_results[market_node]["generation_ires_MW"] = 0
        for ires_technology in config["technologies"]["ires"]:
            status.update(f"{country_flag} Adding {utils.format_technology(ires_technology, capitalize=False)} generation")

            # Create a capacity variable for each IRES node
            ires_nodes = [re.match(f"{ires_technology}_(.+)_cf", column).group(1) for column in ires_capacity_factors.columns if column.startswith(f"{ires_technology}_")]
            ires_potential = utils.get_potential_per_ires_node(market_node, ires_technology, config=config)
            current_capacity = utils.get_current_capacity_per_ires_node(market_node, ires_technology, config=config)
            capacities = model.addVars(ires_nodes, lb=current_capacity, ub=ires_potential)

            # Add the capacities to the ires_capacity DataFrame and calculate the temporal generation for a specific technology
            temporal_ires_generation = 0
            for ires_node, capacity in capacities.items():
                ires_capacity[market_node].loc[ires_node, ires_technology] = capacity
                # Apply is required, otherwise it will throw a ValueError if there are more than a few thousand rows (see https://stackoverflow.com/questions/64801287)
                temporal_ires_generation += ires_capacity_factors[f"{ires_technology}_{ires_node}_cf"].apply(lambda cf: cf * capacity)
            temporal_results[market_node][f"generation_{ires_technology}_MW"] = temporal_ires_generation
            temporal_results[market_node]["generation_ires_MW"] += temporal_ires_generation

        """
        Step 3D: Define dispatchable variables
        """
        temporal_results[market_node]["generation_dispatchable_MW"] = 0

        for dispatchable_technology in config["technologies"]["dispatchable"]:
            status.update(f"{country_flag} Adding {utils.format_technology(dispatchable_technology, capitalize=False)} generation")

            # Create the variable for the dispatchable generation capacity
            dispatchable_capacity_market_node = model.addVar()
            dispatchable_capacity.loc[market_node, dispatchable_technology] = dispatchable_capacity_market_node

            # Create the temporal dispatchable generation variables
            temporal_dispatchable_generation = pd.Series(model.addVars(temporal_demand_electricity.index))
            temporal_results[market_node][f"generation_{dispatchable_technology}_MW"] = temporal_dispatchable_generation
            temporal_results[market_node]["generation_dispatchable_MW"] += temporal_dispatchable_generation

            # Add the mean generation of this technology
            dispatchable_generation_mean.loc[market_node, dispatchable_technology] = gp.quicksum(temporal_dispatchable_generation) / len(temporal_dispatchable_generation.index)

            # Ensure that the temporal generation does not exceed the dispatchable capacity
            model.addConstrs(temporal_dispatchable_generation[timestamp] <= dispatchable_capacity_market_node for timestamp in temporal_demand_electricity.index)

        """
        Step 3D: Define the hydropower variables and constraints
        """
        # Create a DataFrame for the hydropower capacity in this market node
        hydropower_capacity[market_node] = pd.DataFrame(0, index=config["technologies"]["hydropower"], columns=["turbine", "pump", "reservoir"])

        # Add the total net generation and total reservoir columns to the results DataFrame
        temporal_results[market_node]["generation_total_hydropower_MW"] = 0
        temporal_results[market_node]["spillage_total_hydropower_MW"] = 0
        temporal_results[market_node]["energy_stored_total_hydropower_MWh"] = 0

        for hydropower_technology in config["technologies"]["hydropower"]:
            status.update(f"{country_flag} Adding {utils.format_technology(hydropower_technology, capitalize=False)} hydropower")

            # Get the specific hydropower assumptions and calculate the interval length
            hydropower_assumptions = utils.get_technology(hydropower_technology)

            # Add the relevant capacity to the hydropower_capacity DataFrame, if the capacity is not defined, set the capacity to 0
            hydropower_capacity_current_technology = utils.read_csv(utils.path("input", "scenarios", config["scenario"], "hydropower", hydropower_technology, "capacity.csv"), index_col=0)
            default_hydropower_capacity = pd.Series(0, index=hydropower_capacity_current_technology.columns)
            installed_hydropower_capacity = hydropower_capacity_current_technology.transpose().get(market_node, default_hydropower_capacity)
            relative_hydropower_capacity = config["technologies"].get("relative_hydropower_capacity", 1)
            hydropower_capacity[market_node].loc[hydropower_technology] = relative_hydropower_capacity * installed_hydropower_capacity

            # Get the turbine, pump, and reservoir capacity
            turbine_capacity = hydropower_capacity[market_node].loc[hydropower_technology, "turbine"]
            pump_capacity = hydropower_capacity[market_node].loc[hydropower_technology, "pump"]
            reservoir_capacity = hydropower_capacity[market_node].loc[hydropower_technology, "reservoir"]

            # Skip this hydropower technology if it does not have any turbine capacity in this market node
            if turbine_capacity == 0:
                temporal_results[market_node][f"generation_{hydropower_technology}_hydropower_MW"] = 0
                temporal_results[market_node][f"energy_stored_{hydropower_technology}_hydropower_MWh"] = 0
                continue

            # Get the temporal hydropower data
            filepath = utils.path("input", "scenarios", config["scenario"], "hydropower", hydropower_technology, f"{market_node}.csv")
            temporal_hydropower_data = utils.read_temporal_data(filepath, start_year=config["climate_years"]["start"], end_year=config["climate_years"]["end"])
            # Calculate the interval length of the hydropower data
            hydropower_interval_length = (temporal_hydropower_data.index[1] - temporal_hydropower_data.index[0]).total_seconds() / 3600
            # Resample the hydropower data to the selected resolution
            temporal_hydropower_data = temporal_hydropower_data.resample(config["resolution"]).mean()
            # Remove the leap days from the dataset that could have been introduced by the resample method
            temporal_hydropower_data = temporal_hydropower_data[~((temporal_hydropower_data.index.month == 2) & (temporal_hydropower_data.index.day == 29))]
            # Find and add the rows that are missing in the previous results (the resample method does not add rows after the last timestamp and some weeks don't start on January 1st)
            for timestamp in temporal_results[market_node].index.difference(temporal_hydropower_data.index):
                temporal_hydropower_data.loc[timestamp] = pd.Series([], dtype="float64")  # Sets None to all columns in the new row
            # Sort the DataFrame on its index (the first days of January, when missing, are added to the end of the DataFrame)
            temporal_hydropower_data = temporal_hydropower_data.sort_index()

            # Calculate the average inflow in MW
            inflow_MW = temporal_hydropower_data["inflow_MWh"].ffill().bfill() / hydropower_interval_length

            # Set the net hydropower generation to the inflow if there is no reservoir capacity
            if reservoir_capacity == 0:
                temporal_results[market_node][f"generation_{hydropower_technology}_hydropower_MW"] = inflow_MW
                temporal_results[market_node]["generation_total_hydropower_MW"] += inflow_MW
                temporal_results[market_node][f"energy_stored_{hydropower_technology}_hydropower_MWh"] = 0
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
            temporal_results[market_node][f"generation_{hydropower_technology}_hydropower_MW"] = net_flow
            temporal_results[market_node]["generation_total_hydropower_MW"] += net_flow

            # Create the hydropower spillage variables and add them to the temporal_results DataFrame (probably only required for Portugal)
            spillage_MW = pd.Series(model.addVars(temporal_hydropower_data.index))
            temporal_results[market_node]["spillage_total_hydropower_MW"] += spillage_MW

            # Get the turbine and pump efficiency
            turbine_efficiency = hydropower_assumptions.get("turbine_efficiency", 0)
            pump_efficiency = hydropower_assumptions.get("pump_efficiency", 0)

            # Loop over all hours
            reservoir_previous = None
            temporal_reservoir_dict = {}
            for timestamp in temporal_demand_electricity.index:
                # Create the reservoir level variable
                current_reservoir_soc = temporal_hydropower_data.loc[timestamp, "reservoir_soc"]
                current_min_reservoir_soc = temporal_hydropower_data.loc[timestamp, "min_reservoir_soc"]
                current_max_reservoir_soc = temporal_hydropower_data.loc[timestamp, "max_reservoir_soc"]
                if np.isnan(current_reservoir_soc):
                    min_reservoir_soc = 0 if np.isnan(current_min_reservoir_soc) else current_min_reservoir_soc
                    max_reservoir_soc = 1 if np.isnan(current_max_reservoir_soc) else current_max_reservoir_soc
                    reservoir_current = model.addVar(lb=min_reservoir_soc, ub=max_reservoir_soc) * reservoir_capacity
                else:
                    # The min-max transformation has to be transformed since Norway has a lower current_reservoir_soc than current_min_reservoir_soc in 2011
                    reservoir_current = min(max(current_reservoir_soc, current_min_reservoir_soc), current_max_reservoir_soc) * reservoir_capacity

                # Add the reservoir level constraint with regard to the previous timestamp
                if reservoir_previous:
                    model.addConstr(reservoir_current == reservoir_previous + (inflow_MW[timestamp] - spillage_MW[timestamp] - turbine_flow[timestamp] / turbine_efficiency + pump_flow[timestamp] * pump_efficiency) * interval_length)

                # Add the current reservoir level to temporal_reservoir_dict
                temporal_reservoir_dict[timestamp] = reservoir_current

                # Update reservoir_previous
                reservoir_previous = reservoir_current

            # Add the temporal reservoir levels to the temporal_results DataFrame
            temporal_reservoir = pd.Series(temporal_reservoir_dict)
            temporal_results[market_node][f"energy_stored_{hydropower_technology}_hydropower_MWh"] = temporal_reservoir
            temporal_results[market_node]["energy_stored_total_hydropower_MWh"] += temporal_reservoir

        """
        Step 3E: Define storage variables and constraints
        """
        # Create a DataFrame for the storage capacity in this market node
        storage_capacity[market_node] = pd.DataFrame(0, index=config["technologies"]["storage"], columns=["energy", "power"])

        # Add the total storage flow and total stored energy columns to the results DataFrame
        temporal_results[market_node]["net_storage_flow_total_MW"] = 0
        temporal_results[market_node]["energy_stored_total_MWh"] = 0

        # Add the variables and constraints for all storage technologies
        for storage_technology in config["technologies"]["storage"]:
            status.update(f"{country_flag} Adding {utils.format_technology(storage_technology, capitalize=False)} storage")

            # Get the specific storage assumptions
            storage_assumptions = utils.get_technology(storage_technology)
            efficiency = storage_assumptions["roundtrip_efficiency"] ** 0.5

            # Create a variable for the energy and power storage capacity
            storage_capacity[market_node].loc[storage_technology, "energy"] = model.addVar()
            storage_capacity[market_node].loc[storage_technology, "power"] = model.addVar()

            # Create the inflow and outflow variables
            inflow = pd.Series(model.addVars(temporal_demand_electricity.index))
            outflow = pd.Series(model.addVars(temporal_demand_electricity.index))

            # Add the net storage flow variables to the temporal_results DataFrame
            net_flow = inflow - outflow
            temporal_results[market_node][f"net_storage_flow_{storage_technology}_MW"] = net_flow
            temporal_results[market_node]["net_storage_flow_total_MW"] += net_flow

            # Unpack the energy and power capacities for this storage technology
            energy_capacity = storage_capacity[market_node].loc[storage_technology, "energy"]
            power_capacity = storage_capacity[market_node].loc[storage_technology, "power"]

            # Create a variable for each hour for the amount of stored energy
            temporal_energy_stored = pd.Series(model.addVars(temporal_demand_electricity.index))

            # Set the previous energy level to the last energy level
            energy_stored_previous = temporal_energy_stored.tail(1).item()

            # Loop over all hours
            for timestamp in temporal_demand_electricity.index:
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
            temporal_results[market_node][f"energy_stored_{storage_technology}_MWh"] = temporal_energy_stored
            temporal_results[market_node]["energy_stored_total_MWh"] += temporal_energy_stored

        """
        Step 3F: Define the interconnection variables
        """
        # Create empty DataFrames for the interconnections, if they don't exist yet
        if not len(temporal_export):
            temporal_export_columns = pd.MultiIndex.from_tuples([], names=["from", "to"])
            temporal_export["hvac"] = pd.DataFrame(index=temporal_results[market_node].index, columns=temporal_export_columns)
            temporal_export["hvdc"] = pd.DataFrame(index=temporal_results[market_node].index, columns=temporal_export_columns)

        # Create empty DataFrames for the extra interconnection capacity, if they don't exist yet
        if not len(interconnection_capacity):
            interconnection_capacity_index = pd.MultiIndex.from_arrays([[], []], names=("from", "to"))
            interconnection_capacity["hvac"] = pd.DataFrame(index=interconnection_capacity_index, columns=["current", "extra"])
            interconnection_capacity["hvdc"] = pd.DataFrame(index=interconnection_capacity_index, columns=["current", "extra"])

        for connection_type in ["hvac", "hvdc"]:
            status.update(f"{country_flag} Adding {connection_type.upper()} interconnections")
            # Get the export limits
            temporal_export_limits = utils.get_export_limits(market_node, connection_type=connection_type, index=temporal_results[market_node].index, config=config)

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
    for market_node in market_nodes:
        country_flag = utils.get_country_property(utils.get_country_of_market_node(market_node), "flag")
        status.update(f"{country_flag} Adding demand constraints")

        # Add a column for the total temporal export
        temporal_results[market_node]["net_export_MW"] = 0

        # Add a column for the temporal export to each country
        for interconnection_type in temporal_export:
            relevant_temporal_export = [interconnection_market_nodes for interconnection_market_nodes in temporal_export[interconnection_type] if market_node in interconnection_market_nodes]
            for market_node1, market_node2 in relevant_temporal_export:
                # Calculate the export flow
                direction = 1 if market_node1 == market_node else -config["interconnections"]["efficiency"][interconnection_type]
                export_flow = direction * temporal_export[interconnection_type][market_node1, market_node2]

                # Add the export flow to the interconnection type dictionary
                temporal_results[market_node]["net_export_MW"] += export_flow

                # Add the export flow to the relevant market node column
                other_market_node = market_node1 if market_node2 == market_node else market_node2
                column_name = f"net_export_{other_market_node}_MW"
                if column_name not in temporal_results:
                    temporal_results[market_node][column_name] = 0
                temporal_results[market_node][column_name] += export_flow

        # Add the demand constraint
        temporal_results[market_node].apply(lambda row: model.addConstr(row.generation_ires_MW + row.generation_dispatchable_MW + row.generation_total_hydropower_MW - row.net_storage_flow_total_MW - row.net_export_MW >= row.demand_total_MW), axis=1)

        # Calculate the curtailed energy per hour
        curtailed_MW = temporal_results[market_node].generation_ires_MW + temporal_results[market_node].generation_dispatchable_MW + temporal_results[market_node].generation_total_hydropower_MW - temporal_results[market_node].demand_total_MW - temporal_results[market_node].net_storage_flow_total_MW - temporal_results[market_node].net_export_MW
        temporal_results[market_node].insert(temporal_results[market_node].columns.get_loc("generation_ires_MW"), "curtailed_MW", curtailed_MW)

    """
    Step 5: Define the hydrogen constraint
    """
    # Create the hydrogen constraint per year
    for year in range(config["climate_years"]["start"], config["climate_years"]["end"] + 1):
        status.update(f"Adding hydrogen constraint for {year}")

        annual_hydrogen_demand = 0
        annual_hydrogen_production = 0

        for market_node in market_nodes:
            # Calculate the summed results of this market node for this year
            summed_results_year = temporal_results[market_node][temporal_results[market_node].index.year == year].sum() * interval_length
            annual_hydrogen_demand += config["relative_hydrogen_demand"] * summed_results_year.demand_electricity_MW

            # Add the hydrogen production to the total per production technology
            for electrolysis_technology in config["technologies"]["electrolysis"]:
                electrolyzer_efficiency = utils.get_technology(electrolysis_technology)["efficiency"]
                annual_hydrogen_production += electrolyzer_efficiency * summed_results_year[f"demand_{electrolysis_technology}_MW"]

        # Ensure that enough hydrogen is produced in the year
        model.addConstr(annual_hydrogen_production == annual_hydrogen_demand)

    """
    Step 6: Define interconnection capacity constraint if the individual interconnections are optimized
    """
    if optimize_individual_interconnections:
        total_current_capacity = sum(interconnection_capacity[connection_type]["current"].sum() for connection_type in ["hvac", "hvdc"])
        total_extra_capacity = sum(interconnection_capacity[connection_type]["extra"].sum() for connection_type in ["hvac", "hvdc"])
        if total_current_capacity > 0:
            model.addConstr((1 + (total_extra_capacity / total_current_capacity)) == config["interconnections"]["relative_capacity"])

    """
    Step 8: Define the self-sufficiency constraints per country
    """
    for country_code in config["country_codes"]:
        country_flag = utils.get_country_property(country_code, "flag")
        status.update(f"{country_flag} Adding self-sufficiency constraint")

        # Set the variables required to calculate the cumulative results in the country
        sum_demand_total = 0
        sum_ires_generation = 0
        sum_dispatchable_generation = 0
        sum_hydropower_generation = 0
        sum_curtailed = 0
        sum_storage_flow = 0
        sum_hydrogen_demand = 0
        sum_hydrogen_production = 0

        # Loop over all market nodes in the country
        for market_node in utils.get_market_nodes_for_countries([country_code]):
            # Calculate the total demand and non-curtailed generation in this country
            # The Gurobi .quicksum method is significantly faster than Panda's .sum method
            sum_demand_total += gp.quicksum(temporal_results[market_node].demand_total_MW)
            sum_ires_generation += gp.quicksum(temporal_results[market_node].generation_ires_MW)
            sum_dispatchable_generation += gp.quicksum(temporal_results[market_node].generation_dispatchable_MW)
            sum_hydropower_generation += gp.quicksum(temporal_results[market_node].generation_total_hydropower_MW)
            sum_curtailed += gp.quicksum(temporal_results[market_node].curtailed_MW)
            sum_storage_flow += gp.quicksum(temporal_results[market_node].net_storage_flow_total_MW)

            # Calculate the total hydrogen production
            sum_hydrogen_demand += config["relative_hydrogen_demand"] * temporal_demand_electricity[market_node].sum()

            for electrolysis_technology in config["technologies"]["electrolysis"]:
                electrolyzer_efficiency = utils.get_technology(electrolysis_technology)["efficiency"]
                sum_hydrogen_production += gp.quicksum(temporal_results[market_node][f"demand_{electrolysis_technology}_MW"]) * electrolyzer_efficiency

        # Add the self-sufficiency constraints
        electricity_production = sum_ires_generation + sum_dispatchable_generation + sum_hydropower_generation - sum_curtailed - sum_storage_flow
        model.addConstr(electricity_production >= config["self_sufficiency"]["min_electricity"] * sum_demand_total)
        model.addConstr(electricity_production <= config["self_sufficiency"]["max_electricity"] * sum_demand_total)

        # Add the hydrogen constraint to ensure that the temporal hydrogen production equals the total hydrogen demand
        model.addConstr(sum_hydrogen_production >= config["self_sufficiency"]["min_hydrogen"] * sum_hydrogen_demand)
        model.addConstr(sum_hydrogen_production <= config["self_sufficiency"]["max_hydrogen"] * sum_hydrogen_demand)

    """
    Step 9: Create a DataFrame with the mean temporal data
    """
    # Create a DataFrame for the mean temporal data
    relevant_columns = utils.find_common_columns(temporal_results)
    mean_temporal_data = pd.DataFrame(columns=relevant_columns)

    for market_node in market_nodes:
        # Add the mean temporal results to the DataFrame (can't use .mean as some columns include Gurobi variables)
        mean_temporal_data.loc[market_node] = temporal_results[market_node][relevant_columns].sum() / len(temporal_results[market_node].index)

    """
    Step 10: Define the storage costs constraint
    """
    if config.get("fixed_storage") is not None:
        status.update("Adding the storage costs constraint")

        # Calculate the storage costs
        annual_storage_costs = utils.calculate_lcoe(ires_capacity, dispatchable_capacity, storage_capacity, hydropower_capacity, mean_temporal_data=mean_temporal_data, config=config, breakdown_level=1, annual_costs=True)["storage"]

        # Add a constraint so the storage costs are either smaller or larger than the fixed storage costs
        fixed_annual_storage_costs = config["fixed_storage"]["annual_costs"]
        if config["fixed_storage"]["direction"] == "gte":
            model.addConstr(annual_storage_costs >= fixed_annual_storage_costs)
        elif config["fixed_storage"]["direction"] == "lte":
            model.addConstr(annual_storage_costs <= fixed_annual_storage_costs)

    """
    Step 11: Set objective function
    """
    status.update("Setting the objective function")

    # Calculate the annual electricity costs
    annual_electricity_costs = utils.calculate_lcoe(ires_capacity, dispatchable_capacity, storage_capacity, hydropower_capacity, mean_temporal_data=mean_temporal_data, config=config, annual_costs=True)

    # Calculate the total spillage and give it an artificial cost (this is required because otherwise some curtailment might be accounted as spillage)
    total_spillage_hydropower_MWh = utils.merge_dataframes_on_column(temporal_results, "spillage_total_hydropower_MW").sum().sum() * interval_length
    artificial_spillage_cost_factor = 100
    total_spillage_costs = total_spillage_hydropower_MWh * artificial_spillage_cost_factor

    # Calculate the annual electrolyzer costs (don't include electricity costs as this is already included in the electricity costs calculation above)
    annual_electrolyzer_costs = utils.calculate_lcoh(electrolysis_capacity, None, None, config=config, breakdown_level=1, annual_costs=True).electrolyzer

    # Set the objective to the annual system costs
    annualized_system_costs = annual_electricity_costs + annual_electrolyzer_costs + total_spillage_costs
    model.setObjective(annualized_system_costs, gp.GRB.MINIMIZE)

    # Add the initializing duration to the dictionary
    initializing_end = datetime.now()
    duration["initializing"] = (initializing_end - initializing_start).total_seconds()

    """
    Step 12: Solve model
    """
    # Set the status message and create
    status.update("Optimizing")
    optimizing_start = datetime.now()

    # Initialize the 'model' subdirectory
    (output_directory / "model").mkdir()

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

            # Add the log message line to log.txt
            utils.write_text(output_directory / "model" / "log.txt", log_message, mode="a", exist_ok=True)

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
    if config["optimization"]["store_model"]:
        model.write(f"{output_directory}/model/model.lp")
        model.write(f"{output_directory}/model/parameters.prm")

    # Store the quality attributes
    quality = {}
    for column_name, appendix in [("value", ""), ("sum", "Sum"), ("index", "Index")]:
        quality[column_name] = {}
        for quality_attribute in ["BoundVio", "ConstrVio", "ConstrResidual", "DualVio", "DualResidual", "ComplVio"]:
            try:
                quality[column_name][quality_attribute] = model.getAttr(f"{quality_attribute}{appendix}")
            except AttributeError:
                quality[column_name][quality_attribute] = None
    pd.DataFrame(quality).to_csv(output_directory / "model" / "quality.csv")

    # Add the optimizing duration to the dictionary
    optimizing_end = datetime.now()
    duration["optimizing"] = (optimizing_end - optimizing_start).total_seconds()

    """
    Step 13: Check if the model could be solved
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
        return error_message

    """
    Step 14: Store the results
    """
    storing_start = datetime.now()

    # Make the temporal subdirectories
    (output_directory / "temporal").mkdir()
    for sub_directory in ["market_nodes", "interconnections"]:
        (output_directory / "temporal" / sub_directory).mkdir()

    # Make the capacity subdirectories
    (output_directory / "capacity").mkdir()
    for sub_directory in ["ires", "storage", "hydropower", "interconnections"]:
        (output_directory / "capacity" / sub_directory).mkdir()

    # Store the actual values per market node for the temporal results and capacities
    for market_node in market_nodes:
        country_flag = utils.get_country_property(utils.get_country_of_market_node(market_node), "flag")
        status.update(f"{country_flag} Converting and storing the results")

        # Convert the temporal results variables
        temporal_results_market_node = utils.convert_variables_recursively(temporal_results[market_node])
        # Store the temporal results to a CSV file
        temporal_results_market_node.to_csv(output_directory / "temporal" / "market_nodes" / f"{market_node}.csv")

        # Convert and store the IRES capacity
        ires_capacity_market_node = utils.convert_variables_recursively(ires_capacity[market_node])
        ires_capacity_market_node.to_csv(output_directory / "capacity" / "ires" / f"{market_node}.csv")

        # Convert and store the storage capacity
        storage_capacity_market_node = utils.convert_variables_recursively(storage_capacity[market_node])
        storage_capacity_market_node.to_csv(output_directory / "capacity" / "storage" / f"{market_node}.csv")

        # Convert and store the storage capacity
        hydropower_capacity[market_node].to_csv(output_directory / "capacity" / "hydropower" / f"{market_node}.csv")

    # Store the mean temporal data
    mean_temporal_data = utils.convert_variables_recursively(mean_temporal_data)
    mean_temporal_data.to_csv(output_directory / "temporal" / "market_nodes" / "mean.csv")

    # Convert and store the dispatchable capacity
    dispatchable_capacity = utils.convert_variables_recursively(dispatchable_capacity)
    dispatchable_capacity.to_csv(output_directory / "capacity" / "dispatchable.csv")

    # Convert and store the electrolysis capacity
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
    duration["storing"] = (storing_end - storing_start).total_seconds()

    # Store the duration after the optimization
    duration.to_csv(output_directory / "model" / "duration.csv")
