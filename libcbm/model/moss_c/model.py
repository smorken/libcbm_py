from enum import IntEnum
import json
from typing import SupportsRound
import numpy as np

from libcbm.wrapper.libcbm_wrapper import LibCBMWrapper
from libcbm.wrapper.libcbm_handle import LibCBMHandle
from libcbm import resources

class Pool(IntEnum):
    Input=0,
    FeatherMossLive=1,
    SphagnumMossLive=2,
    FeatherMossFast=3,
    SphagnumMossFast=4,
    FeatherMossSlow=5,
    SphagnumMossSlow=6,
    CO2=7

    def get_names(self):
        return [name for name,_ in list(self.__members__.items())]

def f1(merch_vol, a, b):
    """Returns Canopy openess, O(t) as a function of Merch. Volume
    
    10^(((a)*(Log(V(t))) + b) 

    Args:
        merch_vol (float, np.ndarray): array of merch volumes
        a (float, np.ndarray): MossC a parameter
        b (float, np.ndarray): MossC b parameter

    Returns:
        np.ndarray: Canopy openess
    """
    return np.where(
        merch_vol == 0.0, 60.0,
        np.power(10, a * np.log10(merch_vol) + b))

def f2(openness, stand_age, c, d):
    """ returns Feather moss ground cover, GCfm(t)

    (O(t)* c) + d

    Args:
        openness (double, np.ndarray): canopy openness
        stand_age (int, np.ndarray): stand age in years
        c (float, np.ndarray): MossC c parameter, 
        d (float, np.ndarray): MossC d parameter

    Returns:
        np.ndarray: Feathuer moss ground cover
    """
    return np.where(
        stand_age < 10,
        0.0,
        np.where(
            openness > 70.0,
            100.0, openness * c + d))

def f3(openness, stand_age, e, f):
    pass

def f4(openness, g, h):
    pass

def f5(openness, i, j, l):

    pass

def f6(merch_vol, m, n):
    """ 

    Args:
        merch_vol ([type]): [description]
        m ([type]): [description]
        n ([type]): [description]
    """
    pass

def f7(mean_annual_temp, base_decay_rate, q10, t_ref):
    """Applied Decay rate, ak this applies to any of the moss DOM 
    pools feather moss fast (kff), feather moss slow (kfs), sphagnum
    fast (ksf), and sphagnum slow (kss)

    Args:
        mean_annual_temp ([type]): [description]
        base_decay_rate ([type]): [description]
        q10 ([type]): [description]
        t_ref ([type]): [description]
    """
    pass

def get_or_add_c_annual_process_matrix(collection, age, mean_annual_temp,
                                       max_merch_vol, merch_vol,
                                       function_params, decay_params):
    pass

def c_annual_process_dynamics_params(age, mean_annual_temp, max_merch_vol, merch_vol,
                              function_params, decay_params):

    kss = f6(max_merch_vol, function_params.m, function_params.n)

    # applied feather moss fast pool decay rate
    akff = f7(
        mean_annual_temp, decay_params.kff, decay_params.q10,
        decay_params.tref)

    # applied feather moss slow pool decay rate
    akfs = f7(
        mean_annual_temp, decay_params.kfs, decay_params.q10,
        decay_params.tref) 
    
    # applied sphagnum fast pool applied decay rate
    aksf = f7(
        mean_annual_temp, decay_params.ksf, decay_params.q10,
        decay_params.tref) 

    # applied sphagnum slow pool applied decay rate
    akss = f7(mean_annual_temp, kss, decay_params.q10, decay_params.tref) 

    openness = f1(merch_vol, function_params.a, function_params.b)
    
    # Feather moss ground cover
    GCfm = f2(openness, age, function_params.c, function_params.d) 
    
    # Sphagnum ground cover
    GCsp = f3(openness, age, function_params.e, function_params.f) 

    # Feathermoss NPP (assuming 100% ground cover)
    NPPfm = f4(openness, function_params.g, function_params.h) 

    # Sphagnum NPP (assuming 100% ground cover)
    NPPsp = f5(
        openness, function_params.i, function_params.j, function_params.l)
    
def get_annual_process_matrix():
    flows = np.array([
        [Pool.Input, Pool.FeatherMossLive, NPPfm * GCfm/100.0]
        [Pool.Input, Pool.SphagnumMossLive, NPPsp * GCsp/100.0],
 
        # turnovers
        [Pool.FeatherMossLive, Pool.FeatherMossFast, 1.0],
        [Pool.FeatherMossLive, Pool.FeatherMossLive, 0.0],
 
        [Pool.FeatherMossFast, Pool.FeatherMossSlow, akff * 0.15],
 
        [Pool.SphagnumMossLive, Pool.SphagnumMossFast, 1.0],
        [Pool.SphagnumMossLive, Pool.SphagnumMossLive, 0.0],
 
        [Pool.SphagnumMossFast, Pool.SphagnumMossSlow, aksf*0.15],
 
        # fast losses
        [Pool.FeatherMossFast, Pool.FeatherMossFast, 1.0-akff],
        [Pool.SphagnumMossFast, Pool.SphagnumMossFast, 1.0-aksf],
 
        # decays
        [Pool.FeatherMossFast, Pool.CO2, akff*0.85],
 
        [Pool.SphagnumMossFast, Pool.CO2, aksf*0.85],
 
        [Pool.FeatherMossSlow, Pool.CO2, akfs],
        [Pool.FeatherMossSlow, Pool.FeatherMossSlow, 1.0-akfs],
 
        [Pool.SphagnumMossSlow, Pool.CO2, akss],
        [Pool.SphagnumMossSlow, Pool.SphagnumMossSlow, 1.0-akss]
    ])
    return flows


def get_disturbance_flows(disturbance_type_name, disturbance_matrices):
    matrix = [
        [

        ]
    ]
    return matrix


class SpinupState(IntEnum):
    AnnualProcesses=1,
    HistoricalEvent=2,
    LastPassEvent=3,
    End=4


def _small_slow_diff(last_rotation_slow, this_rotation_slow):
    return abs((last_rotation_slow - this_rotation_slow) \
           / (last_rotation_slow+this_rotation_slow)/2.0) < 0.001


def advance_spinup_state(spinup_state, age, return_interval, rotation_num, max_rotations, last_rotation_slow, this_rotation_slow):
    np.where(
        spinup_state == SpinupState.AnnualProcesses, 
        np.where(
            age >= return_interval,
            np.where(
                _small_slow_diff(last_rotation_slow, this_rotation_slow)
                | rotation_num > max_rotations,
                SpinupState.LastPassEvent,
                SpinupState.HistoricalEvent)),
            SpinupState.AnnualProcesses,
        np.where(
            spinup_state == SpinupState.HistoricalEvent,
            SpinupState.AnnualProcesses,
            SpinupState.End))


    #if spinup_state == SpinupState.AnnualProcesses:
    #    if age >= return_interval:
    #        small_slow_diff = \
    #            abs((last_rotation_slow - this_rotation_slow) \
    #            / (last_rotation_slow+this_rotation_slow)/2.0) < 0.001
    #        if small_slow_diff or rotation_num >= max_rotations:
    #            return SpinupState.LastPassEvent
    #        else:
    #            return SpinupState.HistoricalEvent
    #    else:
    #        return SpinupState.AnnualProcesses
    #elif spinup_state == SpinupState.HistoricalEvent:
    #    return SpinupState.AnnualProcesses
    #elif spinup_state == SpinupState.LastPassEvent:
    #    return SpinupState.End

def get_ops(model_state):
    if model_state.spinup_state == SpinupState.AnnualProcesses:
        mat_index = get_annual_process_matrix()

def spinup(pools, model_state, model_params):

    while True:
        model_state.spinup_state = advance_spinup_state(
            spinup_state=model_state.spinup_state,
            age=model_state.age,
            return_interval=model_params.return_interval,
            rotation_num=model_state.rotation_num,
            max_rotations=model_params.max_rotations,
            last_rotation_slow=model_state.last_rotation_slow,
            this_rotation_slow=model_state.this_rotation_slow)
        
        
        annual_process_flows = []
        for row_idx in range(0, len(model_state.index)):
            annual_process_flows.append(
                c_annual_process_dynamics(
                   # row.iloc[].age,
                   # paramsmean_annual_temp, max_merch_vol, merch_vol,
                   #           function_params, decay_params
                ))


def compute_pools(dll, pools, ops, op_indices):
    pools = pools.copy()
    
    op_ids = []
    for i, op in enumerate(ops):
        op_id = dll.allocate_op(pools.shape[0])
        op_ids.append(op_id)
        #The set op function accepts a matrix of coordinate triples.  
        #In LibCBM matrices are stored in a sparse format, so 0 values can be omitted from the parameter
        dll.set_op(op_id, [to_coordinate(x) for x in op], 
                   np.ascontiguousarray(op_indices[:,i]))
        
    dll.compute_pools(op_ids, pools)
    
    return pools


def initialize(config):
    dll = LibCBMWrapper(
        LibCBMHandle(
            resources.get_libcbm_bin_path(),
            json.dumps(config)))

def run():
    pools = np.repeat()
    flux_processor = initialize(
        config={
            "pools": [
                {'name': x, 'id': i+1, 'index': i}
                 for i, x in enumerate(Pool.__members__.keys())],
            "flux_indicators": []
        })