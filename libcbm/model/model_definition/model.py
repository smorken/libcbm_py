from typing import Callable
from typing import Iterator
from contextlib import contextmanager
from libcbm.model.model_definition.cbm_variables import CBMVariables
from libcbm.model.model_definition import model_handle
from libcbm.model.model_definition.model_handle import ModelHandle
from libcbm.wrapper.libcbm_operation import Operation


class CBMModel:
    """
    An abstraction of a Carbon budget model
    """

    def __init__(
        self,
        model_handle: ModelHandle,
        pool_config: list[str],
        flux_config: list[dict],
        spinup_func: Callable[["CBMModel", CBMVariables], CBMVariables] = None,
        step_func: Callable[["CBMModel", CBMVariables], CBMVariables] = None,
    ):
        self._model_handle = model_handle
        self._pool_config = pool_config
        self._flux_config = flux_config
        self._spinup_func = spinup_func
        self._step_func = step_func

    @property
    def pool_names(self) -> list[str]:
        return self._pool_config.copy()

    @property
    def flux_names(self) -> list[str]:
        return [f["name"] for f in self._flux_config]

    def spinup(self, spinup_input: CBMVariables) -> CBMVariables:
        """Initialize the Carbon pools for the specified input
        Args:
            spinup_input (CBMVariables): collection of dataframe
                inputs specifying spinup input

        Returns:
            CBMVariables: initialized CBM input for stepping
        """
        return self._spinup_func(spinup_input)

    def step(self, cbm_vars: CBMVariables) -> CBMVariables:
        """Advance the specified cbm model state/variables by 1 step

        Args:
            cbm_vars (CBMVariables): CBM variables and state (pools/flux etc)

        Returns:
            CBMVariables: The CBM variables, advanced by 1 step
        """
        return self._step_func(self, cbm_vars)

    def create_operation(
        self, matrices: list, fmt: str, process_id: int
    ) -> Operation:
        """Create a set of matrix operations for C dynamics along the row axis
        of cbm_vars. The relationship of matrices to stands is 1:m

        Args:
            matrices (list): a list of matrix information
            fmt (str): one of "repeating_coordinates" or "matrix_list"
            process_id (int): the process_id for flux indicator categorization

        Returns:
            Operation: an `Operation` object
        """
        return self._model_handle.create_operation(matrices, fmt, process_id)

    def compute(
        self,
        cbm_vars: CBMVariables,
        operations: list[Operation],
    ):
        """Compute a batch of C dynamics

        Args:
            cbm_vars (CBMVariables): _description_
            operations (list[Operation]): a list of Operation objects as
                allocated by `create_operation`
            op_process_ids (list[int]): list of integers
        """

        self._model_handle.compute(
            cbm_vars["pools"],
            cbm_vars["flux"] if "flux" in cbm_vars else None,
            cbm_vars["state"]["enabled"],
            operations,
        )


@contextmanager
def initialize(
    pool_config: list[str],
    flux_config: list[dict],
    model_parameters: dict,
    spinup_func: Callable[[CBMModel, CBMVariables], CBMVariables],
    step_func: Callable[[CBMModel, CBMVariables], CBMVariables],
) -> Iterator[CBMModel]:
    """Initialize a CBMModel for spinup or stepping

    Args:
        pool_config (list[str]): list of string pool identifiers.
        flux_config (list[dict]): list of flux indicator dictionary
            structures.
        model_parameters (dict): a dictionary of abitrary model
            parameters used by the specified spinup or step functions
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
        Iterator[CBMModel]: instance of CBMModel
    """
    pools = {p: i for i, p in enumerate(pool_config)}
    flux = None
    with model_handle.create_model_handle(pools, flux) as _model_handle:
        yield CBMModel(
            _model_handle,
            pool_config,
            flux_config,
            model_parameters,
            spinup_func,
            step_func,
        )
