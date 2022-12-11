import streamlit as st

import chart
import colors
import utils
import validate


def sankey_diagram(output_directory, resolution):
    """
    Show a Sankey diagram of the energy flows
    """
    assert validate.is_directory_path(output_directory)
    assert validate.is_resolution(resolution)

    st.title("➡️️ Sankey diagram")

    # Get temporal results for all countries
    all_temporal_results = utils.get_temporal_results(output_directory, resolution)
    config = utils.read_yaml(output_directory / "config.yaml")

    # Show a warning message if the run does not include Li-ion or hydrogen storage
    storage_technologies = config["technologies"]["storage"]
    if len(storage_technologies) != 2 or "lion" not in storage_technologies or "hydrogen" not in storage_technologies:
        st.warning("The Sankey diagram is only available for simulations that include Li-ion and hydrogen storage")
        return

    # Select the included countries
    st.sidebar.header("Options")
    country_codes = st.sidebar.multiselect("Country", config["country_codes"], format_func=lambda country_code: utils.get_country_property(country_code, "name"))

    # Show all countries if none are selected
    if len(country_codes) == 0:
        country_codes = config["country_codes"]

    temporal_results = 0
    for bidding_zone in utils.get_bidding_zones_for_countries(country_codes):
        temporal_results_bidding_zone = all_temporal_results[bidding_zone]

        temporal_results_bidding_zone["export_MW"] = 0
        temporal_results_bidding_zone["import_MW"] = 0
        for export_column in temporal_results_bidding_zone.filter(regex=("^net_export_[A-Z]{2}[0-9a-zA-Z]{2}_MW$")):
            temporal_results_bidding_zone["export_MW"] += temporal_results_bidding_zone[export_column].clip(lower=0)
            temporal_results_bidding_zone["import_MW"] += -temporal_results_bidding_zone[export_column].clip(upper=0)

        temporal_results_bidding_zone["in_MW"] = temporal_results_bidding_zone.production_total_MW + temporal_results_bidding_zone.import_MW
        temporal_results_bidding_zone["out_MW"] = temporal_results_bidding_zone.demand_MW + temporal_results_bidding_zone.export_MW

        temporal_results_bidding_zone["lion_in_MW"] = temporal_results_bidding_zone.net_storage_flow_lion_MW.clip(lower=0)
        temporal_results_bidding_zone["lion_out_MW"] = -temporal_results_bidding_zone.net_storage_flow_lion_MW.clip(upper=0)
        temporal_results_bidding_zone["hydrogen_in_MW"] = temporal_results_bidding_zone.net_storage_flow_hydrogen_MW.clip(lower=0)
        temporal_results_bidding_zone["hydrogen_out_MW"] = -temporal_results_bidding_zone.net_storage_flow_hydrogen_MW.clip(upper=0)

        temporal_results_bidding_zone["lion_in_hydrogen_out_MW"] = (temporal_results_bidding_zone.lion_in_MW > 0) & (temporal_results_bidding_zone.hydrogen_out_MW > 0)
        temporal_results_bidding_zone["hydrogen_in_lion_out_MW"] = (temporal_results_bidding_zone.hydrogen_in_MW > 0) & (temporal_results_bidding_zone.lion_out_MW > 0)
        temporal_results_bidding_zone["lion_from_hydrogen_MW"] = temporal_results_bidding_zone.lion_in_MW.clip(upper=temporal_results_bidding_zone.hydrogen_out_MW)
        temporal_results_bidding_zone["hydrogen_from_lion_MW"] = temporal_results_bidding_zone.hydrogen_in_MW.clip(upper=temporal_results_bidding_zone.lion_out_MW)

        temporal_results_bidding_zone["lion_from_in_MW"] = temporal_results_bidding_zone.lion_in_MW - temporal_results_bidding_zone.lion_from_hydrogen_MW
        temporal_results_bidding_zone["hydrogen_from_in_MW"] = temporal_results_bidding_zone.hydrogen_in_MW - temporal_results_bidding_zone.hydrogen_from_lion_MW
        temporal_results_bidding_zone["in_to_out_MW"] = temporal_results_bidding_zone.in_MW - temporal_results_bidding_zone.lion_from_in_MW - temporal_results_bidding_zone.hydrogen_from_in_MW - temporal_results_bidding_zone.curtailed_MW
        temporal_results_bidding_zone["lion_to_out_MW"] = temporal_results_bidding_zone.lion_out_MW - temporal_results_bidding_zone.hydrogen_from_lion_MW
        temporal_results_bidding_zone["hydrogen_to_out_MW"] = temporal_results_bidding_zone.hydrogen_out_MW - temporal_results_bidding_zone.lion_from_hydrogen_MW

        temporal_results += temporal_results_bidding_zone

    temporal_results = temporal_results.mean()
    temporal_results = temporal_results / temporal_results.demand_MW

    # Initialize Sankey object
    node_color = colors.get("gray", 500, format="rgba")
    link_color = colors.get("gray", 400, alpha=0.2, format="rgba")
    sankey = chart.Sankey(node_color=node_color, link_color=link_color, pad=15, valueformat=".2%")

    # Add all nodes
    sankey.add_node("Solar PV", x=0.01, y=0.2)
    sankey.add_node("Onshore wind", x=0.01, y=0.5)
    sankey.add_node("Offshore wind", x=0.01, y=0.74)
    sankey.add_node("Import", x=0.01, y=0.85)
    sankey.add_node("In", x=0.25, y=0.5)
    sankey.add_node("Curtailed", x=0.5, y=0.2)
    sankey.add_node("Li-ion", x=0.37, y=0.9)
    sankey.add_node("Hydrogen", x=0.58, y=0.82)
    sankey.add_node("Out", x=0.7, y=0.5)
    sankey.add_node("Demand", x=0.9, y=0.4)
    sankey.add_node("Export", x=0.9, y=0.7)

    # Add the links
    sankey.add_link("Solar PV", "In", temporal_results.production_pv_MW)
    sankey.add_link("Onshore wind", "In", temporal_results.production_onshore_MW)
    sankey.add_link("Offshore wind", "In", temporal_results.production_offshore_MW)
    sankey.add_link("Import", "In", temporal_results.import_MW)
    sankey.add_link("In", "Curtailed", temporal_results.curtailed_MW)
    sankey.add_link("In", "Li-ion", temporal_results.lion_from_in_MW)
    sankey.add_link("In", "Hydrogen", temporal_results.hydrogen_from_in_MW)
    sankey.add_link("In", "Out", temporal_results.in_to_out_MW)
    sankey.add_link("Li-ion", "Out", temporal_results.lion_to_out_MW)
    sankey.add_link("Li-ion", "Hydrogen", temporal_results.hydrogen_from_lion_MW)
    sankey.add_link("Hydrogen", "Out", temporal_results.hydrogen_to_out_MW)
    sankey.add_link("Hydrogen", "Li-ion", temporal_results.lion_from_hydrogen_MW)
    sankey.add_link("Out", "Demand", temporal_results.demand_MW)
    sankey.add_link("Out", "Export", temporal_results.export_MW)

    # Display the Sankey chart
    sankey.display()
