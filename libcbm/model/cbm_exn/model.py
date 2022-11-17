from typing import Callable
from typing import Iterator
from contextlib import contextmanager
from libcbm.model.cbm_exn.cbm_variables import CBMVariables
from libcbm.model.cbm_exn.cbm_variables import SpinupInput
from libcbm.model import model_definition
from libcbm.wrapper.libcbm_operation import Operation
from libcbm.wrapper import libcbm_operation


class CBMEXNModel:
    def __init__(
        self,
        model_handle: model_definition.ModelHandle,
        pool_config: list[str],
        flux_config: list[dict],
        model_parameters: dict,
        spinup_func: Callable[
            ["CBMEXNModel", SpinupInput], CBMVariables
        ] = None,
        step_func: Callable[
            ["CBMEXNModel", CBMVariables], CBMVariables
        ] = None,
    ):
        self._model_handle = model_handle
        self._pool_config = pool_config
        self._flux_config = flux_config
        self._spinup_func = spinup_func
        self._step_func = step_func
        self._parameters = model_parameters

    @property
    def parameters(self) -> dict:
        return self._parameters

    def spinup(self, spinup_input: SpinupInput) -> CBMVariables:
        return self._spinup_func(spinup_input)

    def step(self, cbm_vars: CBMVariables) -> CBMVariables:
        return self._step_func(self, cbm_vars)

    def create_operation(self, matrices: list, fmt: str) -> Operation:
        return self._model_handle.create_operation(matrices, fmt)

    def compute(
        self,
        cbm_vars: CBMVariables,
        operations: list[Operation],
        op_process_ids: list[int],
    ):
        libcbm_operation.compute(
            dll=self._model_handle.wrapper,
            pools=cbm_vars.pools,
            operations=operations,
            op_processes=[int(x) for x in op_process_ids],
            flux=cbm_vars.flux,
            enabled=cbm_vars.state["enabled"],
        )
        self._model_handle.compute()


@contextmanager
def initialize(
    pool_config: list[str],
    flux_config: list[dict],
    spinup_func: Callable[[CBMEXNModel, SpinupInput], CBMVariables],
    step_func: Callable[[CBMEXNModel, CBMVariables], CBMVariables],
) -> Iterator[CBMEXNModel]:
    """Initialize a CBMEXNModel for spinup or stepping

    Args:
        pool_config (list[str]): list of string pool identifiers.
        flux_config (list[dict]): list of flux indicator dictionary
            structures.
        spinup_func (func): A function that spins up CBM carbon
            pools, and initialized CBM model state.
        step_func (func): A function that advances CBM
            carbon pools, and CBM model state by one timestep.

    Example Pools::

        ["Input", "Merchantable", "OtherC"]

    Example Flux indicators::

        [
            {
                "name": "NPP",
                "process": "Growth",
                "source_pools": [
                    "Input",
                ],
                "sink_pools": [
                    "Merchantable",
                    "Foliage",
                    "Other",
                    "FineRoot",
                    "CoarseRoot"
                ]
            },
            {
                "name": "DOMEmissions",
                "process": "Decay",
                "source_pools": [
                    "AboveGroundVeryFast",
                    "BelowGroundVeryFast",
                    "AboveGroundFast",
                    "BelowGroundFast",
                    "MediumSoil",
                    "AboveGroundSlow",
                    "BelowGroundSlow",
                    "StemSnag",
                    "BranchSnag",
                ],
                "sink_pools": [
                    "CO2"
                ]
            }
        ]

    Yields:
        Iterator[CBMEXNModel]: instance of CBMEXNModel
    """
    pools = None
    flux = None
    with model_definition.create_model(pools, flux) as model_handle:
        yield CBMEXNModel(
            model_handle, pool_config, flux_config, spinup_func, step_func
        )
