# TODO - in pycode, when printing a For loop, we should check if end == start + 1
#        in which case, we shall replace the For statement by its body and subs
#        the iteration index by its value (start)

from collections import OrderedDict
from itertools import groupby
import string
import random
import numpy as np

from sympy import Basic
from sympy import symbols, Symbol, IndexedBase, Indexed, Function
from sympy import Mul, Add, Tuple
from sympy import Matrix, ImmutableDenseMatrix
from sympy import sqrt as sympy_sqrt
from sympy import S as sympy_S

from pyccel.ast.core import Variable, IndexedVariable
from pyccel.ast.core import For
from pyccel.ast.core import Assign
from pyccel.ast.core import AugAssign
from pyccel.ast.core import Slice
from pyccel.ast.core import Range
from pyccel.ast.core import FunctionDef
from pyccel.ast.core import FunctionCall
from pyccel.ast.core import Import
from pyccel.ast import Zeros
from pyccel.ast import Import
from pyccel.ast import DottedName
from pyccel.ast import Nil
from pyccel.ast import Len
from pyccel.ast import If, Is, Return
from pyccel.ast import String, Print, Shape
from pyccel.ast import Comment, NewLine
from pyccel.parser.parser import _atomic
from pyccel.ast.utilities import build_types_decorator
from pyccel.ast.utilities import variables, indexed_variables

from sympde.core import grad
from sympde.core import Constant
from sympde.core import Mapping
from sympde.core import Field
from sympde.core import Boundary, BoundaryVector, NormalVector, TangentVector
from sympde.core import Covariant, Contravariant
from sympde.core import BilinearForm, LinearForm, Integral, BasicForm
from sympde.core.derivatives import _partial_derivatives
from sympde.core.derivatives import get_max_partial_derivatives
from sympde.core.space import FunctionSpace
from sympde.core.space import TestFunction
from sympde.core.space import VectorTestFunction
from sympde.core.space import IndexedTestTrial
from sympde.core.space import Trace
from sympde.printing.pycode import pycode  # TODO remove from here
from sympde.core.derivatives import print_expression
from sympde.core.derivatives import get_atom_derivatives
from sympde.core.derivatives import get_index_derivatives
from sympde.core.math import math_atoms_as_str

FunctionalForms = (BilinearForm, LinearForm, Integral)

def random_string( n ):
    chars    = string.ascii_lowercase + string.digits
    selector = random.SystemRandom()
    return ''.join( selector.choice( chars ) for _ in range( n ) )

def compute_normal_vector(vector, discrete_boundary, mapping):
    dim = len(vector)
    pdim = dim - len(discrete_boundary)
    if len(discrete_boundary) > 1: raise NotImplementedError('TODO')

    face = discrete_boundary[0]
    axis = face[0] ; ext = face[1]

    body = []

    if not mapping:

        values = np.zeros(dim)
        values[axis] = ext

    else:
        M = mapping
        inv_jac = Symbol('inv_jac')

        # ... construct jacobian on manifold
        lines = []
        n_row,n_col = M.jacobian.shape
        range_row = [i for i in range(0,n_row) if not(i == axis)]
        range_col = range(0,n_col)
        for i_row in range_row:
            line = []
            for i_col in range_col:
                line.append(M.jacobian[i_row, i_col])

            lines.append(line)

        J = Matrix(lines)
        # ...

        # ...
        ops = _partial_derivatives[:dim]
        elements = [d(M[i]) for d in ops for i in range(0, dim)]
        for e in elements:
            new = print_expression(e, mapping_name=False)
            new = Symbol(new)
            J = J.subs(e, new)
        # ...

        if dim == 1:
            raise NotImplementedError('TODO')

        elif dim == 2:
            J = J[0,:]
            # TODO shall we use sympy_sqrt here? is there any difference in
            # Fortran between sqrt and Pow(, 1/2)?
            j = (sum(J[i]**2 for i in range(0, dim)))**(1/2)

            values = [inv_jac*J[1], -inv_jac*J[0]]

        elif dim == 3:
            raise NotImplementedError('TODO')

        values = [ext*i for i in values]

        body += [Assign(inv_jac, 1/j)]

    for i in range(0, dim):
        body += [Assign(vector[i], values[i])]

    return body

def compute_tangent_vector(vector, discrete_boundary, mapping):
    raise NotImplementedError('TODO')


def filter_loops(indices, ranges, body, discrete_boundary, boundary_basis=False):

    quad_mask = []
    quad_ext = []
    if discrete_boundary:
        # TODO improve using namedtuple or a specific class ? to avoid the 0 index
        #      => make it easier to understand
        quad_mask = [i[0] for i in discrete_boundary]
        quad_ext  = [i[1] for i in discrete_boundary]

        # discrete_boundary gives the perpendicular indices, then we need to
        # remove them from directions

    dim = len(indices)
    for i in range(dim-1,-1,-1):
        rx = ranges[i]
        x = indices[i]
        start = rx.start
        end   = rx.stop

        if i in quad_mask:
            i_index = quad_mask.index(i)
            ext = quad_ext[i_index]
            if ext == -1:
                end = start + 1

            elif ext == 1:
                start = end - 1
            else:
                raise ValueError('> Wrong value for ext. It should be -1 or 1')

        rx = Range(start, end)
        body = [For(x, rx, body)]

    return body

def filter_product(indices, args, discrete_boundary):

    mask = []
    ext = []
    if discrete_boundary:
        # TODO improve using namedtuple or a specific class ? to avoid the 0 index
        #      => make it easier to understand
        mask = [i[0] for i in discrete_boundary]
        ext  = [i[1] for i in discrete_boundary]

        # discrete_boundary gives the perpendicular indices, then we need to
        # remove them from directions

    dim = len(indices)
    args = [args[i][indices[i]] for i in range(dim) if not(i in mask)]

    return Mul(*args)

def compute_atoms_expr(atom, indices_quad, indices_test,
                       indices_trial, basis_trial,
                       basis_test, cords, test_function,
                       is_linear,
                       mapping):

    cls = (_partial_derivatives,
           VectorTestFunction,
           TestFunction,
           IndexedTestTrial)

    dim  = len(indices_test)

    if not isinstance(atom, cls):
        raise TypeError('atom must be of type {}'.format(str(cls)))

    orders = [0 for i in range(0, dim)]
    p_indices = get_index_derivatives(atom)
#    print('> atom = ', atom)
#    print('> test_function = ', test_function)
    test = False
    if isinstance(atom, _partial_derivatives):
        orders[atom.grad_index] = p_indices[atom.coordinate]
        if isinstance( test_function, TestFunction ):
            test      = test_function in atom.atoms(TestFunction)

        elif isinstance( test_function, VectorTestFunction ):
            test      = test_function in atom.atoms(VectorTestFunction)

        else:
            raise TypeError('> Expecting TestFunction or VectorTestFunction')
    else:
        if (isinstance( atom, TestFunction ) and
            isinstance( test_function, TestFunction )):
            test      = atom == test_function

        elif (isinstance( atom, VectorTestFunction ) and
              isinstance( test_function, VectorTestFunction )):
            test      = atom.base == test_function.base

    if test or is_linear:
        basis  = basis_test
        idxs   = indices_test
    else:
        basis  = basis_trial
        idxs   = indices_trial

    args = []
    for i in range(dim):
        args.append(basis[i][idxs[i],orders[i],indices_quad[i]])

    # ... assign basis on quad point
    logical = not( mapping is None )
    name = print_expression(atom, logical=logical)
    assign = Assign(Symbol(name), Mul(*args))
    # ...

    # ... map basis function
    map_stmts = []
    if mapping and  isinstance(atom, _partial_derivatives):
        name = print_expression(atom)

        a = get_atom_derivatives(atom)

        M = mapping
        dim = M.rdim
        ops = _partial_derivatives[:dim]

        # ... gradient
        lgrad_B = [d(a) for d in ops]
        grad_B = Covariant(mapping, lgrad_B)
        rhs = grad_B[atom.grad_index]

        # update expression
        elements = [d(M[i]) for d in ops for i in range(0, dim)]
        for e in elements:
            new = print_expression(e, mapping_name=False)
            new = Symbol(new)
            rhs = rhs.subs(e, new)

        for e in lgrad_B:
            new = print_expression(e, logical=True)
            new = Symbol(new)
            rhs = rhs.subs(e, new)
        # ...

        map_stmts += [Assign(Symbol(name), rhs)]
        # ...
    # ...

    return assign, map_stmts

def compute_atoms_expr_field(atom, indices_quad,
                            idxs, basis,
                            test_function):

    if not is_field(atom):
        raise TypeError('atom must be a field expr')

    field = list(atom.atoms(Field))[0]
    field_name = 'coeff_'+str(field.name)

    # ...
    if isinstance(atom, _partial_derivatives):
        direction = atom.grad_index + 1

    else:
        direction = 0
    # ...

    # ...
    test_function = atom.subs(field, test_function)
    name = print_expression(test_function)
    test_function = Symbol(name)
    # ...

    # ...
    args = []
    dim  = len(idxs)
    for i in range(dim):
        if direction == i+1:
            args.append(basis[i][idxs[i],1,indices_quad[i]])

        else:
            args.append(basis[i][idxs[i],0,indices_quad[i]])

    init = Assign(test_function, Mul(*args))
    # ...

    # ...
    args = [IndexedBase(field_name)[idxs], test_function]
    val_name = print_expression(atom) + '_values'
    val  = IndexedBase(val_name)[indices_quad]
    update = AugAssign(val,'+',Mul(*args))
    # ...

    return init, update

def compute_atoms_expr_mapping(atom, indices_quad,
                               idxs, basis,
                               test_function):

    _print = lambda i: print_expression(i, mapping_name=False)

    element = get_atom_derivatives(atom)
    element_name = 'coeff_' + _print(element)

    # ...
    if isinstance(atom, _partial_derivatives):
        direction = atom.grad_index + 1

    else:
        direction = 0
    # ...

    # ...
    test_function = atom.subs(element, test_function)
    name = print_expression(test_function, logical=True)
    test_function = Symbol(name)
    # ...

    # ...
    args = []
    dim  = len(idxs)
    for i in range(dim):
        if direction == i+1:
            args.append(basis[i][idxs[i],1,indices_quad[i]])

        else:
            args.append(basis[i][idxs[i],0,indices_quad[i]])

    init = Assign(test_function, Mul(*args))
    # ...

    # ...
    args = [IndexedBase(element_name)[idxs], test_function]
    val_name = _print(atom) + '_values'
    val  = IndexedBase(val_name)[indices_quad]
    update = AugAssign(val,'+',Mul(*args))
    # ...

    return init, update

def is_field(expr):

    if isinstance(expr, _partial_derivatives):
        return is_field(expr.args[0])

    elif isinstance(expr, Field):
        return True

    return False

class SplBasic(Basic):
    _discrete_boundary = None

    def __new__(cls, tag, name=None, prefix=None, debug=False, detailed=False):

        if name is None:
            if prefix is None:
                raise ValueError('prefix must be given')

            name = '{prefix}_{tag}'.format(tag=tag, prefix=prefix)

        obj = Basic.__new__(cls)
        obj._name = name
        obj._tag = tag
        obj._dependencies = []
        obj._debug = debug
        obj._detailed = detailed

        return obj

    @property
    def name(self):
        return self._name

    @property
    def tag(self):
        return self._tag

    @property
    def func(self):
        return self._func

    @property
    def basic_args(self):
        return self._basic_args

    @property
    def dependencies(self):
        return self._dependencies

    @property
    def debug(self):
        return self._debug

    @property
    def detailed(self):
        return self._detailed

    @property
    def discrete_boundary(self):
        return self._discrete_boundary

class EvalMapping(SplBasic):

    def __new__(cls, space, mapping, discrete_boundary=None, name=None, boundary_basis=None, nderiv=1):

        if not isinstance(mapping, Mapping):
            raise TypeError('> Expecting a Mapping object')

        obj = SplBasic.__new__(cls, mapping, name=name, prefix='eval_mapping')

        obj._space = space
        obj._mapping = mapping
        obj._discrete_boundary = discrete_boundary
        obj._boundary_basis = boundary_basis

        dim = mapping.rdim

        # ...
        lcoords = ['x1', 'x2', 'x3'][:dim]
        obj._lcoords = symbols(lcoords)
        # ...

        # ...
        ops = _partial_derivatives[:dim]
        M = mapping

        components = [M[i] for i in range(0, dim)]
        elements = list(components)

        if nderiv > 0:
            elements += [d(M[i]) for d in ops for i in range(0, dim)]

        if nderiv > 1:
            elements += [d1(d2(M[i])) for e,d1 in enumerate(ops)
                                      for d2 in ops[:e+1]
                                      for i in range(0, dim)]

        if nderiv > 2:
            raise NotImplementedError('TODO')

        obj._elements = tuple(elements)

        obj._components = tuple(components)
        # ...

        obj._func = obj._initialize()

        return obj

    @property
    def space(self):
        return self._space

    @property
    def mapping(self):
        return self._mapping

    @property
    def boundary_basis(self):
        return self._boundary_basis

    @property
    def lcoords(self):
        return self._lcoords

    @property
    def elements(self):
        return self._elements

    @property
    def components(self):
        return self._components

    @property
    def mapping_coeffs(self):
        return self._mapping_coeffs

    @property
    def mapping_values(self):
        return self._mapping_values

    def build_arguments(self, data):

        other = data

        return self.basic_args + other

    def _initialize(self):
        space = self.space
        dim = space.ldim

        _print = lambda i: print_expression(i, mapping_name=False)
        mapping_atoms = [_print(f) for f in self.components]
        mapping_str = [_print(f) for f in self.elements]

        # ... declarations
        degrees        = variables([ 'p{}'.format(i) for i in range(1, dim+1)], 'int')
        orders         = variables([ 'k{}'.format(i) for i in range(1, dim+1)], 'int')
        indices_basis  = variables([ 'jl{}'.format(i) for i in range(1, dim+1)], 'int')
        indices_quad   = variables([ 'g{}'.format(i) for i in range(1, dim+1)], 'int')
        basis          = indexed_variables(['basis{}'.format(i) for i in range(1, dim+1)],
                                          dtype='real', rank=3)
        mapping_coeffs = indexed_variables(['coeff_{}'.format(f) for f in mapping_atoms],
                                          dtype='real', rank=dim)
        mapping_values = indexed_variables(['{}_values'.format(f) for f in mapping_str],
                                          dtype='real', rank=dim)
        # ...

        # ... ranges
        ranges_basis = [Range(degrees[i]+1) for i in range(dim)]
        ranges_quad  = [Range(orders[i]) for i in range(dim)]
        # ...

        # ... basic arguments
        self._basic_args = (orders)
        # ...

        # ...
        self._mapping_coeffs = mapping_coeffs
        self._mapping_values    = mapping_values
        # ...

        # ...
        Nj = TestFunction(space, name='Nj')
        body = []
        init_basis = OrderedDict()
        updates = []
        for atom in self.elements:
            init, update = compute_atoms_expr_mapping(atom, indices_quad,
                                                      indices_basis, basis, Nj)

            updates.append(update)

            basis_name = str(init.lhs)
            init_basis[basis_name] = init

        init_basis = OrderedDict(sorted(init_basis.items()))
        body += list(init_basis.values())
        body += updates
        # ...

        # put the body in tests for loops
        body = filter_loops(indices_basis, ranges_basis, body,
                            self.discrete_boundary,
                            boundary_basis=self.boundary_basis)

        # put the body in for loops of quadrature points
        body = filter_loops(indices_quad, ranges_quad, body,
                            self.discrete_boundary,
                            boundary_basis=self.boundary_basis)

        # initialization of the matrix
        init_vals = [f[[Slice(None,None)]*dim] for f in mapping_values]
        init_vals = [Assign(e, 0.0) for e in init_vals]
        body =  init_vals + body

        func_args = self.build_arguments(degrees + basis + mapping_coeffs + mapping_values)

        decorators = {'types': build_types_decorator(func_args)}
        return FunctionDef(self.name, list(func_args), [], body,
                           decorators=decorators)

class EvalField(SplBasic):

    def __new__(cls, space, fields, discrete_boundary=None, name=None, boundary_basis=None):

        if not isinstance(fields, (tuple, list, Tuple)):
            raise TypeError('> Expecting an iterable')

        obj = SplBasic.__new__(cls, space, name=name, prefix='eval_field')

        obj._space = space
        obj._fields = Tuple(*fields)
        obj._discrete_boundary = discrete_boundary
        obj._boundary_basis = boundary_basis
        obj._func = obj._initialize()

        return obj

    @property
    def space(self):
        return self._space

    @property
    def fields(self):
        return self._fields

    @property
    def boundary_basis(self):
        return self._boundary_basis

    def build_arguments(self, data):

        other = data

        return self.basic_args + other

    def _initialize(self):
        space = self.space
        dim = space.ldim

        field_atoms = self.fields.atoms(Field)
        fields_str = [print_expression(f) for f in self.fields]

        # ... declarations
        degrees       = variables([ 'p{}'.format(i) for i in range(1, dim+1)], 'int')
        orders        = variables([ 'k{}'.format(i) for i in range(1, dim+1)], 'int')
        indices_basis = variables([ 'jl{}'.format(i) for i in range(1, dim+1)], 'int')
        indices_quad  = variables([ 'g{}'.format(i) for i in range(1, dim+1)], 'int')
        basis         = indexed_variables(['basis{}'.format(i) for i in range(1, dim+1)],
                                          dtype='real', rank=3)
        fields_coeffs = indexed_variables(['coeff_{}'.format(f) for f in field_atoms],
                                          dtype='real', rank=dim)
        fields_val    = indexed_variables(['{}_values'.format(f) for f in fields_str],
                                          dtype='real', rank=dim)
        # ...

        # ... ranges
        ranges_basis = [Range(degrees[i]+1) for i in range(dim)]
        ranges_quad  = [Range(orders[i]) for i in range(dim)]
        # ...

        # ... basic arguments
        self._basic_args = (orders)
        # ...

        # ...
        Nj = TestFunction(space, name='Nj')
        body = []
        init_basis = OrderedDict()
        updates = []
        for atom in self.fields:
            init, update = compute_atoms_expr_field(atom, indices_quad, indices_basis,
                                                    basis, Nj)

            updates.append(update)

            basis_name = str(init.lhs)
            init_basis[basis_name] = init

        init_basis = OrderedDict(sorted(init_basis.items()))
        body += list(init_basis.values())
        body += updates
        # ...

        # put the body in tests for loops
        body = filter_loops(indices_basis, ranges_basis, body,
                            self.discrete_boundary,
                            boundary_basis=self.boundary_basis)

        # put the body in for loops of quadrature points
        body = filter_loops(indices_quad, ranges_quad, body,
                            self.discrete_boundary,
                            boundary_basis=self.boundary_basis)

        # initialization of the matrix
        init_vals = [f[[Slice(None,None)]*dim] for f in fields_val]
        init_vals = [Assign(e, 0.0) for e in init_vals]
        body =  init_vals + body

        func_args = self.build_arguments(degrees + basis + fields_coeffs + fields_val)

        decorators = {'types': build_types_decorator(func_args)}
        return FunctionDef(self.name, list(func_args), [], body,
                           decorators=decorators)

# target is used when there are multiple expression (domain/boundaries)
class Kernel(SplBasic):

    def __new__(cls, weak_form, kernel_expr, target=None,
                discrete_boundary=None, name=None, boundary_basis=None):

        if not isinstance(weak_form, FunctionalForms):
            raise TypeError('> Expecting a weak formulation')

        # ...
        # get the target expr if there are multiple expressions (domain/boundary)
        on_boundary = False
        if target is None:
            if len(kernel_expr) > 1:
                msg = '> weak form has multiple expression, but no target was given'
                raise ValueError(msg)

            e = kernel_expr[0]
            on_boundary = isinstance(e.target, Boundary)
            kernel_expr = e.expr

        else:
            ls = [i for i in kernel_expr if i.target is target]
            e = ls[0]
            on_boundary = isinstance(e.target, Boundary)
            kernel_expr = e.expr
        # ...

        # ...
        if discrete_boundary:
            if not isinstance(discrete_boundary, (tuple, list)):
                raise TypeError('> Expecting a tuple or list for discrete_boundary')

            discrete_boundary = list(discrete_boundary)
            if not isinstance(discrete_boundary[0], (tuple, list)):
                discrete_boundary = [discrete_boundary]
            # discrete_boundary is now a list of lists
        # ...

        # ... discrete_boundary must be given if there are Trace nodes
        if on_boundary and not discrete_boundary:
            raise ValueError('> discrete_bounary must be provided for a boundary Kernel')
        # ...

        # ... default value for boundary_basis is True if on boundary
        if on_boundary and (boundary_basis is None):
            boundary_basis = True
        # ...

        tag = random_string( 8 )
        obj = SplBasic.__new__(cls, tag, name=name, prefix='kernel')

        obj._weak_form = weak_form
        obj._kernel_expr = kernel_expr
        obj._target = target
        obj._discrete_boundary = discrete_boundary
        obj._boundary_basis = boundary_basis

        obj._func = obj._initialize()

        return obj

    @property
    def weak_form(self):
        return self._weak_form

    @property
    def kernel_expr(self):
        return self._kernel_expr

    @property
    def target(self):
        return self._target

    @property
    def boundary_basis(self):
        return self._boundary_basis

    @property
    def n_rows(self):
        return self._n_rows

    @property
    def n_cols(self):
        return self._n_cols

    @property
    def max_nderiv(self):
        return self._max_nderiv

    @property
    def constants(self):
        return self._constants

    @property
    def fields(self):
        return self._fields

    @property
    def fields_coeffs(self):
        return self._fields_coeffs

    @property
    def mapping_coeffs(self):
        if not self.eval_mapping:
            return ()

        return self.eval_mapping.mapping_coeffs

    @property
    def mapping_values(self):
        if not self.eval_mapping:
            return ()

        return self.eval_mapping.mapping_values

    @property
    def eval_fields(self):
        return self._eval_fields

    @property
    def eval_mapping(self):
        return self._eval_mapping

    def build_arguments(self, data):

        other = data

        if self.mapping_values:
            other = self.mapping_values + other

        if self.constants:
            other = other + self.constants

        return self.basic_args + other

    def _initialize(self):

        is_linear   = isinstance(self.weak_form, LinearForm)
        is_bilinear = isinstance(self.weak_form, BilinearForm)
        is_function = isinstance(self.weak_form, Integral)

        expr = self.kernel_expr

        # ...
        n_rows = 1 ; n_cols = 1
        if is_bilinear:
            if isinstance(expr, (Matrix, ImmutableDenseMatrix)):
                n_rows = expr.shape[0]
                n_cols = expr.shape[1]

        if is_linear:
            if isinstance(expr, (Matrix, ImmutableDenseMatrix)):
                n_rows = expr.shape[0]

        self._n_rows = n_rows
        self._n_cols = n_cols
        # ...

        dim      = self.weak_form.ldim
        dim_test = dim

        if is_bilinear:
            dim_trial = dim
        else:
            dim_trial = 0

        # ... coordinates
        coordinates = self.weak_form.coordinates
        if dim == 1:
            coordinates = [coordinates]
        # ...

        # ...
        constants = tuple(expr.atoms(Constant))
        self._constants = []
        # we need this, since Constant is an extension of Symbol and the type is
        # given as for sympy Symbol
        for c in constants:
            dtype = 'real'
            if c.is_integer:
                dtype = 'int'

            elif c.is_real:
                dtype = 'real'

            elif c.is_complex:
                dtype = 'complex'

            self._constants.append(Variable(dtype, str(c.name)))

        self._constants = tuple(self._constants)
        # ...

        atoms_types = (_partial_derivatives,
                       VectorTestFunction,
                       TestFunction,
                       IndexedTestTrial,
                       Field)
        atoms  = _atomic(expr, cls=atoms_types)

        atomic_expr_field = [atom for atom in atoms if is_field(atom)]
        atomic_expr       = [atom for atom in atoms if atom not in atomic_expr_field ]

        # TODO use print_expression
        fields_str    = sorted(tuple(map(pycode, atomic_expr_field)))
        field_atoms   = tuple(expr.atoms(Field))

        # ... create EvalField
        self._eval_fields = []
        if atomic_expr_field:
            keyfunc = lambda F: F.space.name
            data = sorted(field_atoms, key=keyfunc)
            for space_str, group in groupby(data, keyfunc):
                g_names = set([f.name for f in group])
                fields_expressions = []
                for e in atomic_expr_field:
                    fs = e.atoms(Field)
                    f_names = set([f.name for f in fs])
                    if f_names & g_names:
                        fields_expressions += [e]
                        space = list(fs)[0].space

                eval_field = EvalField(space, fields_expressions,
                                       discrete_boundary=self.discrete_boundary,
                                       boundary_basis=self.boundary_basis)
                self._eval_fields.append(eval_field)

        # update dependencies
        self._dependencies += self.eval_fields
        # ...

        # ...
        nderiv = 1
        if isinstance(self.kernel_expr, Matrix):
            n_rows, n_cols = self.kernel_expr.shape
            for i_row in range(0, n_rows):
                for i_col in range(0, n_cols):
                    d = get_max_partial_derivatives(self.kernel_expr[i_row,i_col])
                    nderiv = max(nderiv, max(d.values()))
        else:
            d = get_max_partial_derivatives(self.kernel_expr)
            nderiv = max(nderiv, max(d.values()))

        self._max_nderiv = nderiv
        # ...

        # ... mapping
        mapping = self.weak_form.mapping
        self._eval_mapping = None
        if mapping:

            if is_bilinear or is_linear:
                space = self.weak_form.test_spaces[0]

            elif is_function:
                space = self.weak_form.space

            eval_mapping = EvalMapping(space, mapping,
                                       discrete_boundary=self.discrete_boundary,
                                       boundary_basis=self.boundary_basis,
                                       nderiv=nderiv)
            self._eval_mapping = eval_mapping

            # update dependencies
            self._dependencies += [self.eval_mapping]
        # ...

        if is_bilinear or is_linear:
            test_function = self.weak_form.test_functions[0]

        elif is_function:
            test_function = TestFunction(self.weak_form.space, name='Nj')

        # creation of symbolic vars
        if is_bilinear:
            rank = 2*dim

        elif is_linear:
            rank = dim

        elif is_function:
            rank = 1

        if isinstance(expr, Matrix):
            sh   = expr.shape

            # ...
            mats = []
            for i_row in range(0, sh[0]):
                for i_col in range(0, sh[1]):
                    mats.append('mat_{}{}'.format(i_row, i_col))

            mats = indexed_variables(mats, dtype='real', rank=rank)
            # ...

            # ...
            v = []
            for i_row in range(0, sh[0]):
                for i_col in range(0, sh[1]):
                    v.append('v_{}{}'.format(i_row, i_col))

            v = variables(v, 'real')
            # ...

            expr = expr[:]
            ln   = len(expr)

        else:
            mats = (IndexedVariable('mat_00', dtype='real', rank=rank),)

            v    = (Variable('real', 'v_00'),)
            expr = [expr]
            ln   = 1

        # ... declarations
        fields        = symbols(fields_str)

        fields_coeffs = indexed_variables(['coeff_{}'.format(f) for f in field_atoms],
                                          dtype='real', rank=dim)
        fields_val    = indexed_variables(['{}_values'.format(f) for f in fields_str],
                                          dtype='real', rank=dim)

        test_degrees  = variables([ 'test_p{}'.format(i) for i in range(1, dim+1)], 'int')
        trial_degrees = variables(['trial_p{}'.format(i) for i in range(1, dim+1)], 'int')
        test_pads     = variables([ 'test_p{}'.format(i) for i in range(1, dim+1)], 'int')
        trial_pads    = variables(['trial_p{}'.format(i) for i in range(1, dim+1)], 'int')
        indices_quad  = variables(['g{}'.format(i) for i in range(1, dim+1)], 'int')
        qds_dim       = variables(['k{}'.format(i) for i in range(1, dim+1)], 'int')
        indices_test  = variables(['il{}'.format(i) for i in range(1, dim+1)], 'int')
        indices_trial = variables(['jl{}'.format(i) for i in range(1, dim+1)], 'int')
        wvol          = Variable('real', 'wvol')

        basis_trial   = indexed_variables(['trial_bs{}'.format(i) for i in range(1, dim+1)],
                                          dtype='real', rank=3)
        basis_test    = indexed_variables(['test_bs{}'.format(i) for i in range(1, dim+1)],
                                          dtype='real', rank=3)
        weighted_vols = indexed_variables(['w{}'.format(i) for i in range(1, dim+1)],
                                          dtype='real', rank=1)
        positions     = indexed_variables(['u{}'.format(i) for i in range(1, dim+1)],
                                          dtype='real', rank=1)

        # ...

        # ...
        if is_bilinear:
            self._basic_args = (test_pads + trial_pads +
                                basis_test + basis_trial +
                                positions + weighted_vols)

        if is_linear or is_function:
            self._basic_args = (test_pads +
                                basis_test +
                                positions + weighted_vols)
        # ...

        # ...
        mapping_elements = ()
        mapping_coeffs = ()
        mapping_values = ()
        if mapping:
            _eval = self.eval_mapping
            _print = lambda i: print_expression(i, mapping_name=False)

            mapping_elements = [_print(i) for i in _eval.elements]
            mapping_elements = symbols(tuple(mapping_elements))

            mapping_coeffs = [_print(i) for i in _eval.mapping_coeffs]
            mapping_coeffs = indexed_variables(mapping_coeffs, dtype='real', rank=dim)

            mapping_values = [_print(i) for i in _eval.mapping_values]
            mapping_values = indexed_variables(mapping_values, dtype='real', rank=dim)
        # ...

        # ...
        self._fields = fields
        self._fields_coeffs = fields_coeffs
        self._mapping_coeffs = mapping_coeffs
        # ...

        # ranges
        ranges_test  = [Range(test_degrees[i]+1) for i in range(dim_test)]
        ranges_trial = [Range(trial_degrees[i]+1) for i in range(dim_trial)]
        ranges_quad  = [Range(qds_dim[i]) for i in range(dim)]
        # ...

        # body of kernel
        body = []

        init_basis = OrderedDict()
        init_map   = OrderedDict()
        for atom in atomic_expr:
            init, map_stmts = compute_atoms_expr(atom,
                                                 indices_quad,
                                                 indices_test,
                                                 indices_trial,
                                                 basis_trial,
                                                 basis_test,
                                                 coordinates,
                                                 test_function,
                                                 is_linear,
                                                 mapping)

            init_basis[str(init.lhs)] = init
            for stmt in map_stmts:
                init_map[str(stmt.lhs)] = stmt

        init_basis = OrderedDict(sorted(init_basis.items()))
        body += list(init_basis.values())

        if mapping:
            body += [Assign(lhs, rhs[indices_quad]) for lhs, rhs in zip(mapping_elements,
                                                          mapping_values)]

        # ... normal/tangent vectors
        if isinstance(self.target, Boundary):
            vectors = self.kernel_expr.atoms(BoundaryVector)
            normal_vec = symbols('normal_1:%d'%(dim+1))
            tangent_vec = symbols('tangent_1:%d'%(dim+1))

            for vector in vectors:
                if isinstance(vector, NormalVector):
                    # replace n[i] by its scalar components
                    for i in range(0, dim):
                        expr = [e.subs(vector[i], normal_vec[i]) for e in expr]

                    stmts = compute_normal_vector(normal_vec,
                                                  self.discrete_boundary,
                                                  mapping)

                elif isinstance(vector, TangentVector):
                    # replace t[i] by its scalar components
                    for i in range(0, dim):
                        expr = [e.subs(vector[i], tangent_vec[i]) for e in expr]

                    stmts = compute_tangent_vector(tangent_vec,
                                                   self.discrete_boundary,
                                                   mapping)

                body += stmts
        # ...


        if mapping:
            # ... inv jacobian
            jac = mapping.det_jacobian
            rdim = mapping.rdim
            ops = _partial_derivatives[:rdim]
            elements = [d(mapping[i]) for d in ops for i in range(0, rdim)]
            for e in elements:
                new = print_expression(e, mapping_name=False)
                new = Symbol(new)
                jac = jac.subs(e, new)
            # ...

            inv_jac = Symbol('inv_jac')
            body += [Assign(inv_jac, 1/jac)]

            # TODO do we use the same inv_jac?
#            if not isinstance(self.target, Boundary):
#                body += [Assign(inv_jac, 1/jac)]

            init_map = OrderedDict(sorted(init_map.items()))
            for stmt in list(init_map.values()):
                body += [stmt.subs(1/jac, inv_jac)]

        else:
            body += [Assign(coordinates[i],positions[i][indices_quad[i]])
                     for i in range(dim)]
        # ...

        # ...
        weighted_vol = filter_product(indices_quad, weighted_vols, self.discrete_boundary)
        # ...

        # ...
        # add fields
        for i in range(len(fields_val)):
            body.append(Assign(fields[i],fields_val[i][indices_quad]))

        body.append(Assign(wvol,weighted_vol))

        for i in range(ln):
            body.append(AugAssign(v[i],'+',Mul(expr[i],wvol)))
        # ...

        # ...
        # put the body in for loops of quadrature points
        body = filter_loops(indices_quad, ranges_quad, body,
                            self.discrete_boundary,
                            boundary_basis=self.boundary_basis)

        # initialization of intermediate vars
        init_vars = [Assign(v[i],0.0) for i in range(ln)]
        body = init_vars + body
        # ...

        if dim_trial:
            trial_idxs = tuple([indices_trial[i]+trial_pads[i]-indices_test[i] for i in range(dim)])
            idxs = indices_test + trial_idxs
        else:
            idxs = indices_test

        if is_bilinear or is_linear:
            for i in range(ln):
                body.append(Assign(mats[i][idxs],v[i]))

        elif is_function:
            for i in range(ln):
                body.append(Assign(mats[i][0],v[i]))

        # ...
        # put the body in tests and trials for loops
        if is_bilinear:
            body = filter_loops(indices_test, ranges_test, body,
                                self.discrete_boundary,
                                boundary_basis=self.boundary_basis)

            body = filter_loops(indices_trial, ranges_trial, body,
                                self.discrete_boundary,
                                boundary_basis=self.boundary_basis)

        if is_linear:
            body = filter_loops(indices_test, ranges_test, body,
                                self.discrete_boundary,
                                boundary_basis=self.boundary_basis)
        # ...

        # ...
        # initialization of the matrix
        if is_bilinear or is_linear:
            init_mats = [mats[i][[Slice(None,None)]*(dim_test+dim_trial)] for i in range(ln)]

            init_mats = [Assign(e, 0.0) for e in init_mats]
            body =  init_mats + body

        # call eval field
        for eval_field in self.eval_fields:
            args = test_degrees + basis_test + fields_coeffs + fields_val
            args = eval_field.build_arguments(args)
            body = [FunctionCall(eval_field.func, args)] + body

        # calculate field values
        if fields_val:
            prelude  = [Import('zeros', 'numpy')]
            allocate = [Assign(f, Zeros(qds_dim)) for f in fields_val]
            body = prelude + allocate + body

        # call eval mapping
        if self.eval_mapping:
            args = (test_degrees + basis_test + mapping_coeffs + mapping_values)
            args = eval_mapping.build_arguments(args)
            body = [FunctionCall(eval_mapping.func, args)] + body

        # compute length of logical points
        len_quads = [Assign(k, Len(u)) for k,u in zip(qds_dim, positions)]
        body = len_quads + body

        # get math functions and constants
        math_elements = math_atoms_as_str(self.kernel_expr)
        math_imports = []
        for e in math_elements:
            math_imports += [Import(e, 'numpy')]
        body = math_imports + body

        # function args
        func_args = self.build_arguments(fields_coeffs + mapping_coeffs + mats)

        decorators = {'types': build_types_decorator(func_args)}
        return FunctionDef(self.name, list(func_args), [], body,
                           decorators=decorators)

class Assembly(SplBasic):

    def __new__(cls, kernel, name=None):

        if not isinstance(kernel, Kernel):
            raise TypeError('> Expecting a kernel')

        obj = SplBasic.__new__(cls, kernel.tag, name=name, prefix='assembly')

        obj._kernel = kernel

        # update dependencies
        obj._dependencies += [kernel]

        obj._func = obj._initialize()
        return obj

    @property
    def weak_form(self):
        return self.kernel.weak_form

    @property
    def kernel(self):
        return self._kernel

    @property
    def global_matrices(self):
        return self._global_matrices

    @property
    def init_stmts(self):
        return self._init_stmts

    def build_arguments(self, data):

        other = data

        if self.kernel.constants:
            other = other + self.kernel.constants

        if self.kernel.mapping_coeffs:
            other = self.kernel.mapping_coeffs + other

        return self.basic_args + other

    def _initialize(self):
        kernel = self.kernel
        form   = self.weak_form
        fields = kernel.fields
        fields_coeffs = kernel.fields_coeffs

        is_linear   = isinstance(self.weak_form, LinearForm)
        is_bilinear = isinstance(self.weak_form, BilinearForm)
        is_function = isinstance(self.weak_form, Integral)

        dim    = form.ldim

        n_rows = kernel.n_rows
        n_cols = kernel.n_cols

        # ... declarations
        starts        = variables([ 's{}'.format(i) for i in range(1, dim+1)], 'int')
        ends          = variables([ 'e{}'.format(i) for i in range(1, dim+1)], 'int')

        indices_elm   = variables([ 'ie{}'.format(i) for i in range(1, dim+1)], 'int')
        indices_span  = variables([ 'is{}'.format(i) for i in range(1, dim+1)], 'int')

        test_pads     = variables([ 'test_p{}'.format(i) for i in range(1, dim+1)], 'int')
        trial_pads    = variables(['trial_p{}'.format(i) for i in range(1, dim+1)], 'int')
        test_degrees  = variables([ 'test_p{}'.format(i) for i in range(1, dim+1)], 'int')
        trial_degrees = variables(['trial_p{}'.format(i) for i in range(1, dim+1)], 'int')

        # TODO remove later and replace by Len inside Kernel
        quad_orders   = variables([ 'k{}'.format(i) for i in range(1, dim+1)], 'int')

        trial_basis   = indexed_variables(['trial_basis_{}'.format(i) for i in range(1, dim+1)],
                                          dtype='real', rank=4)
        test_basis    = indexed_variables(['test_basis_{}'.format(i) for i in range(1, dim+1)],
                                          dtype='real', rank=4)
        trial_basis_in_elm = indexed_variables(['trial_bs{}'.format(i) for i in range(1, dim+1)],
                                               dtype='real', rank=3)
        test_basis_in_elm  = indexed_variables(['test_bs{}'.format(i) for i in range(1, dim+1)],
                                               dtype='real', rank=3)

        points_in_elm  = indexed_variables(['u{}'.format(i) for i in range(1, dim+1)],
                                           dtype='real', rank=1)
        weights_in_elm = indexed_variables(['w{}'.format(i) for i in range(1, dim+1)],
                                           dtype='real', rank=1)
        points   = indexed_variables(['points_{}'.format(i) for i in range(1, dim+1)],
                                     dtype='real', rank=2)
        weights  = indexed_variables(['weights_{}'.format(i) for i in range(1, dim+1)],
                                     dtype='real', rank=2)

        spans    = indexed_variables(['test_spans_{}'.format(i) for i in range(1, dim+1)],
                                     dtype='int', rank=1)
        # ...

        # ...
        if is_bilinear:
            self._basic_args = (starts + ends + quad_orders +
                                test_degrees + trial_degrees +
                                spans +
                                points + weights +
                                test_basis + trial_basis)

        if is_linear or is_function:
            self._basic_args = (starts + ends + quad_orders +
                                test_degrees +
                                spans +
                                points + weights +
                                test_basis)
        # ...

        # ...
        if is_bilinear:
            rank = 2*dim

        elif is_linear:
            rank = dim

        elif is_function:
            rank = 1
        # ...

        # ... element matrices
        element_matrices = {}
        for i in range(0, n_rows):
            for j in range(0, n_cols):
                mat = 'mat_{i}{j}'.format(i=i,j=j)

                mat = IndexedVariable(mat, dtype='real', rank=rank)

                element_matrices[i,j] = mat
        # ...

        # ... global matrices
        global_matrices = {}
        for i in range(0, n_rows):
            for j in range(0, n_cols):
                mat = 'M_{i}{j}'.format(i=i,j=j)

                mat = IndexedVariable(mat, dtype='real', rank=rank)

                global_matrices[i,j] = mat
        # ...

        # sympy does not like ':'
        _slice = Slice(None,None)

        # assignments
        body  = [Assign(indices_span[i], spans[i][indices_elm[i]]) for i in range(dim)]
        if self.debug and self.detailed:
            msg = lambda x: (String('> span {} = '.format(x)), x)
            body += [Print(msg(indices_span[i])) for i in range(dim)]

        body += [Assign(points_in_elm[i], points[i][indices_elm[i],_slice]) for i in range(dim)]
        body += [Assign(weights_in_elm[i], weights[i][indices_elm[i],_slice]) for i in range(dim)]
        body += [Assign(test_basis_in_elm[i], test_basis[i][indices_elm[i],_slice,_slice,_slice])
                 for i in range(dim)]
        if is_bilinear:
            body += [Assign(trial_basis_in_elm[i], trial_basis[i][indices_elm[i],_slice,_slice,_slice])
                     for i in range(dim)]

        # ... kernel call
        mats = []
        for i in range(0, n_rows):
            for j in range(0, n_cols):
                mats.append(element_matrices[i,j])
        mats = tuple(mats)

        gslices = [Slice(i,i+p+1) for i,p in zip(indices_span, test_degrees)]
        f_coeffs = tuple([f[gslices] for f in fields_coeffs])
        m_coeffs = tuple([f[gslices] for f in kernel.mapping_coeffs])

        args = kernel.build_arguments(f_coeffs + m_coeffs + mats)
        body += [FunctionCall(kernel.func, args)]
        # ...

        # ... update global matrices
        lslices = [Slice(None,None)]*dim
        if is_bilinear:
            lslices += [Slice(None,None)]*dim # for assignement

        if is_bilinear:
            gslices = [Slice(i-p,i+1) for i,p in zip(indices_span, test_degrees)]
            gslices += [Slice(None,None)]*dim # for assignement

        if is_linear:
            gslices = [Slice(i,i+p+1) for i,p in zip(indices_span, test_degrees)]

        if is_function:
            lslices = 0
            gslices = 0

        for i in range(0, n_rows):
            for j in range(0, n_cols):
                M = global_matrices[i,j]
                mat = element_matrices[i,j]

                stmt = AugAssign(M[gslices], '+', mat[lslices])

                body += [stmt]
        # ...

        # ... loop over elements
        ranges_elm  = [Range(starts[i], ends[i]+1) for i in range(dim)]
        body = filter_loops(indices_elm, ranges_elm, body,
                            self.kernel.discrete_boundary, boundary_basis=False)
        # ...

        # ... prelude
        prelude = []

        # import zeros from numpy
        stmt = Import('zeros', 'numpy')
        prelude += [stmt]

        # allocate element matrices
        orders  = [p+1 for p in test_degrees]
        spads   = [2*p+1 for p in test_pads]
        for i in range(0, n_rows):
            for j in range(0, n_cols):
                mat = element_matrices[i,j]

                if is_bilinear:
                    stmt = Assign(mat, Zeros((*orders, *spads)))

                if is_linear:
                    stmt = Assign(mat, Zeros((*orders,)))

                if is_function:
                    stmt = Assign(mat, Zeros((1,)))

                prelude += [stmt]

                if self.debug:
                    prelude += [Print((String('> shape {} = '.format(mat)), *orders, *spads))]

        # allocate mapping values
        if self.kernel.mapping_values:
            for v in self.kernel.mapping_values:
                stmt = Assign(v, Zeros(quad_orders))
                prelude += [stmt]
        # ...

        # ...
        if self.debug:
            for i in range(0, n_rows):
                for j in range(0, n_cols):
                    M = global_matrices[i,j]
                    prelude += [Print((String('> shape {} = '.format(M)), Shape(M)))]
        # ...

        # ...
        body = prelude + body
        # ...

        # ...
        mats = []
        for i in range(0, n_rows):
            for j in range(0, n_cols):
                M = global_matrices[i,j]
                mats.append(M)
        mats = tuple(mats)
        self._global_matrices = mats
        # ...

        # ... the following statements are needed for f2py interface to avoid
        # the intent problem
        #     TODO must be fixed in pyccel by computing intent from FunctionDef
        if is_bilinear:
            gslices = [Slice(None,None)]*2*dim

        if is_linear:
            gslices = [Slice(None,None)]*dim

        if is_function:
            gslices = 0

        init_stmts = []
        for i in range(0, n_rows):
            for j in range(0, n_cols):
                M = global_matrices[i,j]
                stmt = AugAssign(M[gslices], '+', 0.)
                init_stmts += [stmt]

        self._init_stmts = init_stmts
        # ...

        # function args
        func_args = self.build_arguments(fields_coeffs + mats)

        decorators = {'types': build_types_decorator(func_args)}
        return FunctionDef(self.name, list(func_args), [], body,
                           decorators=decorators)

class Interface(SplBasic):

    def __new__(cls, assembly, name=None):

        if not isinstance(assembly, Assembly):
            raise TypeError('> Expecting an Assembly')

        obj = SplBasic.__new__(cls, assembly.tag, name=name, prefix='interface')

        obj._assembly = assembly

        # update dependencies
        obj._dependencies += [assembly]

        obj._func = obj._initialize()
        return obj

    @property
    def weak_form(self):
        return self.assembly.weak_form

    @property
    def assembly(self):
        return self._assembly

    @property
    def max_nderiv(self):
        return self.assembly.kernel.max_nderiv

    def build_arguments(self, data):
        # data must be at the end, since they are optional
        return self.basic_args + data

    @property
    def in_arguments(self):
        return self._in_arguments

    @property
    def inout_arguments(self):
        return self._inout_arguments

    def _initialize(self):
        form = self.weak_form
        assembly = self.assembly
        global_matrices = assembly.global_matrices
        fields = tuple(form.expr.atoms(Field))
        fields = sorted(fields, key=lambda x: str(x.name))
        fields = tuple(fields)

        is_linear   = isinstance(self.weak_form, LinearForm)
        is_bilinear = isinstance(self.weak_form, BilinearForm)
        is_function = isinstance(self.weak_form, Integral)

        dim = form.ldim

        # ... declarations
        test_space = Symbol('W')
        trial_space = Symbol('V')
        if is_bilinear:
            spaces = (test_space, trial_space)

        if is_linear or is_function:
            spaces = (test_space,)

        starts         = symbols('s1:%d'%(dim+1))
        ends           = symbols('e1:%d'%(dim+1))
        test_degrees   = symbols('test_p1:%d'%(dim+1))
        trial_degrees  = symbols('trial_p1:%d'%(dim+1))
        points         = symbols('points_1:%d'%(dim+1), cls=IndexedBase)
        weights        = symbols('weights_1:%d'%(dim+1), cls=IndexedBase)
        trial_basis    = symbols('trial_basis_1:%d'%(dim+1), cls=IndexedBase)
        test_basis     = symbols('test_basis_1:%d'%(dim+1), cls=IndexedBase)
        spans          = symbols('test_spans_1:%d'%(dim+1), cls=IndexedBase)
        quad_orders    = symbols('k1:%d'%(dim+1))

        mapping = ()
        if form.mapping:
            mapping = Symbol('mapping')
        # ...

        # ...
        if dim == 1:
            points        = points[0]
            weights       = weights[0]
            trial_basis   = trial_basis[0]
            test_basis    = test_basis[0]
            spans         = spans[0]
            quad_orders   = quad_orders[0]
        # ...

        # ...
        self._basic_args = spaces
        # ...

        # ... getting data from fem space
        body = []

        # TODO use supports here with starts / ends
        body += [Assign(test_degrees, DottedName(test_space, 'vector_space', 'pads'))]
        if is_bilinear:
            body += [Assign(trial_degrees, DottedName(trial_space, 'vector_space', 'pads'))]

        body += [Comment(' TODO must use suppoerts with starts/ends')]
        body += [Assign(starts, DottedName(test_space, 'vector_space', 'starts'))]
        body += [Assign(ends, DottedName(test_space, 'vector_space', 'ends'))]
        for i in range(0, dim):
            body += [Assign(ends[i], ends[i]-test_degrees[i])]


        body += [Assign(spans, DottedName(test_space, 'spans'))]
        body += [Assign(quad_orders, DottedName(test_space, 'quad_order'))]
        body += [Assign(points, DottedName(test_space, 'quad_points'))]
        body += [Assign(weights, DottedName(test_space, 'quad_weights'))]

        body += [Assign(test_basis, DottedName(test_space, 'quad_basis'))]
        if is_bilinear:
            body += [Assign(trial_basis, DottedName(trial_space, 'quad_basis'))]
        # ...

        # ...
        if mapping:
            for i, coeff in enumerate(assembly.kernel.mapping_coeffs):
                component = IndexedBase(DottedName(mapping, '_fields'))[i]
                body += [Assign(coeff, DottedName(component, '_coeffs', '_data'))]
        # ...

        # ...
        if not is_function:
            if is_bilinear:
                body += [Import('StencilMatrix', 'spl.linalg.stencil')]

            if is_linear:
                body += [Import('StencilVector', 'spl.linalg.stencil')]

            for M in global_matrices:
                if_cond = Is(M, Nil())
                if is_bilinear:
                    args = [DottedName(test_space, 'vector_space'),
                            DottedName(trial_space, 'vector_space')]
                    if_body = [Assign(M, FunctionCall('StencilMatrix', args))]

                if is_linear:
                    args = [DottedName(test_space, 'vector_space')]
                    if_body = [Assign(M, FunctionCall('StencilVector', args))]

                stmt = If((if_cond, if_body))
                body += [stmt]

        else:
            body += [Import('zeros', 'numpy')]
            for M in global_matrices:
                body += [Assign(M, Zeros(1))]
        # ...

        # ...
        self._inout_arguments = list(global_matrices)
        self._in_arguments = list(self.assembly.kernel.constants) + list(fields)
        # ...

        # ... call to assembly
        if is_bilinear or is_linear:
            mat_data = [DottedName(M, '_data') for M in global_matrices]

        elif is_function:
            mat_data = [M for M in global_matrices]

        mat_data       = tuple(mat_data)

        field_data     = [DottedName(F, '_coeffs', '_data') for F in fields]
        field_data     = tuple(field_data)

        args = assembly.build_arguments(field_data + mat_data)

        body += [FunctionCall(assembly.func, args)]
        # ...

        # ... results
        if is_bilinear or is_linear:
            if len(global_matrices) > 1:
                L = Symbol('L')
                if is_bilinear:
                    body += [Import('BlockMatrix', 'spl.linalg.block')]

                    # TODO this is a duplicated code => use a function to define
                    # global_matrices
                    n_rows = self.assembly.kernel.n_rows
                    n_cols = self.assembly.kernel.n_cols

                    d = {}
                    for i in range(0, n_rows):
                        for j in range(0, n_cols):
                            mat = IndexedBase('M_{i}{j}'.format(i=i,j=j))
                            d[(i,j)] = mat

                    D = Symbol('d')
                    d = OrderedDict(sorted(d.items()))
                    body += [Assign(D, d)]
                    body += [Assign(L, FunctionCall('BlockMatrix', [D]))]

                elif is_linear:
                    body += [Import('BlockVector', 'spl.linalg.block')]
                    body += [Assign(L, FunctionCall('BlockVector', [global_matrices]))]

                body += [Return(L)]

            else:
                M = global_matrices[0]
                body += [Return(M)]

        elif is_function:
            if len(global_matrices) == 1:
                M = global_matrices[0]
                body += [Return(M[0])]

            else:
                body += [Return(M[0] for M in global_matrices)]
        # ...

        # ... arguments
        if is_bilinear or is_linear:
            mats = [Assign(M, Nil()) for M in global_matrices]
            mats = tuple(mats)

        elif is_function:
            mats = ()

        if mapping:
            mapping = (mapping,)

        if self.assembly.kernel.constants:
            constants = self.assembly.kernel.constants
            args = mapping + constants + fields + mats

        else:
            args = mapping + fields + mats

        func_args = self.build_arguments(args)
        # ...

        return FunctionDef(self.name, list(func_args), [], body)
