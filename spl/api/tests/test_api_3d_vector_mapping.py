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
mesh_dir = os.path.join(base_dir, 'mesh')

domain = Domain('\Omega', dim=3)


def test_api_vector_laplace_3d_dir_analytical_collela():

    # ... abstract model
    mapping = Mapping('M', rdim=3, domain=domain)

    U = VectorFunctionSpace('U', domain)
    V = VectorFunctionSpace('V', domain)

    B1 = Boundary(r'\Gamma_1', domain)
    B2 = Boundary(r'\Gamma_2', domain)
    B3 = Boundary(r'\Gamma_3', domain)
    B4 = Boundary(r'\Gamma_4', domain)
    B5 = Boundary(r'\Gamma_5', domain)
    B6 = Boundary(r'\Gamma_6', domain)

    x,y,z = domain.coordinates

    F = VectorField(V, name='F')

    v = VectorTestFunction(V, name='v')
    u = VectorTestFunction(U, name='u')

    expr = inner(grad(v), grad(u))
    a = BilinearForm((v,u), expr, mapping=mapping)

    f1 = 3*pi**2*sin(pi*x)*sin(pi*y)*sin(pi*z)
    f2 = 3*pi**2*sin(pi*x)*sin(pi*y)*sin(pi*z)
    f3 = 3*pi**2*sin(pi*x)*sin(pi*y)*sin(pi*z)
    f = Tuple(f1, f2, f3)
    expr = dot(f, v)
    l = LinearForm(v, expr, mapping=mapping)

    f1 = sin(pi*x)*sin(pi*y)*sin(pi*z)
    f2 = sin(pi*x)*sin(pi*y)*sin(pi*z)
    f3 = sin(pi*x)*sin(pi*y)*sin(pi*z)
    f = Tuple(f1, f2, f3)
    error = Matrix([F[0]-f[0], F[1]-f[1], F[2]-f[2]])
    l2norm = Norm(error, domain, kind='l2', name='u', mapping=mapping)
    h1norm = Norm(error, domain, kind='h1', name='u', mapping=mapping)

    bc = [DirichletBC(i) for i in [B1, B2, B3, B4, B5, B6]]
    equation = Equation(a(v,u), l(v), bc=bc)
    # ...

    # ... discrete spaces
    Vh, mapping = fem_context(os.path.join(mesh_dir, 'collela_3d.h5'))
    Vh = ProductFemSpace(Vh, Vh, Vh)
    # ...

    # ... dsicretize the equation using Dirichlet bc
    B1 = DiscreteBoundary(B1, axis=0, ext=-1)
    B2 = DiscreteBoundary(B2, axis=0, ext= 1)
    B3 = DiscreteBoundary(B3, axis=1, ext=-1)
    B4 = DiscreteBoundary(B4, axis=1, ext= 1)
    B5 = DiscreteBoundary(B5, axis=2, ext=-1)
    B6 = DiscreteBoundary(B6, axis=2, ext= 1)

    bc = [DiscreteDirichletBC(i) for i in [B1, B2, B3, B4, B5, B6]]
    equation_h = discretize(equation, [Vh, Vh], mapping, bc=bc)
    # ...

    # ... discretize norms
    l2norm_h = discretize(l2norm, Vh, mapping)
    h1norm_h = discretize(h1norm, Vh, mapping)
    # ...

    # ... solve the discrete equation
    x = equation_h.solve(settings={'solver':'cg', 'tol':1e-13, 'maxiter':1000,
                                   'verbose':False})
    # ...

    # ...
    phi = VectorFemField( Vh, 'phi' )
    phi.coeffs[0][:,:,:] = x[0][:,:,:]
    phi.coeffs[1][:,:,:] = x[1][:,:,:]
    phi.coeffs[2][:,:,:] = x[2][:,:,:]
    # ...

    # ... compute norms
    l2_error = l2norm_h.assemble(F=phi)
    h1_error = h1norm_h.assemble(F=phi)

    expected_l2_error =  1.5005652609706435
    expected_h1_error =  13.894218155165344

    assert( abs(l2_error - expected_l2_error) < 1.e-7)
    assert( abs(h1_error - expected_h1_error) < 1.e-7)
    # ...


#==============================================================================
# CLEAN UP SYMPY NAMESPACE
#==============================================================================

def teardown_module():
    from sympy import cache
    cache.clear_cache()