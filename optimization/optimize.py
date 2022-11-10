import math
from datetime import datetime, timedelta
import gurobipy as gp
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
    optimize_individual_interconnections = config["interconnections"]["optimize_individual_interconnections"] == True and config["interconnections"]["relative_capacity"] != 1

    """
    Step 1: Create the model and set the parameters
    """
    model = gp.Model(config["name"])
    model.setParam("OutputFlag", 0)

    # Set the user defined parameters
    model.setParam("Threads", config["optimization"]["thread_count"])
    model.setParam("Method", config["optimization"]["method"])

    # Disable crossover and set BarHomogeneous and Aggregate
    objective_scale_factor = 10 ** 6
    model.setParam("Crossover", 0)
    model.setParam("BarConvTol", config["optimization"]["barrier_convergence_tolerance"])
    model.setParam("BarHomogeneous", 1)  # Don't know what this does, but it speeds up some more complex models
    model.setParam("Aggregate", 0)  # Don't know what this does, but it speeds up some more complex models
    model.setParam("Presolve", 2)  # Use an aggressive presolver
    model.setParam("NumericFocus", 1)

    """
    Step 2: Initialize each bidding zone
    """
    # Create dictionaries to store all the data per bidding zone
    temporal_data = {}
    temporal_results = {}
    temporal_export = {}
    interconnection_capacity = {}
    production_capacity = {}
    storage_capacity = {}

    bidding_zones = utils.get_bidding_zones_for_countries(config["country_codes"])
    for index, bidding_zone in enumerate(bidding_zones):
        """
        Step 2A: Import the temporal data
        """
        country_flag = utils.get_country_property(utils.get_country_of_bidding_zone(bidding_zone), "flag")
        status.update(f"{country_flag} Importing data")

        filepath = utils.path("input", "scenarios", config["scenario"], "bidding_zones", f"{bidding_zone}.csv")
        start_year = config["climate_years"]["start"]
        end_year = config["climate_years"]["end"]
        # Get the temporal data and resample to the required resolution
        temporal_data[bidding_zone] = utils.read_temporal_data(filepath, start_year=start_year, end_year=end_year).resample(config["resolution"]).mean()
        # Remove the leap days from the dataset that could have been introduced by the resample method
        temporal_data[bidding_zone] = temporal_data[bidding_zone][~((temporal_data[bidding_zone].index.month == 2) & (temporal_data[bidding_zone].index.day == 29))]
        # Create an temporal_results DataFrame with the demand_MW column
        temporal_results[bidding_zone] = temporal_data[bidding_zone].loc[:, ["demand_MW"]]
        # Calculate the energy covered by the baseload
        temporal_results[bidding_zone]["baseload_MW"] = temporal_results[bidding_zone].demand_MW.mean() * config["technologies"]["relative_baseload"]

        # Create a DataFrame for the production capacities
        production_capacity[bidding_zone] = pd.DataFrame(columns=config["technologies"]["production"])

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

        """
        Step 2B: Define production capacity variables
        """
        temporal_results[bidding_zone]["production_total_MW"] = 0
        for production_technology in config["technologies"]["production"]:
            status.update(f"{country_flag} Adding {utils.format_technology(production_technology, capitalize=False)} production")

            # Create a capacity variable for each climate zone
            climate_zones = [re.match(f"{production_technology}_(.+)_cf", column).group(1) for column in temporal_data[bidding_zone].columns if column.startswith(f"{production_technology}_")]
            production_potential = utils.get_production_potential_in_climate_zone(bidding_zone, production_technology, config=config)
            current_capacity = utils.get_current_production_capacity_in_climate_zone(bidding_zone, production_technology, config=config)
            capacities = model.addVars(climate_zones, lb=current_capacity, ub=production_potential)

            # Add the capacities to the production_capacity DataFrame and calculate the temporal production for a specific technology
            temporal_production = 0
            for climate_zone, capacity in capacities.items():
                production_capacity[bidding_zone].loc[climate_zone, production_technology] = capacity
                # Apply is required, otherwise it will throw a ValueError if there are more than a few thousand rows (see https://stackoverflow.com/questions/64801287)
                temporal_production += temporal_data[bidding_zone][f"{production_technology}_{climate_zone}_cf"].apply(lambda cf: cf * capacity)
            temporal_results[bidding_zone][f"production_{production_technology}_MW"] = temporal_production
            temporal_results[bidding_zone]["production_total_MW"] += temporal_production

        """
        Step 2C: Define storage variables and constraints
        """
        # Create a DataFrame for the storage capacity in this bidding zone
        storage_capacity[bidding_zone] = pd.DataFrame(0, index=config["technologies"]["storage"], columns=["energy", "power"])

        # Create an object to save the storage capacity (energy & power) and add 2 columns to the results DataFrame
        temporal_results[bidding_zone]["net_storage_flow_total_MW"] = 0
        temporal_results[bidding_zone]["energy_stored_total_MWh"] = 0

        # Add the variables and constraints for all storage technologies
        for storage_technology in config["technologies"]["storage"]:
            status.update(f"{country_flag} Adding {utils.format_technology(storage_technology, capitalize=False)} storage")

            # Get the specific storage assumptions
            storage_assumptions = utils.get_technologies(technology_type="storage")[storage_technology]
            efficiency = storage_assumptions["roundtrip_efficiency"] ** 0.5
            timestep_hours = pd.Timedelta(config["resolution"]).total_seconds() / 3600

            # Get the storage energy potential
            storage_potential = utils.get_storage_potential_in_bidding_zone(bidding_zone, storage_technology, config=config)

            # Create a variable for the energy and power storage capacity
            if storage_potential == 0:
                storage_capacity[bidding_zone].loc[storage_technology, "energy"] = 0
                storage_capacity[bidding_zone].loc[storage_technology, "power"] = 0
            else:
                storage_capacity[bidding_zone].loc[storage_technology, "energy"] = model.addVar(ub=storage_potential)
                storage_capacity[bidding_zone].loc[storage_technology, "power"] = model.addVar()

            # Create the inflow and outflow variables
            if storage_potential == 0:
                inflow = {timestamp: 0 for timestamp in temporal_data[bidding_zone].index}
                outflow = {timestamp: 0 for timestamp in temporal_data[bidding_zone].index}
            else:
                inflow = model.addVars(temporal_data[bidding_zone].index)
                outflow = model.addVars(temporal_data[bidding_zone].index)

            # Add the net storage flow variables to the temporal_results DataFrame
            net_flow = pd.Series(data=[inflow_value - outflow_value for inflow_value, outflow_value in zip(inflow.values(), outflow.values())], index=temporal_results[bidding_zone].index)
            temporal_results[bidding_zone][f"net_storage_flow_{storage_technology}_MW"] = net_flow
            temporal_results[bidding_zone]["net_storage_flow_total_MW"] += net_flow

            # Create the energy stored column for this storage technology in the temporal_results DataFrame
            temporal_results[bidding_zone][f"energy_stored_{storage_technology}_MWh"] = None

            # Unpack the energy and power capacities for this storage technology
            energy_capacity = storage_capacity[bidding_zone].loc[storage_technology, "energy"]
            power_capacity = storage_capacity[bidding_zone].loc[storage_technology, "power"]

            if storage_potential == 0:
                temporal_energy_stored = pd.Series(0, index=temporal_data[bidding_zone].index)
            else:
                # Loop over all hours
                energy_stored_previous = None
                temporal_energy_stored_dict = {}
                for timestamp in temporal_data[bidding_zone].index:
                    # Create the state of charge variables
                    energy_stored_current = model.addVar()

                    # Add the SOC constraint with regard to the previous timestamp
                    if energy_stored_previous:
                        model.addConstr(energy_stored_current == energy_stored_previous + (inflow[timestamp] * efficiency - outflow[timestamp] / efficiency) * timestep_hours)

                    # Add the energy capacity constraints (can't be added when the flow variables are defined because it's a gurobipy.Var)
                    model.addConstr(energy_stored_current >= storage_assumptions["soc_min"] * energy_capacity)
                    model.addConstr(energy_stored_current <= storage_assumptions["soc_max"] * energy_capacity)

                    # Add the power capacity constraints (can't be added when the flow variables are defined because it's a gurobipy.Var)
                    model.addConstr(inflow[timestamp] <= power_capacity)
                    model.addConstr(outflow[timestamp] <= power_capacity)

                    # Add the current energy stored to temporal_energy_stored_dict
                    temporal_energy_stored_dict[timestamp] = energy_stored_current

                    # Update energy_stored_previous
                    energy_stored_previous = energy_stored_current

                # Convert the temporal_energy_stored_dict to a Series
                temporal_energy_stored = pd.Series(data=temporal_energy_stored_dict)

                # Ensure that the SOC of the first timestep equals the SOC of the last timestep
                model.addConstr(temporal_energy_stored.head(1).item() == temporal_energy_stored.tail(1).item())

            # Add the temporal energy stored to the temporal_results DataFrame
            temporal_results[bidding_zone][f"energy_stored_{storage_technology}_MWh"] = temporal_energy_stored
            temporal_results[bidding_zone]["energy_stored_total_MWh"] += temporal_energy_stored

        """
        Step 2D: Define the interconnection variables
        """
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
    Step 3: Define demand constraints
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
        temporal_results[bidding_zone].apply(lambda row: model.addConstr(row.baseload_MW + row.production_total_MW - row.net_storage_flow_total_MW - row.net_export_MW >= row.demand_MW), axis=1)

        # Calculate the curtailed energy per hour
        curtailed_MW = temporal_results[bidding_zone].baseload_MW + temporal_results[bidding_zone].production_total_MW - temporal_results[bidding_zone].demand_MW - temporal_results[bidding_zone].net_storage_flow_total_MW - temporal_results[bidding_zone].net_export_MW
        temporal_results[bidding_zone].insert(temporal_results[bidding_zone].columns.get_loc("production_total_MW"), "curtailed_MW", curtailed_MW)

    """
    Step 4: Define interconnection capacity constraint if the individual interconnections are optimized
    """
    if optimize_individual_interconnections:
        total_current_capacity = sum(interconnection_capacity[connection_type]["current"].sum() for connection_type in ["hvac", "hvdc"])
        total_extra_capacity = sum(interconnection_capacity[connection_type]["extra"].sum() for connection_type in ["hvac", "hvdc"])
        if total_current_capacity > 0:
            model.addConstr((1 + (total_extra_capacity / total_current_capacity)) == config["interconnections"]["relative_capacity"])

    """
    Step 5: Define the self-sufficiency constraints per country
    """
    if config["interconnections"]["min_self_sufficiency"] > 0:
        for country_code in config["country_codes"]:
            country_flag = utils.get_country_property(country_code, "flag")
            status.update(f"{country_flag} Adding self-sufficiency constraint")

            # Set the variables required to calculate the cumulative results in the country
            sum_demand = 0
            sum_baseload = 0
            sum_production = 0
            sum_curtailed = 0
            sum_storage_flow = 0

            # Loop over all bidding zones in the country
            for bidding_zone in utils.get_bidding_zones_for_countries([country_code]):
                # Calculate the total demand and non-curtailed production in this country
                sum_demand += temporal_results[bidding_zone].demand_MW.sum()
                # The Gurobi .quicksum method is significantly faster than Panda's .sum method
                sum_baseload += gp.quicksum(temporal_results[bidding_zone].baseload_MW)
                sum_production += gp.quicksum(temporal_results[bidding_zone].production_total_MW)
                sum_curtailed += gp.quicksum(temporal_results[bidding_zone].curtailed_MW)
                sum_storage_flow += gp.quicksum(temporal_results[bidding_zone].net_storage_flow_total_MW)

            # Add the self-sufficiency constraint if there is any demand in the country
            if sum_demand > 0:
                min_self_sufficiency = config["interconnections"]["min_self_sufficiency"]
                model.addConstr((sum_baseload + sum_production - sum_curtailed - sum_storage_flow) / sum_demand >= min_self_sufficiency)

    """
    Step 6: Define the storage costs constraint
    """
    if config.get("fixed_storage") is not None:
        status.update("Adding the storage costs constraint")

        # Calculate the storage costs
        temporal_net_demand = utils.merge_dataframes_on_column(temporal_results, "demand_MW") - utils.merge_dataframes_on_column(temporal_results, "baseload_MW")
        storage_costs = utils.calculate_lcoe(production_capacity, storage_capacity, temporal_net_demand, config=config, breakdown_level=1)["storage"]

        # Add a constraint so the storage costs are either smaller or larger than the fixed storage costs
        fixed_storage_costs = config["fixed_storage"]["costs"]
        if config["fixed_storage"]["direction"] == "gte":
            model.addConstr(storage_costs >= fixed_storage_costs)
        elif config["fixed_storage"]["direction"] == "lte":
            model.addConstr(storage_costs <= fixed_storage_costs)

    """
    Step 7: Set objective function
    """
    status.update("Setting the objective function")
    temporal_net_demand = utils.merge_dataframes_on_column(temporal_results, "demand_MW") - utils.merge_dataframes_on_column(temporal_results, "baseload_MW")
    firm_lcoe = utils.calculate_lcoe(production_capacity, storage_capacity, temporal_net_demand, config=config)
    model.setObjective(firm_lcoe * objective_scale_factor, gp.GRB.MINIMIZE)

    # Add the initializing duration to the dictionary
    initializing_end = datetime.now()
    duration["initializing"] = round((initializing_end - initializing_start).total_seconds())

    """
    Step 8: Solve model
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
            objective_value = model.cbGet(gp.GRB.Callback.BARRIER_PRIMOBJ) / objective_scale_factor
            barrier_convergence = model.cbGet(gp.GRB.Callback.BARRIER_PRIMOBJ) / model.cbGet(gp.GRB.Callback.BARRIER_DUALOBJ) - 1
            stat1.metric("Iteration (barrier)", f"{iteration:,}")
            stat2.metric("Objective", f"{objective_value:,.2f}€/MWh")
            stat3.metric("Convergence", f"{barrier_convergence:.2e}")
        if where == gp.GRB.Callback.SIMPLEX and model.cbGet(gp.GRB.Callback.SPX_ITRCNT) % 1000 == 0:
            iteration = model.cbGet(int(gp.GRB.Callback.SPX_ITRCNT))
            objective_value = model.cbGet(gp.GRB.Callback.SPX_OBJVAL) / objective_scale_factor
            infeasibility = model.cbGet(gp.GRB.Callback.SPX_PRIMINF)
            stat1.metric("Iteration (simplex)", f"{int(iteration):,}")
            stat2.metric("Objective", f"{objective_value:,.2f}€/MWh")
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
    Step 9: Check if the model could be solved
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
    Step 10: Store the results
    """
    storing_start = datetime.now()

    # Make a directory for each type of output
    for sub_directory in ["temporal_results", "temporal_export", "production_capacities", "storage_capacities", "interconnection_capacity"]:
        (output_directory / sub_directory).mkdir()

    # Store the actual values per bidding zone for the temporal results and capacities
    for bidding_zone in bidding_zones:
        country_flag = utils.get_country_property(utils.get_country_of_bidding_zone(bidding_zone), "flag")
        status.update(f"{country_flag} Converting and storing the results")
        # Convert the temporal results variables
        temporal_results_bidding_zone = utils.convert_variables_recursively(temporal_results[bidding_zone])

        # Store the temporal results to a CSV file
        temporal_results_bidding_zone.to_csv(output_directory / "temporal_results" / f"{bidding_zone}.csv")

        # Convert and store the production capacity
        production_capacity_bidding_zone = utils.convert_variables_recursively(production_capacity[bidding_zone])
        production_capacity_bidding_zone.to_csv(output_directory / "production_capacities" / f"{bidding_zone}.csv")

        # Convert and store the storage capacity
        storage_capacity_bidding_zone = utils.convert_variables_recursively(storage_capacity[bidding_zone])
        storage_capacity_bidding_zone.to_csv(output_directory / "storage_capacities" / f"{bidding_zone}.csv")

    # Store the actual values per connection type for the temporal export
    for connection_type in ["hvac", "hvdc"]:
        status.update(f"Converting and storing the {connection_type.upper()} interconnection results")
        # Convert and store the temporal interconnection flows
        temporal_export_connection_type = utils.convert_variables_recursively(temporal_export[connection_type])
        temporal_export_connection_type.to_csv(output_directory / "temporal_export" / f"{connection_type}.csv")
        # Convert and store the interconnection capacities
        interconnection_capacity_connection_type = utils.convert_variables_recursively(interconnection_capacity[connection_type])
        interconnection_capacity_connection_type.to_csv(output_directory / "interconnection_capacity" / f"{connection_type}.csv")

    # Add the storing duration to the dictionary
    storing_end = datetime.now()
    duration["storing"] = round((storing_end - storing_start).total_seconds())

    return {"duration": duration}
