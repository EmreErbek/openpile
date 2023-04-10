# misc functions


import random
import numpy as np
import pandas as pd
import math as m

from numba import njit
from matplotlib.colors import CSS4_COLORS


def from_list2x_parse_top_bottom(var):
    """provide top and bottom values of layer based on float or list inputs"""
    if isinstance(var, float) or isinstance(var, int):
        top = var
        bottom = var
    elif isinstance(var, list) and len(var) == 1:
        top = var[0]
        bottom = var[0]
    elif isinstance(var, list) and len(var) == 2:
        top = var[0]
        bottom = var[1]
    else:
        print("Soil Layer variable is not a float nor a list")
        raise TypeError

    return top, bottom


def var_to_str(var):
    if isinstance(var, float) or isinstance(var, int):
        var_print = var
    elif isinstance(var, list):
        var_print = "-".join(str(v) for v in var)
    else:
        raise ValueError("not a float nor list")
    return var_print


def generate_color_string():
    colors = list(CSS4_COLORS.values())
    return colors[random.randint(0, len(colors) - 1)]


def repeat_inner(arr):
    arr = arr.reshape(-1, 1)

    arr_inner = arr[1:-1]
    arr_inner = np.tile(arr_inner, (2)).reshape(-1)

    return np.hstack([arr[0], arr_inner, arr[-1]])


def get_springs(springs: np.ndarray, elevations: np.ndarray, kind: str) -> pd.DataFrame:
    """
    Returns soil springs created for the given model in one DataFrame.

    Parameters
    ----------
    springs : ndarray dim[nelem,2,2,spring_dim]
        Springs at top and bottom of element
    elevations : ndarray
        self.nodes_coordinates["x [m]"].values
    kind : str
        type of spring to extract. one of ["p-y", "m-t", "Hb-y", "Mb-t", "t-z"]

    Returns
    -------
    pd.DataFrame
        Soil springs
    """

    def springs_to_df(springs: np.ndarray, elevations: np.ndarray, flag) -> pd.DataFrame:

        spring_dim = springs.shape[-1]
        nelem = springs.shape[0]

        column_values_spring = [f"VAL {i}" for i in range(spring_dim)]

        id = np.repeat(np.arange(nelem), 4)
        x = np.repeat(repeat_inner(elevations), 2)

        if len(x) > 2:
            t_b = ["top", "top", "bottom", "bottom"] * int(nelem)

            df = pd.DataFrame(
                data={
                    "Element no.": id,
                    "Position": t_b,
                    "Elevation [m]": x,
                }
            )
        else:
            df = pd.DataFrame(
                data={
                    "Element no.": id,
                    "Elevation [m]": x,
                }
            )

        df["type"] = flag.split("-") * int(len(x) / 2)
        df[column_values_spring] = np.reshape(springs, (-1, spring_dim))

        return df

    return springs_to_df(springs, elevations, flag=kind)


@njit(cache=True)
def conic(
    x_u: float,
    n: float,
    k: float,
    y_u: float,
    output_length: int,
):
    # Create x vector with 10% extension
    x = np.linspace(0, x_u, output_length - 1).astype(np.float32)
    x = np.append(x, 1.1 * x_u)

    a = 1 - 2 * n

    y = np.zeros((len(x)), dtype=np.float32)

    for i in range(len(x)):
        if abs(x[i] - x_u) < 1e-4:
            y[i] = y_u
        elif x[i] < x_u:
            b = 2 * n * x[i] / x_u - (1 - n) * (1 + x[i] * k / y_u)
            c = x[i] * (k / y_u) * (1 - n) - n * (x[i] ** 2 / x_u**2)

            y[i] = y_u * 2 * c / (-b + (b**2 - 4 * a * c) ** 0.5)
        else:
            y[i] = y_u

    return x, y
