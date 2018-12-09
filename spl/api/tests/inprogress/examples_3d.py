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

import os

base_dir = os.path.dirname(os.path.realpath(__file__))
mesh_dir = os.path.join(base_dir, '..', 'mesh')

domain = Domain('\Omega', dim=3)

#==============================================================================
def create_discrete_space(p=(2,2,2), ne=(2**2,2**2,2**2)):
    # ... discrete spaces
    # Input data: degree, number of elements
    p1,p2,p3 = p
    ne1,ne2,ne3 = ne

    # Create uniform grid
    grid_1 = linspace( 0., 1., num=ne1+1 )
    grid_2 = linspace( 0., 1., num=ne2+1 )
    grid_3 = linspace( 0., 1., num=ne3+1 )

    # Create 1D finite element spaces and precompute quadrature data
    V1 = SplineSpace( p1, grid=grid_1 ); V1.init_fem()
    V2 = SplineSpace( p2, grid=grid_2 ); V2.init_fem()
    V3 = SplineSpace( p3, grid=grid_3 ); V3.init_fem()

    # Create 3D tensor product finite element space
    V = TensorFemSpace( V1, V2, V3 )
    # ...

    return V


#==============================================================================
def test_api_poisson_3d_dirneu_identity_2():

    # ... abstract model
    mapping = Mapping('M', rdim=3, domain=domain)

    U = FunctionSpace('U', domain)
    V = FunctionSpace('V', domain)

    B2 = Boundary(r'\Gamma_2', domain) # neumann  bc will be applied on B2

    x,y,z = domain.coordinates

    F = Field('F', V)

    v = TestFunction(V, name='v')
    u = TestFunction(U, name='u')

    expr = dot(grad(v), grad(u))
    a = BilinearForm((v,u), expr, mapping=mapping)

    solution = sin(0.5*pi*x)*sin(pi*y)*sin(pi*z)

    expr = (9./4.)*pi**2*solution*v
    l0 = LinearForm(v, expr, mapping=mapping)

    expr = v*trace_1(grad(solution), B2)
    l_B2 = LinearForm(v, expr, mapping=mapping)

    expr = l0(v) + l_B2(v)
    l = LinearForm(v, expr, mapping=mapping)

    error = F - solution
    l2norm = Norm(error, domain, kind='l2', name='u', mapping=mapping)
    h1norm = Norm(error, domain, kind='h1', name='u', mapping=mapping)

    bc = [DirichletBC(-B2)]
    equation = Equation(a(v,u), l(v), bc=bc)
    # ...

    # ... discrete spaces
    Vh, mapping = fem_context(os.path.join(mesh_dir, 'identity_3d.h5'))
    # ...

    # ... dsicretize the equation using Dirichlet bc
    B2 = DiscreteBoundary(B2, axis=0, ext= 1)

    bc = [DiscreteDirichletBC(-B2)]
    equation_h = discretize(equation, [Vh, Vh], mapping, boundary=B2, bc=bc)
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
    phi.coeffs[:,:,:] = x[:,:,:]
    # ...

    # ... compute norms
    l2_error = l2norm_h.assemble(F=phi)
    h1_error = h1norm_h.assemble(F=phi)
    print('> l2_error = ', l2_error)
    print('> h1_error = ', h1_error)

#    expected_l2_error =  0.002108675850460567
#    expected_h1_error =  0.049398529195520964
#
#    assert( abs(l2_error - expected_l2_error) < 1.e-7)
#    assert( abs(h1_error - expected_h1_error) < 1.e-7)
    # ...


###############################################
if __name__ == '__main__':

    test_api_poisson_3d_dirneu_identity_2()