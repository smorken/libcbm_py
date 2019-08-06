import numpy as np
import pandas as pd
import json
import os


class CBM:
    def __init__(self, dll, config):
        """Creates a new instance of the CBM model with the specified
        LibCBM wrapper instance. The wrapper instance is initialized
        with model parameters and configuration.

        Arguments:
            dll {LibCBMWrapper} -- an instance of the LibCBMWrapper.
        """
        self.dll = dll
        self.config = config

        config_string = json.dumps(config)
        dll.InitializeCBM(config_string)

        # create an index for lookup of classifiers
        classifier_id_lookup = {x["id"]: x for x in config["classifiers"]}
        self.classifier_lookup = {}
        for cv in config["classifier_values"]:
            classifier_id = cv["classifier_id"]
            classifier_name = classifier_id_lookup[classifier_id]["name"]
            if classifier_name in self.classifier_lookup:
                self.classifier_lookup[classifier_name][cv["value"]] = cv
            else:
                self.classifier_lookup[classifier_name] = {cv["value"]: cv}

        self.opNames = [
            "growth",
            "snag_turnover",
            "biomass_turnover",
            "dom_decay",
            "slow_decay",
            "slow_mixing",
            "disturbance"
            ]

        self.opProcesses = {
            "growth": 1,
            "snag_turnover": 1,
            "biomass_turnover": 1,
            "dom_decay": 2,
            "slow_decay": 2,
            "slow_mixing": 2,
            "disturbance": 3
        }

    def get_classifier_value_id(self, classifier_name, classifier_value_name):
        """Get the classifier value id associated with the classifier_name,
        classifier_value_name pair

        Arguments:
            classifier {str} -- name of the classifier
            classifier_value {str} -- name of the classifier value

        Returns:
            int -- identifier for the classifier/classifier value
        """
        c = self.classifier_lookup[classifier_name]
        cv = c[classifier_value_name]
        return cv["id"]

    def spinup(self, inventory, variables, parameters, debug=False):
        """Run the CBM-CFS3 spinup function on an array of stands,
        initializing the specified variables.

        See libcbm.model.cbm_variables for creating this function's
        parameters.

        Arguments:
            inventory {object} -- Data comprised of classifier sets
                and cbm inventory data. Will not be modified by this function.
            variables {object} -- spinup working variables
            parameters {object} -- spinup parameters

        Keyword Arguments:
            debug {bool} -- if true this function will return a pandas
                dataframe of selected spinup state variables.
                (default: {False})

        Returns:
            pandas.DataFrame or None -- returns a debug dataframe if parameter
                debug is set to true, and None otherwise.
        """
        variables.pools[:, 0] = 1.0
        n_stands = variables.pools.shape[0]

        ops = {x: self.dll.AllocateOp(n_stands) for x in self.opNames}

        self.dll.GetTurnoverOps(ops["snag_turnover"], ops["biomass_turnover"],
                                inventory.spatial_unit)

        self.dll.GetDecayOps(
            ops["dom_decay"], ops["slow_decay"], ops["slow_mixing"],
            inventory.spatial_unit, True, parameters.mean_annual_temp)

        opSchedule = [
            "growth",
            "snag_turnover",
            "biomass_turnover",
            "growth",
            "dom_decay",
            "slow_decay",
            "slow_mixing",
            "disturbance"
            ]
        debug_output = None
        if(debug):
            debug_output = pd.DataFrame()
        iteration = 0

        while (True):

            n_finished = self.dll.AdvanceSpinupState(
                inventory.spatial_unit, parameters.return_interval,
                parameters.min_rotations, parameters.max_rotations,
                inventory.age, inventory.delay, variables.slowPools,
                inventory.historic_disturbance_type,
                inventory.last_pass_disturbance_type,
                inventory.afforestation_pre_type_id, variables.spinup_state,
                variables.disturbance_types, variables.rotation,
                variables.step, variables.lastRotationSlowC,
                variables.enabled)
            if n_finished == n_stands:
                break

            self.dll.GetMerchVolumeGrowthOps(
                ops["growth"], inventory.classifiers.to_numpy(),
                variables.pools, variables.age, inventory.spatial_unit,
                None, None, None, variables.growth_enabled)

            self.dll.GetDisturbanceOps(
                ops["disturbance"], inventory.spatial_unit,
                variables.disturbance_types)

            self.dll.ComputePools(
                [ops[x] for x in opSchedule], variables.pools,
                variables.enabled)

            self.dll.EndSpinupStep(
                variables.spinup_state, variables.pools,
                variables.disturbance_types, variables.age,
                variables.slowPools, variables.growth_enabled)

            if(debug):
                debug_output = debug_output.append(pd.DataFrame(data={
                    "index": list(range(n_stands)),
                    "iteration": iteration,
                    "age": variables.age,
                    "slow_pools": variables.slowPools,
                    "spinup_state": variables.spinup_state,
                    "rotation": variables.rotation,
                    "last_rotation_c": variables.lastRotationSlowC,
                    "step": variables.step,
                    "disturbance_type": variables.disturbance_types
                    }))

            iteration = iteration + 1

        for x in self.opNames:
            self.dll.FreeOp(ops[x])
        return debug_output

    def init(self, inventory, variables):
        """Set the initial state of CBM variables after spinup and prior
        to starting CBM simulation

        See libcbm.model.cbm_variables for creating this function's
        parameters.

        Arguments:
            inventory {object} -- Read-only data comprised of classifier sets
                and cbm inventory data
            variables {object} -- simulation variables for:
                - pool variables
                - flux variables
                - state variables
        """
        self.dll.InitializeLandState(
            inventory.last_pass_disturbance_type, inventory.delay,
            inventory.age, inventory.spatial_unit,
            inventory.afforestation_pre_type_id, variables.pools,
            variables.state.last_disturbance_type,
            variables.state.time_since_last_disturbance,
            variables.state.time_since_land_class_change,
            variables.state.growth_enabled, variables.state.enabled,
            variables.state.land_class, variables.state.age)

    def step(self, inventory, variables, parameters):
        """Advances the specified CBM variables through one time step of CBM
        simulation.

        See libcbm.model.cbm_variables for creating this function's
        parameters.

        Arguments:
            inventory {object} -- Data comprised of classifier sets
                and cbm inventory data.  Inventory data will not be modified
                by this function, but classifier sets may be modified if
                transition rules are used.
            variables {object} -- simulation variables altered by this
                function. Comprised of:
                - pool variables
                - flux variables
                - state variables
            parameters {object} -- read-only parameters used in a CBM timestep:
                - disturbance types
                - mean annual temperature
                - transitions
        """

        variables.pools[:, 0] = 1.0
        variables.flux *= 0.0
        n_stands = variables.pools.shape[0]

        ops = {x: self.dll.AllocateOp(n_stands) for x in self.opNames}

        annual_process_opSchedule = [
            "growth",
            "snag_turnover",
            "biomass_turnover",
            "growth",
            "dom_decay",
            "slow_decay",
            "slow_mixing"
            ]

        self.dll.AdvanceStandState(
            inventory.classifiers.to_numpy(), inventory.spatial_unit,
            parameters.disturbance_type, parameters.transition_rule_id,
            variables.state.last_disturbance_type,
            variables.state.time_since_last_disturbance,
            variables.state.time_since_land_class_change,
            variables.state.growth_enabled, variables.state.enabled,
            variables.state.land_class, variables.state.regeneration_delay,
            variables.state.age)

        self.dll.GetDisturbanceOps(
            ops["disturbance"], inventory.spatial_unit,
            parameters.disturbance_type)

        self.dll.ComputeFlux(
            [ops["disturbance"]], [self.opProcesses["disturbance"]],
            variables.pools, variables.flux, enabled=None)

        # enabled = none on line above is due to a possible bug in CBM3. This
        # is very much an edge case:
        # stands can be disturbed despite having all other C-dynamics processes
        # disabled (which happens in peatland)

        self.dll.GetMerchVolumeGrowthOps(
            ops["growth"], inventory.classifiers.to_numpy(), inventory.pools,
            variables.state.age, inventory.spatial_unit,
            variables.state.last_disturbance_type,
            variables.state.time_since_last_disturbance,
            variables.state.growth_multiplier, variables.state.growth_enabled)

        self.dll.GetTurnoverOps(
            ops["snag_turnover"], ops["biomass_turnover"],
            inventory.spatial_unit)

        self.dll.GetDecayOps(
            ops["dom_decay"], ops["slow_decay"], ops["slow_mixing"],
            inventory.spatial_unit, parameters.mean_annual_temp)

        self.dll.ComputeFlux(
            [ops[x] for x in annual_process_opSchedule],
            [self.opProcesses[x] for x in annual_process_opSchedule],
            variables.pools, variables.flux, variables.state.enabled)

        self.dll.EndStep(
            variables.state.age, variables.state.regeneration_delay,
            variables.state.growth_enabled)

        for x in self.opNames:
            self.dll.FreeOp(ops[x])
