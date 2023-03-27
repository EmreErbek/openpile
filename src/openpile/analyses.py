"""
`Analyses` module
==================

The `analyses` module is used to run various simulations. 

Every function from this module returns an `openpile.compute.Result` object. 

"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# from pydantic import BaseModel, Field, root_validator
from pydantic.dataclasses import dataclass

from openpile.core import kernel
import openpile.core.validation as validation
import openpile.utils.graphics as graphics
import openpile.core.misc as misc


class PydanticConfig:
    arbitrary_types_allowed = True


def structural_forces_to_df(model, q):
    x = model.nodes_coordinates["x [m]"].values
    x = misc.repeat_inner(x)
    L = kernel.mesh_to_element_length(model).reshape(-1)

    N = np.vstack((-q[0::6], q[3::6])).reshape(-1, order="F")
    V = np.vstack((-q[1::6], q[4::6])).reshape(-1, order="F")
    M = np.vstack((-q[2::6], -q[2::6] + L * q[1::6])).reshape(-1, order="F")

    structural_forces_to_DataFrame = pd.DataFrame(
        data={
            "Elevation [m]": x,
            "N [kN]": N,
            "V [kN]": V,
            "M [kNm]": M,
        }
    )

    return structural_forces_to_DataFrame


def disp_to_df(model, u):
    x = model.nodes_coordinates["x [m]"].values

    Tx = u[::3].reshape(-1)
    Ty = u[1::3].reshape(-1)
    Rx = u[2::3].reshape(-1)

    disp_to_DataFrame = pd.DataFrame(
        data={
            "Elevation [m]": x,
            "Settlement [m]": Tx,
            "Deflection [m]": Ty,
            "Rotation [rad]": Rx,
        }
    )

    return disp_to_DataFrame


@dataclass(config=PydanticConfig)
class Result:
    name: str
    displacements: pd.DataFrame
    forces: pd.DataFrame

    class Config:
        frozen = True

    @property
    def settlement(self):
        return self.displacements[["Elevation [m]", "Settlement [m]"]]

    @property
    def deflection(self):
        return self.displacements[["Elevation [m]", "Deflection [m]"]]

    @property
    def rotation(self):
        return self.displacements[["Elevation [m]", "Rotation [rad]"]]

    def plot_deflection(self, assign=False):
        fig = graphics.plot_deflection(self)
        return fig if assign else None

    def plot_forces(self, assign=False):
        fig = graphics.plot_forces(self)
        return fig if assign else None

    def plot(self, assign=False):
        fig = graphics.plot_results(self)
        return fig if assign else None


def simple_beam_analysis(model):
    """
    Function where loading or displacement defined in the model boundary conditions
    are used to solve the system of equations, .

    Parameters
    ----------
    model : `openpile.construct.Model` object
        Model where structure and boundary conditions are defined.

    Returns
    -------
    results : `openpile.compute.Result` object
        Results of the analysis
    """

    if model.soil is None:
        # initialise global force
        F = kernel.mesh_to_global_force_dof_vector(model.global_forces)
        # initiliase prescribed displacement vector
        U = kernel.mesh_to_global_disp_dof_vector(model.global_disp)
        # initialise global stiffness matrix
        K = kernel.build_stiffness_matrix(model)
        # initialise global supports vector
        supports = kernel.mesh_to_global_restrained_dof_vector(model.global_restrained)

        # validate boundary conditions
        validation.check_boundary_conditions(model)

        u, _ = kernel.solve_equations(K, F, U, restraints=supports)

        # internal forces
        q_int = kernel.struct_internal_force(model, u)

        # Final results
        results = Result(
            name=f"{model.name} ({model.pile.name}/{model.soil.name})",
            displacements=disp_to_df(model, u),
            forces=structural_forces_to_df(model, q_int),
        )

        return results


def simple_winkler_analysis(model, solver="NR", max_iter: int = 100):
    """
    Function where loading or displacement defined in the model boundary conditions
    are used to solve the system of equations, .

    #TODO

    Parameters
    ----------
    model : `openpile.construct.Model` object
        Model where structure and boundary conditions are defined.
    solver: str, by default 'MNR'
        solver. literally 'NR': "Newton-Raphson" or 'MNR': "Modified Newton-Raphson"
    max_iter: int, by defaut 100
        maximum number of iterations for convergence

    Returns
    -------
    results : `openpile.analyses.Result` object
        Results of the analysis
    """

    if model.soil is None:
        UserWarning("SoilProfile must be provided when creating the Model.")

    else:
        # initialise global force
        F = kernel.mesh_to_global_force_dof_vector(model.global_forces)
        # initiliase prescribed displacement vector
        U = kernel.mesh_to_global_disp_dof_vector(model.global_disp)
        # initialise displacement vectors
        d = np.zeros(U.shape)

        # initialise global stiffness matrix
        K = kernel.build_stiffness_matrix(model, u=d, kind="initial")

        # initialise global supports vector
        supports = kernel.mesh_to_global_restrained_dof_vector(model.global_restrained)

        # validate boundary conditions
        # validation.check_boundary_conditions(model)

        # Initialise residual forces
        Rg = F

        # incremental calculations to convergence
        iter_no = 0
        while iter_no <= 100:
            iter_no += 1

            # solve system
            try:
                u_inc, Q = kernel.solve_equations(K, Rg, U, restraints=supports)
            except np.linalg.LinAlgError:
                print(
                    """Cannot converge. Failure of the pile-soil system.\n
                      Boundary conditions may not be realistic or values may be too large."""
                )
                break

            # External forces
            F_ext = F - Q
            control = np.linalg.norm(F_ext)

            # add up increment displacements
            d += u_inc

            # internal forces
            K_secant = kernel.build_stiffness_matrix(model, u=d, kind="secant")
            F_int = K_secant.dot(d)

            # calculate residual forces
            Rg = F_ext - F_int

            # check if converged
            if np.linalg.norm(Rg[~supports]) < 1e-4 * control:
                print(f"Converged at iteration no. {iter_no}")
                break

            if iter_no == 100:
                print("Not converged after 100 iterations.")

            # re-calculate global stiffness matrix for next iterations
            if solver == "NR":
                K = kernel.build_stiffness_matrix(model, u=d, kind="tangent")
            elif solver == "MNR":
                pass

            # reset displacements in case of displacement-driven analysis
            U[:] = 0.0

        # Internal forces calculations with dim(nelem,6,6)
        q_int = kernel.struct_internal_force(model, d)

        # Final results
        results = Result(
            name=f"{model.name} ({model.pile.name}/{model.soil.name})",
            displacements=disp_to_df(model, d),
            forces=structural_forces_to_df(model, q_int),
        )

        return results