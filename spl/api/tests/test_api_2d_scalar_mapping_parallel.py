# -*- coding: UTF-8 -*-

from sympy import pi, cos, sin
from sympy import S
from sympy import Tuple
from sympy import Matrix

from sympde.core import dx, dy, dz
from sympde.core import Mapping
from sympde.core import Constant
from sympde.core import Field
from sympde.core import VectorField
from sympde.core import grad, dot, inner, cross, rot, curl, div
from sympde.core import FunctionSpace, VectorFunctionSpace
from sympde.core import TestFunction
from sympde.core import VectorTestFunction
from sympde.core import BilinearForm, LinearForm, Integral
from sympde.core import Norm
from sympde.core import Equation, DirichletBC
from sympde.core import Domain
from sympde.core import Boundary, trace_0, trace_1
from sympde.core import ComplementBoundary
from sympde.gallery import Poisson, Stokes

from spl.fem.context import fem_context
from spl.fem.basic   import FemField
from spl.fem.splines import SplineSpace
from spl.fem.tensor  import TensorFemSpace
from spl.fem.vector  import ProductFemSpace, VectorFemField
from spl.api.discretization import discretize
from spl.api.boundary_condition import DiscreteBoundary
from spl.api.boundary_condition import DiscreteComplementBoundary
from spl.api.boundary_condition import DiscreteDirichletBC

from spl.mapping.discrete import SplineMapping

from numpy import linspace, zeros, allclose

from mpi4py import MPI
import pytest

import os

base_dir = os.path.dirname(os.path.realpath(__file__))
mesh_dir = os.path.join(base_dir, 'mesh')

domain = Domain('\Omega', dim=2)

def create_discrete_space(p=(3,3), ne=(2**4,2**4), periodic=[False, False], comm=MPI.COMM_WORLD):
    # ... discrete spaces
    # Input data: degree, number of elements
    p1,p2 = p
    ne1,ne2 = ne
    per1,per2 = periodic

    # Create uniform grid
    grid_1 = linspace( 0., 1., num=ne1+1 )
    grid_2 = linspace( 0., 1., num=ne2+1 )

    # Create 1D finite element spaces and precompute quadrature data
    V1 = SplineSpace( p1, grid=grid_1, periodic=per1 ); V1.init_fem()
    V2 = SplineSpace( p2, grid=grid_2, periodic=per2 ); V2.init_fem()

    # Create 2D tensor product finite element space
    V = TensorFemSpace( V1, V2, comm=comm )
#    print(V.local_support)
    # ...

    return V

@pytest.mark.parallel
def test_api_poisson_2d_dir_collela():

    # ... abstract model
    mapping = Mapping('M', rdim=2, domain=domain)

    U = FunctionSpace('U', domain)
    V = FunctionSpace('V', domain)

    B1 = Boundary(r'\Gamma_1', domain)
    B2 = Boundary(r'\Gamma_2', domain)
    B3 = Boundary(r'\Gamma_3', domain)
    B4 = Boundary(r'\Gamma_4', domain)

    x,y = domain.coordinates

    F = Field('F', V)

    v = TestFunction(V, name='v')
    u = TestFunction(U, name='u')

    expr = dot(grad(v), grad(u))
    a = BilinearForm((v,u), expr, mapping=mapping)

    expr = 2*pi**2*sin(pi*x)*sin(pi*y)*v
    l = LinearForm(v, expr, mapping=mapping)

    error = F -sin(pi*x)*sin(pi*y)
    l2norm = Norm(error, domain, kind='l2', name='u', mapping=mapping)
    h1norm = Norm(error, domain, kind='h1', name='u', mapping=mapping)

    bc = [DirichletBC(i) for i in [B1, B2, B3, B4]]
    equation = Equation(a(v,u), l(v), bc=bc)
    # ...

    # Communicator, size, rank
    mpi_comm = MPI.COMM_WORLD
    mpi_size = mpi_comm.Get_size()
    mpi_rank = mpi_comm.Get_rank()

    # ... discrete spaces
    Vh, mapping = fem_context(os.path.join(mesh_dir, 'collela_2d.h5'), comm=mpi_comm)
    # ...

    # ... dsicretize the equation using Dirichlet bc
    B1 = DiscreteBoundary(B1, axis=0, ext=-1)
    B2 = DiscreteBoundary(B2, axis=0, ext= 1)
    B3 = DiscreteBoundary(B3, axis=1, ext=-1)
    B4 = DiscreteBoundary(B4, axis=1, ext= 1)

    bc = [DiscreteDirichletBC(i) for i in [B1, B2, B3, B4]]
    equation_h = discretize(equation, [Vh, Vh], mapping, bc=bc)
    # ...

    # ... discretize norms
    l2norm_h = discretize(l2norm, Vh, mapping)
    h1norm_h = discretize(h1norm, Vh, mapping)
    # ...

    # ... solve the discrete equation
    x = equation_h.solve()
    # ...

    # ...
    phi = FemField( Vh, 'phi' )
    phi.coeffs[:,:] = x[:,:]
    phi.coeffs.update_ghost_regions()
    # ...

    # ... compute norms
    l2_error = l2norm_h.assemble(F=phi)
    h1_error = h1norm_h.assemble(F=phi)

    expected_l2_error =  0.09389860248700987
    expected_h1_error =  1.2524517961158783

    assert( abs(l2_error - expected_l2_error) < 1.e-7)
    assert( abs(h1_error - expected_h1_error) < 1.e-7)
    # ...


#==============================================================================
# CLEAN UP SYMPY NAMESPACE
#==============================================================================

def teardown_module():
    from sympy import cache
    cache.clear_cache()