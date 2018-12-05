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
from spl.api.settings import SPL_BACKEND_PYTHON, SPL_BACKEND_PYCCEL

from spl.mapping.discrete import SplineMapping

from numpy import linspace, zeros, allclose
from utils import assert_identical_coo

from mpi4py import MPI

DEBUG = False

domain = Domain('\Omega', dim=2)

def create_discrete_space(p=(3,3), ne=(2**4,2**4), periodic=[False, False], comm=MPI.COMM_WORLD):
#def create_discrete_space(p=(3,3), ne=(2**8,2**8), periodic=[False, False], comm=MPI.COMM_WORLD):
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
    # ...

    return V


# TODO not working yet
def laplace_2d_periodic_1(backend=SPL_BACKEND_PYTHON):

    # ... abstract model
    U = FunctionSpace('U', domain)
    V = FunctionSpace('V', domain)

    x,y = domain.coordinates

    F = Field('F', V)

    v = TestFunction(V, name='v')
    u = TestFunction(U, name='u')

    expr = dot(grad(v), grad(u)) + v*u
    a = BilinearForm((v,u), expr)

    expr = (8*pi**2 + 1 )*sin(2*pi*x)*sin(2*pi*y)*v
    l = LinearForm(v, expr)

    error = F -sin(2*pi*x)*sin(2*pi*y)
    l2norm = Norm(error, domain, kind='l2', name='u')
    h1norm = Norm(error, domain, kind='h1', name='u')

    equation = Equation(a(v,u), l(v))
    # ...

    # Communicator, size, rank
    mpi_comm = MPI.COMM_WORLD
    mpi_size = mpi_comm.Get_size()
    mpi_rank = mpi_comm.Get_rank()

    # ... discrete spaces
    Vh = create_discrete_space(periodic=[True, True], comm=mpi_comm)
    # ...

    # ... discretize the equation
    equation_h = discretize(equation, [Vh, Vh], backend=backend)
    # ...

    # ... discretize norms
    l2norm_h = discretize(l2norm, Vh, backend=backend)
    h1norm_h = discretize(h1norm, Vh, backend=backend)
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
    error = l2norm_h.assemble(F=phi)
    if mpi_rank == 0:
        print('> L2 norm      = ', error)

    error = h1norm_h.assemble(F=phi)
    if mpi_rank == 0:
        print('> H1 seminorm  = ', error)
    # ...

###############################################
if __name__ == '__main__':

    laplace_2d_periodic_1()
