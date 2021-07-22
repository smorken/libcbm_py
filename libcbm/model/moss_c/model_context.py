import os
import json
from types import SimpleNamespace
import numpy as np
import pandas as pd

from libcbm.model.moss_c.pools import Pool
from libcbm.model.moss_c.pools import FLUX_INDICATORS
from libcbm.model.moss_c import model_functions
from libcbm.wrapper.libcbm_wrapper import LibCBMWrapper
from libcbm.wrapper.libcbm_handle import LibCBMHandle
from libcbm import resources


class InputData:
    def __init__(self, decay_parameter, disturbance_matrix, moss_c_parameter,
                 inventory, mean_annual_temperature, merch_volume,
                 spinup_parameter):
        self.decay_parameter = decay_parameter,
        self.disturbance_matrix = disturbance_matrix,
        self.moss_c_parameter = moss_c_parameter,
        self.inventory = inventory,
        self.mean_annual_temperature = mean_annual_temperature,
        self.merch_volume = merch_volume,
        self.spinup_parameter = spinup_parameter


class ModelContext:

    def __init__(self, *args, **kwargs):
        self.input_data = InputData(**kwargs)
        self.n_stands = len(self.input_data.inventory.index)
        self.merch_vol_lookup = model_functions.build_merch_vol_lookup(
            self.input_data.merch_volume)

    def _initialize_libcbm(self):
        libcbm_config = {
            "pools": [
                {'name': p.name, 'id': int(p), 'index': p_idx}
                for p_idx, p in enumerate(Pool)],
            "flux_indicators": [
                {
                    "id": f_idx + 1,
                    "index": f_idx,
                    "process_id": f["process_id"],
                    "source_pools": [int(x) for x in f["source_pools"]],
                    "sink_pools": [int(x) for x in f["sink_pools"]],
                } for f_idx, f in enumerate(FLUX_INDICATORS)]
            }
        self.dll = LibCBMWrapper(
            LibCBMHandle(
                resources.get_libcbm_bin_path(),
                json.dumps(libcbm_config)))

    def _initialize_dynamics_parameter(self):
        max_vols = pd.DataFrame(
            {"max_merch_vol": self.input_data.merch_volume.volume.groupby(
                by=self.input_data.merch_volume.index).max()})

        dynamics_param = (
            self.input_data.inventory
                .merge(
                    self.input_data.moss_c_parameter,
                    left_on="moss_c_parameter_id",
                    right_index=True, validate="m:1")
                .merge(
                    self.input_data.decay_parameter,
                    left_on="decay_parameter_id",
                    right_index=True, validate="m:1")
                .merge(
                    self.input_data.mean_annual_temperature,
                    left_on="mean_annual_temperature_id",
                    right_index=True, validate="m:1")
                .merge(
                    self.input_data.spinup_parameter,
                    left_on="spinup_parameter_id",
                    right_index=True, validate="m:1")
                .merge(
                    max_vols,
                    left_on="merch_volume_id",
                    right_index=True, validate="m:1"))

        if (dynamics_param.index != self.input_data.inventory.index).any():
            raise ValueError()
        self.params = model_functions.to_numpy_namespace(
            dynamics_param)

    def _initialize_pools(self):
        pools = np.zeros(shape=(self.n_stands, len(Pool)))
        pools[:, Pool.Input] = 1.0
        self.pools = pools

    def _initialize_model_state(self):
        initial_age = np.full(self.n_stands, 1, dtype=int)
        model_state = SimpleNamespace(
            age=initial_age,
            merch_vol=model_functions.get_merch_vol(
                self.merch_vol_lookup,
                initial_age,
                self.input_data.inventory.merch_volume_id.to_numpy()))
        self.state = model_state

    def _initialize_disturbance_data(self):
        self.disturbance_matrices = model_functions.initialize_dm(
            self.input_data.disturbance_matrix)
        self.disturbance_types = np.zeros(self.n_stands, 0, dtype=np.uintp)
        self.historic_dm_index = model_functions.np_map(
            self.input_data.inventory.historical_disturbance_type,
            self.disturbance_matrices.dm_name_index)
        self.last_pass_dm_index = model_functions.np_map(
            self.input_data.inventory.historical_disturbance_type,
            self.disturbance_matrices.dm_name_index)


def create_from_csv(dir, decay_parameter_fn="decay_parameter.csv",
                    disturbance_matrix_fn="disturbance_matrix.csv",
                    moss_c_parameter_fn="moss_c_parameter.csv",
                    inventory_fn="inventory.csv",
                    mean_annual_temperature_fn="mean_annual_temperature.csv",
                    merch_volume_fn="merch_volume.csv",
                    spinup_parameter_fn="spinup_parameter.csv"):

    def read_csv(fn):
        path = os.path.join(dir, decay_parameter_fn)
        return pd.read_csv(path, index_col="id")

    return ModelContext(
        decay_parameter=read_csv(decay_parameter_fn),
        disturbance_matrix=read_csv(disturbance_matrix_fn),
        moss_c_parameter=read_csv(moss_c_parameter_fn),
        inventory=read_csv(inventory_fn),
        mean_annual_temperature=read_csv(mean_annual_temperature_fn),
        merch_volume=read_csv(merch_volume_fn),
        spinup_parameter=read_csv(spinup_parameter_fn))
