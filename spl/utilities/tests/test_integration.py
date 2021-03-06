# -*- coding: UTF-8 -*-

import numpy as np

from spl.core.interface import make_open_knots
from spl.core.interface import construct_quadrature_grid
from spl.core.interface import compute_greville

from spl.utilities.quadratures import gauss_legendre
from spl.utilities.integrate   import integrate
from spl.utilities.integrate   import Integral

def test_integrate():
    # ...
    n_elements = 8
    p = 2                    # spline degree
    n = n_elements + p - 1   # number of control points
    # ...

    T = make_open_knots(p, n)
    grid = compute_greville(p, n, T)
    u, w = gauss_legendre(p)  # gauss-legendre quadrature rule
    k = len(u)
    ne = len(grid) - 1        # number of elements
    points, weights = construct_quadrature_grid(ne, k, u, w, grid)

    f = lambda u: u*(1.-u)
    f_int = integrate(points, weights, f)

def test_integral():
    # ...
    n_elements = 8
    p = 2                    # spline degree
    n = n_elements + p - 1   # number of control points
    # ...

    T = make_open_knots(p, n)

    f = lambda u: u*(1.-u)

    integral = Integral(p, n, T, kind='natural')
    f_int = integral(f)

    integral = Integral(p, n, T, kind='greville')
    f_int = integral(f)

####################################################################################
if __name__ == '__main__':

    test_integrate()
    test_integral()
