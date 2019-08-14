from types import SimpleNamespace
import pandas as pd
import numpy as np
import ctypes


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

    Args:
        variables (SimpleNamespace, pd.DataFrame): The set of variables to
        unpack.

    Raises:
        ValueError: the type of the specified argument was not supported

    Returns:
        types.SimpleNamespace: a SimpleNamespace whose properties are ndarray.
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

    Args:
        a (None, ndarray, pandas.DataFrame, or pandas.Series): data to
            potentially convert to ndarray

    Returns:
        ndarray, or None: the specified ndarray, the ndarray storage of a
            specified pandas object, or None
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
    """Helper method for wrapper parameters that can be specified either as
    null pointers or pointers to numpy memory

    Args:
        a (numpy.ndarray, None): array to convert to pointer, if None is
            specified None is returned.
        type (object, optional): type supported by ctypes.POINTER. Defaults
            to ctypes.c_double.

    Returns:
        None or ctypes.POINTER: if the specified argument is None, None is
            returned, otherwise the argument is converted to a pointer to
            the underlying ndarray data.
    """
    if a is None:
        return None
    else:
        result = get_ndarray(a).ctypes.data_as(ctypes.POINTER(type))
        return result


def promote_scalar(value, size, dtype):
    """If the specified value is scalar promote it to a numpy array filled
    with the scalar value, and otherwise return the value.  This is purely
    a helper function to allow scalar parameters for certain vector
    functions

    Args:
        value (numpy.ndarray, number, or None): value to promote
        size (int): the length of the resulting vector if promotion
            occurs
        dtype (object): object used to define the type of the resulting
            vector if promotion occurs


    Returns:
        ndarray or None: returns either the original value, a promoted
            scalar or None depending on the specified values
    """
    if value is None:
        return None
    elif isinstance(value, np.ndarray):
        return value
    else:
        return np.ones(size, dtype=dtype) * value


def append_simulation_result(simulation_result, timestep_data, timestep):
    """Append the specified timestep data to a simulation result spanning
    multiple time steps

    Args:
        simulation_result (pandas.DataFrame): a dataframe storing the
            simulation results.  If this parameter is None a new dataframe
            will be created with the single timestep as the contents.
        timestep_data (pandas.DataFrame): a dataframe storing a single
            timestep result
        timestep (int): an integer which will be added to the data appended
            to the larger simulation result in the "timestep" column

    Returns:
        pandas.DataFrame: The simulation result with the specified timestep
            data appended
    """
    ts = timestep_data.copy()
    ts.insert(loc=0, column="timestep", value=timestep)
    ts.insert(loc=0, column="identifier", value=list(range(1, ts.shape[0]+1)))
    if simulation_result is None or simulation_result.shape[0] == 0:
        simulation_result = ts
    else:
        simulation_result = simulation_result.append(ts)
    simulation_result.reset_index(drop=True)
    return simulation_result
