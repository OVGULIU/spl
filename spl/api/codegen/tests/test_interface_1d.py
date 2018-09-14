# coding: utf-8

import os

from sympy import Symbol
from sympy.core.containers import Tuple
from sympy import symbols
from sympy import IndexedBase
from sympy import Matrix
from sympy import Function
from sympy import pi, cos, sin
from sympy import S

from sympde.core import dx, dy, dz
from sympde.core import Constant
from sympde.core import Field
from sympde.core import grad, dot, inner, cross, rot, curl, div
from sympde.core import FunctionSpace
from sympde.core import TestFunction
from sympde.core import VectorTestFunction
from sympde.core import BilinearForm, LinearForm, Integral
from sympde.core import Mapping
from sympde.core import Domain
from sympde.core import Boundary, trace_0, trace_1
from sympde.core import evaluate

from spl.api.codegen.ast import Kernel
from spl.api.codegen.ast import Assembly
from spl.api.codegen.ast import Interface
from spl.api.codegen.printing import pycode

sanitize = lambda txt: os.linesep.join([s for s in txt.splitlines() if s.strip()])

DEBUG = False
DIM = 1

domain = Domain('\Omega', dim=DIM)

def test_interface_bilinear_1d_scalar_1(mapping=False):
    print('============ test_interface_bilinear_1d_scalar_1 =============')

    if mapping: mapping = Mapping('M', rdim=DIM, domain=domain)

    U = FunctionSpace('U', domain)
    V = FunctionSpace('V', domain)

    v = TestFunction(V, name='v')
    u = TestFunction(U, name='u')

    expr = dot(grad(v), grad(u))
    a = BilinearForm((v,u), expr, mapping=mapping)

    kernel_expr = evaluate(a)
    kernel = Kernel(a, kernel_expr, name='kernel')
    assembly = Assembly(kernel, name='assembly')
    interface = Interface(assembly, name='interface')
    code = pycode(interface)
    if DEBUG: print(code)

def test_interface_bilinear_1d_scalar_2(mapping=False):
    print('============ test_interface_bilinear_1d_scalar_2 =============')

    if mapping: mapping = Mapping('M', rdim=DIM, domain=domain)

    U = FunctionSpace('U', domain)
    V = FunctionSpace('V', domain)

    v = TestFunction(V, name='v')
    u = TestFunction(U, name='u')

    c = Constant('c', real=True, label='mass stabilization')

    expr = dot(grad(v), grad(u)) + c*v*u
    a = BilinearForm((v,u), expr, mapping=mapping)

    kernel_expr = evaluate(a)
    kernel = Kernel(a, kernel_expr, name='kernel')
    assembly = Assembly(kernel, name='assembly')
    interface = Interface(assembly, name='interface')
    code = pycode(interface)
    if DEBUG: print(code)

def test_interface_bilinear_1d_scalar_3(mapping=False):
    print('============ test_interface_bilinear_1d_scalar_3 =============')

    if mapping: mapping = Mapping('M', rdim=DIM, domain=domain)

    U = FunctionSpace('U', domain)
    V = FunctionSpace('V', domain)

    v = TestFunction(V, name='v')
    u = TestFunction(U, name='u')

    F = Field('F', space=V)

    expr = dot(grad(v), grad(u)) + F*v*u
    a = BilinearForm((v,u), expr, mapping=mapping)

    kernel_expr = evaluate(a)
    kernel = Kernel(a, kernel_expr, name='kernel')
    assembly = Assembly(kernel, name='assembly')
    interface = Interface(assembly, name='interface')
    code = pycode(interface)
    if DEBUG: print(code)

def test_interface_bilinear_1d_scalar_4(mapping=False):
    print('============ test_interface_bilinear_1d_scalar_4 =============')

    if mapping: mapping = Mapping('M', rdim=DIM, domain=domain)

    U = FunctionSpace('U', domain)
    V = FunctionSpace('V', domain)

    v = TestFunction(V, name='v')
    u = TestFunction(U, name='u')

    F = Field('F', space=V)
    G = Field('G', space=V)

    expr = dot(grad(G*v), grad(u)) + F*v*u
    a = BilinearForm((v,u), expr, mapping=mapping)

    kernel_expr = evaluate(a)
    kernel = Kernel(a, kernel_expr, name='kernel')
    assembly = Assembly(kernel, name='assembly')
    interface = Interface(assembly, name='interface')
    code = pycode(interface)
    if DEBUG: print(code)

def test_interface_bilinear_1d_scalar_5(mapping=False):
    print('============ test_interface_bilinear_1d_scalar_5 =============')

    if mapping: mapping = Mapping('M', rdim=DIM, domain=domain)

    B1 = Boundary(r'\Gamma_1', domain)

    U = FunctionSpace('U', domain)
    V = FunctionSpace('V', domain)

    v = TestFunction(V, name='v')
    u = TestFunction(U, name='u')

    expr = dot(grad(v), grad(u))
    a_0 = BilinearForm((v,u), expr, mapping=mapping, name='a_0')

    expr = v*trace_1(grad(u), B1)
    a_bnd = BilinearForm((v, u), expr, mapping=mapping, name='a_bnd')

    expr = a_0(v,u) + a_bnd(v,u)
    a = BilinearForm((v,u), expr, mapping=mapping, name='a')

    kernel_expr = evaluate(a)
    kernel_bnd = Kernel(a, kernel_expr, target=B1, discrete_boundary=(1, -1), name='kernel_bnd')
    kernel_int = Kernel(a, kernel_expr, target=domain, name='kernel_int')
    assembly_bnd = Assembly(kernel_bnd, name='assembly_bnd')
    assembly_int = Assembly(kernel_int, name='assembly_int')
    interface_bnd = Interface(assembly_bnd, name='interface_bnd')
    interface_int = Interface(assembly_int, name='interface_int')
    for interface in [interface_int, interface_bnd]:
        code = pycode(interface)
        if DEBUG: print(code)

def test_interface_bilinear_1d_block_1(mapping=False):
    print('============ test_interface_bilinear_1d_block_1 =============')

    if mapping: mapping = Mapping('M', rdim=DIM, domain=domain)

    # 1d wave problem

    U = FunctionSpace('U', domain)
    V = FunctionSpace('V', domain)

    # trial functions
    u = TestFunction(U, name='u')
    f = TestFunction(V, name='f')

    # test functions
    v = TestFunction(U, name='v')
    w = TestFunction(V, name='w')

    rho = Constant('rho', real=True, label='mass density')
    dt = Constant('dt', real=True, label='time step')

    mass = BilinearForm((v,u), v*u, mapping=mapping, name='m')
    adv  = BilinearForm((v,u), dx(v)*u, mapping=mapping, name='adv')

    expr = rho*mass(v,u) + dt*adv(v, f) + dt*adv(w,u) + mass(w,f)
    a = BilinearForm(((v,w), (u,f)), expr, mapping=mapping, name='a')

    kernel_expr = evaluate(a)
    kernel = Kernel(a, kernel_expr, name='kernel')
    assembly = Assembly(kernel, name='assembly')
    interface = Interface(assembly, name='interface')
    code = pycode(interface)
    if DEBUG: print(code)

def test_interface_linear_1d_scalar_1(mapping=False):
    print('============ test_interface_linear_1d_scalar_1 =============')

    if mapping: mapping = Mapping('M', rdim=DIM, domain=domain)

    V = FunctionSpace('V', domain)
    x = V.coordinates

    v = TestFunction(V, name='v')

    expr = cos(2*pi*x)*v
    a = LinearForm(v, expr, mapping=mapping)

    kernel_expr = evaluate(a)
    kernel = Kernel(a, kernel_expr, name='kernel')
    assembly = Assembly(kernel, name='assembly')
    interface = Interface(assembly, name='interface')
    code = pycode(interface)
    if DEBUG: print(code)

def test_interface_linear_1d_scalar_2(mapping=False):
    print('============ test_interface_linear_1d_scalar_2 =============')

    if mapping: mapping = Mapping('M', rdim=DIM, domain=domain)

    V = FunctionSpace('V', domain)
    x = V.coordinates

    v = TestFunction(V, name='v')

    c = Constant('c', real=True, label='mass stabilization')

    expr = c*cos(2*pi*x)*v
    a = LinearForm(v, expr, mapping=mapping)

    kernel_expr = evaluate(a)
    kernel = Kernel(a, kernel_expr, name='kernel')
    assembly = Assembly(kernel, name='assembly')
    interface = Interface(assembly, name='interface')
    code = pycode(interface)
    if DEBUG: print(code)

def test_interface_linear_1d_scalar_3(mapping=False):
    print('============ test_interface_linear_1d_scalar_3 =============')

    if mapping: mapping = Mapping('M', rdim=DIM, domain=domain)

    V = FunctionSpace('V', domain)
    x = V.coordinates

    v = TestFunction(V, name='v')

    F = Field('F', space=V)

    expr = F*v
    a = LinearForm(v, expr, mapping=mapping)

    kernel_expr = evaluate(a)
    kernel = Kernel(a, kernel_expr, name='kernel')
    assembly = Assembly(kernel, name='assembly')
    interface = Interface(assembly, name='interface')
    code = pycode(interface)
    if DEBUG: print(code)

def test_interface_linear_1d_scalar_4(mapping=False):
    print('============ test_interface_linear_1d_scalar_4 =============')

    if mapping: mapping = Mapping('M', rdim=DIM, domain=domain)

    V = FunctionSpace('V', domain)
    x = V.coordinates

    v = TestFunction(V, name='v')

    F = Field('F', space=V)

    expr = dx(F)*v
    a = LinearForm(v, expr, mapping=mapping)

    kernel_expr = evaluate(a)
    kernel = Kernel(a, kernel_expr, name='kernel')
    assembly = Assembly(kernel, name='assembly')
    interface = Interface(assembly, name='interface')
    code = pycode(interface)
    if DEBUG: print(code)

def test_interface_function_1d_scalar_1(mapping=False):
    print('============ test_interface_function_1d_scalar_1 =============')

    if mapping: mapping = Mapping('M', rdim=DIM, domain=domain)

    V = FunctionSpace('V', domain)
    x = V.coordinates

    expr = S.One
    a = Integral(expr, domain, coordinates=[x], mapping=mapping)

    kernel_expr = evaluate(a)
    kernel = Kernel(a, kernel_expr, name='kernel')
    assembly = Assembly(kernel, name='assembly')
    interface = Interface(assembly, name='interface')
    code = pycode(interface)
    if DEBUG: print(code)

def test_interface_function_1d_scalar_2(mapping=False):
    print('============ test_interface_function_1d_scalar_2 =============')

    if mapping: mapping = Mapping('M', rdim=DIM, domain=domain)

    V = FunctionSpace('V', domain)
    x = V.coordinates

    F = Field('F', space=V)

    expr = F-cos(2*pi*x)
    a = Integral(expr, domain, coordinates=[x], mapping=mapping)

    kernel_expr = evaluate(a)
    kernel = Kernel(a, kernel_expr, name='kernel')
    assembly = Assembly(kernel, name='assembly')
    interface = Interface(assembly, name='interface')
    code = pycode(interface)
    if DEBUG: print(code)

def test_interface_function_1d_scalar_3(mapping=False):
    print('============ test_interface_function_1d_scalar_3 =============')

    if mapping: mapping = Mapping('M', rdim=DIM, domain=domain)

    V = FunctionSpace('V', domain)
    x = V.coordinates

    F = Field('F', space=V)

    error = F-cos(2*pi*x)
    expr = dot(grad(error), grad(error))
    a = Integral(expr, domain, coordinates=[x], mapping=mapping)

    kernel_expr = evaluate(a)
    kernel = Kernel(a, kernel_expr, name='kernel')
    assembly = Assembly(kernel, name='assembly')
    interface = Interface(assembly, name='interface')
    code = pycode(interface)
    if DEBUG: print(code)

#................................
if __name__ == '__main__':

#    test_interface_bilinear_1d_scalar_5(mapping=False)

    # .................................
    # without mapping
    test_interface_bilinear_1d_scalar_1(mapping=False)
    test_interface_bilinear_1d_scalar_2(mapping=False)
    test_interface_bilinear_1d_scalar_3(mapping=False)
    test_interface_bilinear_1d_scalar_4(mapping=False)
#    test_interface_bilinear_1d_scalar_5(mapping=False)
    test_interface_bilinear_1d_block_1(mapping=False)

    # with mapping
    test_interface_bilinear_1d_scalar_1(mapping=True)
    test_interface_bilinear_1d_scalar_2(mapping=True)
    test_interface_bilinear_1d_scalar_3(mapping=True)
    test_interface_bilinear_1d_scalar_4(mapping=True)
#    test_interface_bilinear_1d_scalar_5(mapping=True)
    test_interface_bilinear_1d_block_1(mapping=True)
    # .................................

    # .................................
    # without mapping
    test_interface_linear_1d_scalar_1(mapping=False)
    test_interface_linear_1d_scalar_2(mapping=False)
    test_interface_linear_1d_scalar_3(mapping=False)
    test_interface_linear_1d_scalar_4(mapping=False)

    # with mapping
    test_interface_linear_1d_scalar_1(mapping=True)
    test_interface_linear_1d_scalar_2(mapping=True)
    test_interface_linear_1d_scalar_3(mapping=True)
    test_interface_linear_1d_scalar_4(mapping=True)
    # .................................

    # .................................
    # without mapping
    test_interface_function_1d_scalar_1(mapping=False)
    test_interface_function_1d_scalar_2(mapping=False)
    test_interface_function_1d_scalar_3(mapping=False)

    # with mapping
    test_interface_function_1d_scalar_1(mapping=True)
    test_interface_function_1d_scalar_2(mapping=True)
    test_interface_function_1d_scalar_3(mapping=True)
    # .................................