import ctypes
import logging
import sqlite3
import os
import numpy as np
import pandas as pd
from types import SimpleNamespace
from libcbm.wrapper.libcbm_matrix import LibCBM_Matrix
from libcbm.wrapper.libcbm_matrix import LibCBM_Matrix_Int
from libcbm.wrapper.libcbm_error import LibCBM_Error
from libcbm.wrapper.libcbm_ctypes import LibCBM_ctypes


def unpack_ndarrays(variables):
    """Convert and return a set of variables as a types.SimpleNamespace whose
    members are only ndarray.
    Supports 2 cases:
        1: the specified variables are already stored in a SimpleNamespace
        whose properties are one of pd.Series,pd.DataFrame,or np.ndarray.
        For each property in the namespace, convert to an ndarray if
        necessary.
        2: the specified variables are the columns of a pandas.DataFrame.
        Return a reference to each column's underlying numpy.ndarray storage

    Arguments:
        variables {SimpleNamespace or pd.DataFrame} -- The set of variables to
        unpack.

    Raises:
        ValueError: the type of the specified argument was not supported

    Returns:
        SimpleNamespace -- a SimpleNamespace whose properties are ndarray.
    """
    properties = {}
    if isinstance(variables, SimpleNamespace):
        for k, v in variables.__dict__.items():
            properties[k] = get_ndarray(v)
    elif isinstance(variables, pd.DataFrame):
        for c in variables:
            properties[c] = get_ndarray(variables[c])
    else:
        raise ValueError("Unsupported type")
    return SimpleNamespace(**properties)


def get_ndarray(a):
    """Helper method to deal with numpy arrays stored in pandas objects.
    Returns specified value if it is already an np.ndarray instance, and
    otherwise gets a reference to the underlying numpy.ndarray storage
    from a pandas.DataFrame or pandas.Series.  If None is specified, None is
    returned.

    Arguments:
        a {None, ndarray, pandas.DataFrame, or pandas.Series} -- data to
        potentially convert to ndarray

    Returns:
        ndarray, or None - an ndarray
    """
    if a is None:
        return None
    if isinstance(a, np.ndarray):
        return a
    elif isinstance(a, pd.DataFrame) or isinstance(a, pd.Series):
        return a.values
    else:
        raise ValueError(
            "Specified type not supported for conversion to ndarray")


def get_nullable_ndarray(a, type=ctypes.c_double):
    """helper method for wrapper parameters that can be specified either as
    null pointers or pointers to numpy memory

    Arguments:
        a {array_like} or {None} -- array to convert to pointer, if None is
        specified None is returned.

    Keyword Arguments:
        type {object} -- type supported by ctypes.POINTER
        (default: {ctypes.c_double})

    Returns:
        None or ctypes.POINTER -- if the specified argument is None, None is
        returned, otherwise the argument is converted to a C_CONTIGUOUS
        pointer to the underlying ndarray data.
    """
    if a is None:
        return None
    else:
        result = get_ndarray(a).ctypes.data_as(ctypes.POINTER(type))
        return result


class LibCBMWrapper(LibCBM_ctypes):
    """Exposes low level ctypes wrapper to regular python functions
    """
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """frees the allocated libcbm handle"""
        if self.handle:
            err = LibCBM_Error()
            self._dll.LibCBM_Free(ctypes.byref(err), self.handle)
            if err.Error != 0:
                raise RuntimeError(err.getErrorMessage())

    def Initialize(self, config):
        """Initialize libcbm with pools, and flux indicators

        Arguments:
            config {str} -- a json formatted string containing configuration
            for libcbm pools and flux definitions.

            The number of pools, and flux indicators defined here, corresponds
            to other data dimensions used during the lifetime of this instance:
                1. The number of pools here defines the number of columns in
                   the pool value matrix used by several other libCBM functions
                2. The number of flux_indicators here defines the number of
                   columns in the flux indicator matrix in the
                   ComputeFlux method.

            Example:
                {
                    "pools": [
                        {"id": 1, "index": 0, "name": "pool_1"},
                        {"id": 2, "index": 1, "name": "pool_2"},
                           ...
                        {"id": n, "index": n-1, "name": "pool_n"}],

                    "flux_indicators": [
                        {
                            "id": 1,
                            "index": 0,
                            "process_id": 1,
                            "source_pools": [1, 2]
                            "sink_pools": [3]
                        },
                        {
                            "id": 2,
                            "index": 1,
                            "process_id": 1,
                            "source_pools": [1, 2]
                            "sink_pools": [3]
                        },
                        ...
                    ]
                }

            Pool/Flux Indicators configuration rules:
                1. ids may be any integer, but are constrained to be unique
                   within the set of pools.
                2. indexes must be the ordered set of integers from 0 to
                   n_pools - 1.
                3. For flux indicator source_pools and sink_pools, list values
                   correspond to id values in the collection of pools

        Raises:
            RuntimeError: if an error is detected in libCBM, it will be
            re-raised with an appropriate error message.
        """
        p_config = ctypes.c_char_p(config.encode("UTF-8"))

        self.handle = self._dll.LibCBM_Initialize(
            ctypes.byref(self.err),  # error structure
            p_config
            )

        if self.err.Error != 0:
            raise RuntimeError(self.err.getErrorMessage())

    def AllocateOp(self, n):
        """Allocates storage for n matrices, returning an id for the
        allocated block.

        Arguments:
            n {int} -- The number of matrices to allocate.

        Raises:
            AssertionError: raised if the Initialize method was not called
            prior to this method.
            RuntimeError: if an error is detected in libCBM, it will be
            re-raised with an appropriate error message.

        Returns:
            int -- the id for an allocated block of matrices
        """
        if not self.handle:
            raise AssertionError("dll not initialized")

        op_id = self._dll.LibCBM_Allocate_Op(
            ctypes.byref(self.err),
            self.handle, n)

        if self.err.Error != 0:
            raise RuntimeError(self.err.getErrorMessage())

        return op_id

    def FreeOp(self, op_id):
        """Deallocates a matrix block that was allocated by the AllocateOp method.

        Arguments:
            op_id {int} -- The id for an allocated block of matrices.

        Raises:
            AssertionError: raised if the Initialize method was not called
                prior to this method.
            RuntimeError: if an error is detected in libCBM, it will be
                re-raised with an appropriate error message.
        """
        if not self.handle:
            raise AssertionError("dll not initialized")

        self._dll.LibCBM_Free_Op(
            ctypes.byref(self.err),
            self.handle, op_id)

        if self.err.Error != 0:
            raise RuntimeError(self.err.getErrorMessage())

    def SetOp(self, op_id, matrices, matrix_index):
        """Assigns values to an allocated block of matrices.

        Arguments:
            op_id {int} -- The id for an allocated block of matrices
            matrices {list of ndarray} -- a list of n by 3 matrices which are
                coordinate format triplet values (row,column,value).  All
                defined row/column combinations are set with the value, and
                all other matrix cells are assumed to be 0.
            matrix_index {ndarray} -- an array of length n stands where the
                value is an index to a matrix in the specified list of matrices
                provided to this function.

        Raises:
            AssertionError: raised if the Initialize method was not called
                prior to this method.
            RuntimeError: if an error is detected in libCBM, it will be
                re-raised with an appropriate error message.
        """
        if not self.handle:
            raise AssertionError("dll not initialized")
        matrices_array = (LibCBM_Matrix * len(matrices))()
        for i, x in enumerate(matrices):
            matrices_array[i] = LibCBM_Matrix(x)
        matrices_p = ctypes.cast(matrices_array, ctypes.POINTER(LibCBM_Matrix))
        self._dll.LibCBM_SetOp(
            ctypes.byref(self.err), self.handle, op_id, matrices_p,
            len(matrices), matrix_index, matrix_index.shape[0])
        if self.err.Error != 0:
            raise RuntimeError(self.err.getErrorMessage())

    def ComputePools(self, ops, pools, enabled=None):
        """Computes flows between pool values for all stands.

        Each value in the ops parameter is an id to a matrix block, and is also
        conceptually a list of matrixes of length n stands.

        Performs the following computation:

            for op in ops:
                for s in len(n_stands):
                    M = get_matrix(op,s)
                    pools[s,:] = np.matmul(pools[s,:], M)

        Where get_matrix is a function returning the matrix for the
        op, stand index combination.

        Arguments:
            ops {ndarray} -- list of matrix block ids as allocated by the
                AllocateOp function.
            pools {numpy.ndarray or pandas.DataFrame} -- matrix of shape
                n_stands by n_pools. The values in this matrix are updated by
                this function.

        Keyword Arguments:
            enabled {ndarray} -- optional int vector of length n stands. If
                specified, enables or disables flows for each stand, based on
                the value at each stand index. (0 is disabled, !0 is enabled)
                If unspecified, all flows are assumed to be enabled.
                (default: {None})

        Raises:
            AssertionError: raised if the Initialize method was not called
                prior to this method.
            RuntimeError: if an error is detected in libCBM, it will be
                re-raised with an appropriate error message.
        """
        if not self.handle:
            raise AssertionError("dll not initialized")

        n_ops = len(ops)
        p = get_ndarray(pools)
        poolMat = LibCBM_Matrix(p)
        ops_p = ctypes.cast(
            (ctypes.c_size_t*n_ops)(*ops), ctypes.POINTER(ctypes.c_size_t))

        self._dll.LibCBM_ComputePools(
            ctypes.byref(self.err), self.handle, ops_p, n_ops, poolMat,
            get_nullable_ndarray(enabled, type=ctypes.c_int))

        if self.err.Error != 0:
            raise RuntimeError(self.err.getErrorMessage())

    def ComputeFlux(self, ops, op_processes, pools, flux, enabled=None):
        """Computes and tracks flows between pool values for all stands.

        Performs the same operation as ComputePools, except that the fluxes
        are tracked in the specified flux parameter, according to the
        flux_indicators configuration passed to the LibCBM initialize method.

        Arguments:
            ops {ndarray} -- list of matrix block ids as allocated by the
                AllocateOp function.
            op_processes {ndarray} -- list of integers of length n_ops.
                Ids referencing flux indicator process_id definition in the
                LibCBM Initialize method.
            pools {numpy.ndarray or pandas.DataFrame} -- matrix of shape
                n_stands by n_pools. The values in this matrix are updated by
                this function.
            flux {ndarray or pandas.DataFrame} -- matrix of shape n_stands
                by n_flux_indicators. The values in this matrix are updated
                by this function according to the definition of flux
                indicators in the configuration and the flows that occur in
                the specified operations.

        Keyword Arguments:
            enabled {ndarray} -- optional int vector of length n stands. If
                specified, enables or disables flows for each stand, based on
                the value at each stand index. (0 is disabled, !0 is enabled)
                If unspecified, all flows are assumed to be enabled.
                (default: {None})

        Raises:
            AssertionError: raised if the Initialize method was not called
                prior to this method.
            ValueError: raised when parameters passed to this function are not
                valid.
            RuntimeError: if an error is detected in libCBM, it will be
                re-raised with an appropriate error message.
        """
        if not self.handle:
            raise AssertionError("dll not initialized")

        n_ops = len(ops)
        if len(op_processes) != n_ops:
            raise ValueError("ops and op_processes must be of equal length")
        p = get_ndarray(pools)
        poolMat = LibCBM_Matrix(p)

        f = get_ndarray(flux)
        fluxMat = LibCBM_Matrix(f)

        ops_p = ctypes.cast(
            (ctypes.c_size_t*n_ops)(*ops), ctypes.POINTER(ctypes.c_size_t))
        op_process_p = ctypes.cast(
            (ctypes.c_size_t*n_ops)(*op_processes),
            ctypes.POINTER(ctypes.c_size_t))
        enabled = get_nullable_ndarray(enabled, type=ctypes.c_int)
        self._dll.LibCBM_ComputeFlux(
            ctypes.byref(self.err), self.handle, ops_p, op_process_p, n_ops,
            poolMat, fluxMat, enabled)

        if self.err.Error != 0:
            raise RuntimeError(self.err.getErrorMessage())

    def InitializeCBM(self, config):
        """Initializes CBM-specific functionality within LibCBM

        Arguments:
            config {str} -- A json formatted string containing CBM
                configuration.

            See libcbm.configuration.cbm_defaults for construction of the
            "cbm_defaults" value.  It is too large to include a useful example
            here.

            Example:
                {
                    "cbm_defaults": {"p1": {}, "p2": {}, ..., "pN": {}},
                    "classifiers": [
                        {"id": 1, "name": "a"},
                        {"id": 2, "name": "b"},
                        {"id": 3, "name": "c"}
                    ],
                    "classifier_values": [
                        {
                            "id": 1,
                            "classifier_id": 1,
                            "value": "a1",
                            "description": "a1"
                        },
                        {
                            "id": 2,
                            "classifier_id": 2,
                            "value": "b2",
                            "description": "b2"
                        },
                        {
                            "id": 3,
                            "classifier_id": 3,
                            "value": "c1",
                            "description": "c1"
                        }
                    ],
                    "merch_volume_to_biomass": {
                        'db_path': './cbm_defaults.db',
                        'merch_volume_curves': [
                            {
                                'classifier_set': {
                                    'type': 'name', 'values': ['a1','b2','c1']
                                },
                                'components': [
                                    {
                                    'species_id': 1,
                                    'age_volume_pairs': [(age0, vol0),
                                                         (age1, vol0),
                                                         (ageN, volN)]
                                    },
                                    {
                                    'species_id': 2,
                                    'age_volume_pairs': [(age0, vol0),
                                                         (age1, vol0),
                                                         (ageN, volN)]
                                    }
                                ]
                            }
                        ]
                    },
                    "transitions": [
                        {
                            "id": 1,
                            "classifier_set": {
                                'type': 'name', 'values': ['a1','b2','?']
                            },
                            "regeneration_delay": 0,
                            "reset_age": 0
                        }
                    ]
                }

        Raises:
            AssertionError: raised if the Initialize method was not called
                prior to this method.
            RuntimeError: if an error is detected in libCBM, it will be
                re-raised with an appropriate error message.
        """
        if not self.handle:
            raise AssertionError("dll not initialized")

        p_config = ctypes.c_char_p(config.encode("UTF-8"))

        self._dll.LibCBM_Initialize_CBM(ctypes.byref(self.err), self.handle,
                                        p_config)

        if self.err.Error != 0:
            raise RuntimeError(self.err.getErrorMessage())

    def AdvanceStandState(self, inventory, state_variables, parameters):
        """Advances CBM stand variables through a timestep based on the
        current simulation state.

        Arguments:
            inventory {object} -- Data comprised of classifier sets
                and cbm inventory data. Will not be modified by this function.
                See: libcbm.model.cbm_variables.initialize_inventory for a
                compatible definition
            state_variables {pandas.DataFrame} -- simulation variables which
                define all non-pool state in the CBM model.  Altered by this
                function call.  See:
                libcbm.model.cbm_variables.initialize_cbm_state_variables
                for a compatible definition
            parameters {object} -- Read-only parameters used in a CBM timestep.
                See: libcbm.model.cbm_variables.initialize_cbm_parameters for
                a compatible definition.

        Raises:
            AssertionError: raised if the Initialize method was not called
                prior to this method.
            RuntimeError: if an error is detected in libCBM, it will be
                re-raised with an appropriate error message.
        """
        if not self.handle:
            raise AssertionError("dll not initialized")

        i = unpack_ndarrays(inventory)
        v = unpack_ndarrays(state_variables)
        p = unpack_ndarrays(parameters)

        n = i.classifiers.shape[0]
        classifiersMat = LibCBM_Matrix_Int(i.classifiers)

        self._dll.LibCBM_AdvanceStandState(
            ctypes.byref(self.err), self.handle, n, classifiersMat,
            i.spatial_unit, p.disturbance_type, p.transition_rule_id,
            v.last_disturbance_type, v.time_since_last_disturbance,
            v.time_since_land_class_change, v.growth_enabled, v.enabled,
            v.land_class, v.regeneration_delay, v.age)

        if self.err.Error != 0:
            raise RuntimeError(self.err.getErrorMessage())

    def EndStep(self, state_variables):
        """Applies end-of-timestep changes to the CBM state

        state_variables {pandas.DataFrame} -- simulation variables which
            define all non-pool state in the CBM model.  This
            function call will alter this variable with end-of-step changes.
            See: libcbm.model.cbm_variables.initialize_cbm_state_variables
            for a compatible definition

        Raises:
            AssertionError: raised if the Initialize method was not called
                prior to this method.
            RuntimeError: if an error is detected in libCBM, it will be
                re-raised with an appropriate error message.
        """
        if not self.handle:
            raise AssertionError("dll not initialized")
        v = unpack_ndarrays(state_variables)
        n = v.age.shape[0]
        self._dll.LibCBM_EndStep(
            ctypes.byref(self.err), self.handle, n, v.age,
            v.regeneration_delay, v.enabled)
        if self.err.Error != 0:
            raise RuntimeError(self.err.getErrorMessage())

    def InitializeLandState(self, inventory, pools, state_variables):
        """Initializes CBM state to values appropriate for after running
        spinup and before starting CBM stepping

        Arguments:
            inventory {object} -- Data comprised of classifier sets
                and cbm inventory data. Will not be modified by this function.
                See: libcbm.model.cbm_variables.initialize_inventory for a
                compatible definition
            pools {numpy.ndarray or pandas.DataFrame} -- matrix of shape
                n_stands by n_pools. The values in this matrix are updated by
                this function for stands that have an afforestation pre-type
                defined.
            state_variables {pandas.DataFrame} -- simulation variables which
                define all non-pool state in the CBM model.  This
                function call will alter this variable with CBM initial state
                values. See:
                libcbm.model.cbm_variables.initialize_cbm_state_variables for
                a compatible definition

        Raises:
            AssertionError: raised if the Initialize method was not called
                prior to this method.
            RuntimeError: if an error is detected in libCBM, it will be
                re-raised with an appropriate error message.
        """
        if not self.handle:
            raise AssertionError("dll not initialized")

        i = unpack_ndarrays(inventory)
        v = unpack_ndarrays(state_variables)
        n = i.last_pass_disturbance_type.shape[0]
        poolMat = LibCBM_Matrix(get_ndarray(pools))

        self._dll.LibCBM_InitializeLandState(
            ctypes.byref(self.err), self.handle, n,
            i.last_pass_disturbance_type, i.delay, i.age, i.spatial_unit,
            i.afforestation_pre_type_id, poolMat, v.last_disturbance_type,
            v.time_since_last_disturbance, v.time_since_land_class_change,
            v.growth_enabled, v.enabled, v.land_class, v.age)

        if self.err.Error != 0:
            raise RuntimeError(self.err.getErrorMessage())

    def AdvanceSpinupState(self, inventory, variables, parameters):
        """Advances spinup state variables through one spinup step.

        Arguments:
            inventory {object} -- Data comprised of classifier sets
                and cbm inventory data. Will not be modified by this function.
                See: libcbm.model.cbm_variables.initialize_inventory for a
                compatible definition
            variables {object} -- Spinup working variables.  Defines all
                non-pool simulation state during spinup.  See:
                libcbm.model.cbm_variables.initialize_spinup_variables for a
                compatible definition
            parameters {object} -- spinup parameters. See:
                libcbm.model.cbm_variables.initialize_spinup_parameters for a
                compatible definition

        Raises:
            AssertionError: raised if the Initialize method was not called
                prior to this method.
            RuntimeError: if an error is detected in libCBM, it will be
                re-raised with an appropriate error message.

        Returns:
            int -- The number of stands finished running the spinup routine
            as of the end of this call.
        """
        if not self.handle:
            raise AssertionError("dll not initialized")

        i = unpack_ndarrays(inventory)
        p = unpack_ndarrays(parameters)
        v = unpack_ndarrays(variables)
        n = i.spatial_unit.shape[0]

        n_finished = self._dll.LibCBM_AdvanceSpinupState(
            ctypes.byref(self.err), self.handle, n,
            get_nullable_ndarray(i.spatial_unit, type=ctypes.c_int),
            get_nullable_ndarray(p.return_interval, type=ctypes.c_int),
            get_nullable_ndarray(p.min_rotations, type=ctypes.c_int),
            get_nullable_ndarray(p.max_rotations, type=ctypes.c_int),
            i.age, i.delay, v.slow_pools, i.historic_disturbance_type,
            i.last_pass_disturbance_type, i.afforestation_pre_type_id,
            v.spinup_state, v.disturbance_type, v.rotation, v.step,
            v.last_rotation_slow_C, v.enabled)

        if self.err.Error != 0:
            raise RuntimeError(self.err.getErrorMessage())

        return n_finished

    def EndSpinupStep(self, pools, variables):
        """Applies end-of-timestep changes to the spinup state

        Arguments:
            pools {numpy.ndarray or pandas.DataFrame} -- matrix of shape
                n_stands by n_pools. The values in this matrix are used to
                compute a criteria for exiting the spinup routing.  They not
                altered by this function.
            variables {object} -- Spinup working variables.  Defines all
                non-pool simulation state during spinup.  Set to an
                end-of-timestep state by this function. See:
                libcbm.model.cbm_variables.initialize_spinup_variables for a
                compatible definition

        Raises:
            AssertionError: raised if the Initialize method was not called
                prior to this method.
            RuntimeError: if an error is detected in libCBM, it will be
                re-raised with an appropriate error message.
        """
        if not self.handle:
            raise AssertionError("dll not initialized")
        v = unpack_ndarrays(variables)
        n = v.age.shape[0]
        poolMat = LibCBM_Matrix(get_ndarray(pools))
        self._dll.LibCBM_EndSpinupStep(
            ctypes.byref(self.err), self.handle, n, v.spinup_state, poolMat,
            v.disturbance_type, v.age, v.slow_pools, v.growth_enabled)
        if self.err.Error != 0:
            raise RuntimeError(self.err.getErrorMessage())

    def GetMerchVolumeGrowthOps(self, growth_op, inventory, pools,
                                state_variables):
        """[summary]

        Arguments:
            growth_op {[type]} -- [description]
            inventory {[type]} -- [description]
            pools {[type]} -- [description]
            state_variables {[type]} -- [description]

        Raises:
            AssertionError: [description]
            RuntimeError: [description]
        """
        if not self.handle:
            raise AssertionError("dll not initialized")
        n = pools.shape[0]
        poolMat = LibCBM_Matrix(get_ndarray(pools))

        opIds = (ctypes.c_size_t * (1))(*[growth_op])
        i = unpack_ndarrays(inventory)
        classifiersMat = LibCBM_Matrix_Int(get_ndarray(i.classifiers))
        v = unpack_ndarrays(state_variables)

        self._dll.LibCBM_GetMerchVolumeGrowthOps(
            ctypes.byref(self.err), self.handle, opIds, n, classifiersMat,
            poolMat, v.age, i.spatial_unit,
            get_nullable_ndarray(v.last_disturbance_type, type=ctypes.c_int),
            get_nullable_ndarray(
                v.time_since_last_disturbance, type=ctypes.c_int),
            get_nullable_ndarray(v.growth_multiplier, type=ctypes.c_double),
            get_nullable_ndarray(v.growth_enabled, type=ctypes.c_int))

        if self.err.Error != 0:
            raise RuntimeError(self.err.getErrorMessage())

    def GetTurnoverOps(self, biomass_turnover_op, snag_turnover_op,
                       inventory):
        if not self.handle:
            raise AssertionError("dll not initialized")
        i = unpack_ndarrays(inventory)
        n = i.spatial_unit.shape[0]
        opIds = (ctypes.c_size_t * (2))(
            *[biomass_turnover_op, snag_turnover_op])

        self._dll.LibCBM_GetTurnoverOps(
            ctypes.byref(self.err), self.handle, opIds, n, i.spatial_unit)

        if self.err.Error != 0:
            raise RuntimeError(self.err.getErrorMessage())

    def GetDecayOps(self, dom_decay_op, slow_decay_op, slow_mixing_op,
                    inventory, parameters, historical_mean_annual_temp=False):
        if not self.handle:
            raise AssertionError("dll not initialized")
        i = unpack_ndarrays(inventory)
        p = unpack_ndarrays(parameters)
        n = i.spatial_unit.shape[0]
        opIds = (ctypes.c_size_t * (3))(
            *[dom_decay_op, slow_decay_op, slow_mixing_op])
        self._dll.LibCBM_GetDecayOps(
            ctypes.byref(self.err), self.handle, opIds, n,
            get_nullable_ndarray(i.spatial_unit, ctypes.c_int),
            historical_mean_annual_temp,
            get_nullable_ndarray(p.mean_annual_temp))
        if self.err.Error != 0:
            raise RuntimeError(self.err.getErrorMessage())

    def GetDisturbanceOps(self, disturbance_op, inventory,
                          parameters):
        if not self.handle:
            raise AssertionError("dll not initialized")
        spatial_unit = unpack_ndarrays(inventory).spatial_unit
        disturbance_type = unpack_ndarrays(parameters).disturbance_type
        n = spatial_unit.shape[0]
        opIds = (ctypes.c_size_t * (1))(*[disturbance_op])

        self._dll.LibCBM_GetDisturbanceOps(
            ctypes.byref(self.err), self.handle, opIds, n, spatial_unit,
            disturbance_type)

        if self.err.Error != 0:
            raise RuntimeError(self.err.getErrorMessage())
