import os
from cbm3_python.simulation import projectsimulator
from cbm3_python.cbm3data import sit_helper
from cbm3_python.cbm3data import cbm3_results
from libcbm.test.cbm import case_generation


def get_unfccc_land_class_id_ref():
    """Returns a dictionary of the name (key), id (value) pairs used in the
    CBM-CFS3 model for UNFCCC land class.

    Returns:
        dict: a dictionary of UNFCCC land class names and ids
    """
    return {
        "UNFCCC_FL_R_FL": 0, "UNFCCC_CL_R_CL": 1, "UNFCCC_GL_R_GL": 2,
        "UNFCCC_WL_R_WL": 3, "UNFCCC_SL_R_SL": 4, "UNFCCC_OL_R_OL": 5,
        "UNFCCC_CL_R_FL": 6, "UNFCCC_GL_R_FL": 7, "UNFCCC_WL_R_FL": 8,
        "UNFCCC_SL_R_FL": 9, "UNFCCC_OL_R_FL": 10, "UNFCCC_FL_R_CL": 11,
        "UNFCCC_FL_R_GL": 12, "UNFCCC_FL_R_WL": 13, "UNFCCC_FL_R_SL": 14,
        "UNFCCC_FL_R_OL": 15, "UNFCCC_UFL": 16, "UNFCCC_UFL_R_CL": 17,
        "UNFCCC_UFL_R_GL": 18, "UNFCCC_UFL_R_WL": 19, "UNFCCC_UFL_R_SL": 20,
        "UNFCCC_UFL_R_OL": 21, "UNFCCC_UFL_R_FL": 22, "PEATLAND": 13}


def get_project_path(toolbox_path, name):
    """Returns a sensible default project path for running a CBM-CFS3 project
    in the CBM-CFS3 toolbox.

    Args:
        toolbox_path (str): path to the installation of the Operational-Scale
            CBM-CFS3 toolbox.
        name (str): the project name, which is used to form the subdirectory
            and project file name

    Returns:
        str: a path for the specified project
    """
    return os.path.join(toolbox_path, "Projects", name, "{}.mdb".format(name))


def get_results_path(project_path):
    """Returns a sensible default results database path based on the project
    database path.

    Args:
        name (str): the project name, which is used to form the subdirectory
            and project file name

    Returns:
        str: a path for the specified project
    """
    name = os.path.splitext(os.path.basename(project_path))[0]
    return os.path.join(
        os.path.dirname(project_path), "{}_results.mdb".format(name))


def get_config_path(toolbox_path, name):
    """Creates a sensible default path for saving the configuration file used
    to generate a CBM-CFS3 project

    Args:
        toolbox_path (str): path to the installation of the Operational-Scale
            CBM-CFS3 toolbox.
        name (str): the project name, which is used to form the subdirectory
            and project file name

    Returns:
        str: a path for the SIT configuration based on the specified args
    """
    cbm3_project_dir = os.path.dirname(get_project_path(toolbox_path, name))
    return os.path.join(cbm3_project_dir, "{}.json".format(name))


def import_cbm3_project(name, cases, age_interval, num_age_classes, n_steps,
                        toolbox_path, archive_index_db_path,
                        cbm3_project_path=None, sit_config_save_path=None):
    """Create a CBM-CFS3 project via the StandardImportToolPlugin tool

    This is a windows only function, since the Operational Scale toolbox is a
    windows only application.

    https://github.com/cat-cfs/StandardImportToolPlugin

    Args:
        name (str): project name
        cases (dict): test cases as generated by the test case generator.
            See: libcbm.test.casegeneration
        age_interval (int): the number of years between each merchantable
            volume.
        num_age_classes (int): The number of points in each merchantable
            volume curve.
        n_steps (int): The number of timesteps to simulate
        toolbox_path (str): Path to the installed Operational-Scale CBM-CFS3
            model.
        archive_index_db_path (str): path to a copy of a CBM-CFS3 archive
            index access database which stores simulation parameters.
        cbm3_project_path (str, optional): If specified a path at which the
            CBM3 project will be created. If unspecified, a default path is
            generated based on the project name and the "Projects" dir of the
            toolbox installation. Defaults to None.
        sit_config_save_path (str, optional): If specified a path at which the
            Standard Import tool config will be created. If unspecified, a
            default path is generated based on the project name and the
            "Projects" dir of the toolbox installation. Defaults to None.

    Raises:
        ValueError: An invalid test case was detected.

    Returns:
        str: The path to the generated CBM-CFS3 project.
    """

    local_dir = os.path.dirname(os.path.realpath(__file__))
    sit_plugin_path = sit_helper.load_standard_import_tool_plugin(
        os.path.join(local_dir, "StandardImportToolPlugin")
    )

    if not cbm3_project_path:
        cbm3_project_path = get_project_path(toolbox_path, name)
    if not sit_config_save_path:
        sit_config_save_path = get_config_path(toolbox_path, name)

    sit_config = sit_helper.SITConfig(
        imported_project_path=cbm3_project_path,
        initialize_mapping=True,
        archive_index_db_path=archive_index_db_path
    )
    sit_config.data_config(
        age_class_size=age_interval,
        num_age_classes=num_age_classes,
        classifiers=["admin", "eco", "identifier", "species"])
    sit_config.set_admin_eco_mapping("admin", "eco")
    sit_config.set_species_classifier("species")
    for c in cases:
        species = None
        is_afforestation = False
        if not c["afforestation_pre_type"] is None:
            species = c["afforestation_pre_type"]
            is_afforestation = True
        else:
            species = "Spruce"
            # "Spruce" does not actually matter here, since ultimately
            # species composition is decided in yields

        classifier_set = [
            c["admin_boundary"],
            c["eco_boundary"],
            case_generation.get_classifier_value_name(c["id"]),
            species]

        if is_afforestation:
            # in cbm3, afforestation requires a transition rule.
            first_event = c["events"][0]["disturbance_type"]
            if len(c["events"]) < 1 or first_event != "Afforestation":
                raise ValueError(
                    "specified afforestation configuration not supported")
            sit_config.add_transition_rule(
                classifier_set_source=classifier_set,
                classifier_set_target=classifier_set,
                disturbance_type="Afforestation", percent=100)

        unfccc_land_class = get_unfccc_land_class_id_ref()[
            c["unfccc_land_class"]]
        sit_config.add_inventory(
            classifier_set=classifier_set, area=c["area"], age=c["age"],
            unfccc_land_class=unfccc_land_class,
            delay=c["delay"], historic_disturbance=c["historical_disturbance"],
            last_pass_disturbance=c["last_pass_disturbance"])
        for component in c["components"]:
            sit_config.add_yield(
                classifier_set=classifier_set,
                leading_species_classifier_value=component["species"],
                values=[x[1] for x in component["age_volume_pairs"]])
        # not yet supporting disturbance rules here, meaning each event will
        # target only a single stand
        for event in c["events"]:
            sit_config.add_event(
                classifier_set=classifier_set,
                disturbance_type=event["disturbance_type"],
                time_step=event["time_step"],
                target=1,
                target_type="Area",
                sort="SORT_BY_SW_AGE")

    sit_config.add_event(
        classifier_set=["?", "?", "?", "?"],
        disturbance_type="Wildfire",
        time_step=n_steps+1,
        target=1,
        target_type="Area",
        sort="SORT_BY_SW_AGE")
    sit_config.import_project(
        sit_plugin_path, sit_config_save_path)
    return cbm3_project_path


def run_cbm3(archive_index_db_path, project_path, toolbox_path,
             cbm_exe_path, cbm3_results_db_path=None):
    """Simulate the specified CBM-CFS3 project, and return the path to the
    resulting simulation results database.

    This is a windows only function, since the Operational-Scale CBM-CFS3
    toolbox is a windows only application.

    Args:
        archive_index_db_path (str): path to a copy of a CBM-CFS3 archive
            index access database.
        project_path (str): path to a CBM-CFS3 project database to simulate.
        toolbox_path (str): Path to the installed Operational-Scale CBM-CFS3
            model.
        cbm_exe_path (str): directory containing the CBM-CFS3 model
            executables "cbm.exe" and "makelist.exe".
        cbm3_results_db_path ([type], optional): [description]. Defaults to
            None.

    Returns:
        str: The path to a CBM-CFS3 results database containing simulation
        results for the specified project.
    """
    if not cbm3_results_db_path:
        cbm3_results_db_path = get_results_path(project_path)
    projectsimulator.run(
        aidb_path=archive_index_db_path,
        project_path=project_path,
        toolbox_installation_dir=toolbox_path,
        cbm_exe_path=cbm_exe_path,
        results_database_path=cbm3_results_db_path)
    return cbm3_results_db_path


def get_cbm3_results(cbm3_results_db_path):
    """Loads and returns CBM pool, flux and state simulation results into
    pandas.DataFrame for analysis.

    Args:
        cbm3_results_db_path (str): path to a CBM-CFS3 results database.

    Returns:
        dict:
            "pools": a pandas.DataFrame containing CBM-CFS3 pool
                simulation results
            "flux": a pandas.DataFrame containing CBM-CFS3 flux
                simulation results
            "state": a pandas dataframe containing age, and landclass
                information.
    """
    cbm3_pool_result = cbm3_results.load_pool_indicators(
        cbm3_results_db_path, classifier_set_grouping=True)
    cbm3_flux_result = cbm3_results.load_flux_indicators(
        cbm3_results_db_path, classifier_set_grouping=True,
        disturbance_type_grouping=True)
    cbm3_age_indicators_result = cbm3_results.load_age_indicators(
        cbm3_results_db_path, classifier_set_grouping=True,
        land_class_grouping=True)
    return {
        "pools": cbm3_pool_result,
        "flux": cbm3_flux_result,
        "state": cbm3_age_indicators_result
        }
