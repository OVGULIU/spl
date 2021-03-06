# coding: utf-8
"""
This module provides iterative solvers and precondionners.
"""

__all__ = ['cg','pcg', 'jacobi', 'weighted_jacobi']

# ...
def cg( A, b, x0=None, tol=1e-6, maxiter=1000, verbose=False ):
    """
    Conjugate gradient algorithm for solving linear system Ax=b.
    Implementation from [1], page 137.

    Parameters
    ----------
    A : spl.linalg.basic.LinearOperator
        Left-hand-side matrix A of linear system; individual entries A[i,j]
        can't be accessed, but A has 'shape' attribute and provides 'dot(p)'
        function (i.e. matrix-vector product A*p).

    b : spl.linalg.basic.Vector
        Right-hand-side vector of linear system. Individual entries b[i] need
        not be accessed, but b has 'shape' attribute and provides 'copy()' and
        'dot(p)' functions (dot(p) is the vector inner product b*p ); moreover,
        scalar multiplication and sum operations are available.

    x0 : spl.linalg.basic.Vector
        First guess of solution for iterative solver (optional).

    tol : float
        Absolute tolerance for L2-norm of residual r = A*x - b.

    maxiter: int
        Maximum number of iterations.

    verbose : bool
        If True, L2-norm of residual r is printed at each iteration.

    Returns
    -------
    x : spl.linalg.basic.Vector
        Converged solution.

    See also
    --------
    [1] A. Maister, Numerik linearer Gleichungssysteme, Springer ed. 2015.

    """
    from math import sqrt

    n = A.shape[0]

    assert( A.shape == (n,n) )
    assert( b.shape == (n, ) )

    # First guess of solution
    if x0 is None:
        x = 0.0 * b.copy()
    else:
        assert( x0.shape == (n,) )
        x = x0.copy()

    # First values
    r  = b - A.dot( x )
    am = r.dot( r )
    p  = r.copy()

    tol_sqr = tol**2

    if verbose:
        print( "CG solver:" )
        print( "+---------+---------------------+")
        print( "+ Iter. # | L2-norm of residual |")
        print( "+---------+---------------------+")
        template = "| {:7d} | {:19.2e} |"

    # Iterate to convergence
    for m in range( 1, maxiter+1 ):

        if am < tol_sqr:
            m -= 1
            break

        v   = A.dot( p )
        l   = am / v.dot( p )
        x  += l*p
        r  -= l*v
        am1 = r.dot( r )
        p   = r + (am1/am)*p
        am  = am1

        if verbose:
            print( template.format( m, sqrt( am ) ) )

    if verbose:
        print( "+---------+---------------------+")

    # Convergence information
    info = {'niter': m, 'success': am < tol_sqr, 'res_norm': sqrt( am ) }

    return x, info
# ...

# ...
def pcg(A, b, pc, x0=None, tol=1e-6, maxiter=1000, verbose=False):
    """
    Preconditioned Conjugate Gradient (PCG) solves the symetric positive definte
    system Ax = b. It assumes that pc(r) returns the solution to Ps = r,
    where P is positive definite.

    Parameters
    ----------
    A : spl.linalg.stencil.StencilMatrix
        Left-hand-side matrix A of linear system

    b : spl.linalg.stencil.StencilVector
        Right-hand-side vector of linear system.

    pc: string
        Preconditioner for A, it should approximate the inverse of A.
        "jacobi" and "weighted_jacobi" are available in this module.

    x0 : spl.linalg.basic.Vector
        First guess of solution for iterative solver (optional).

    tol : float
        Absolute tolerance for L2-norm of residual r = A*x - b.

    maxiter: int
        Maximum number of iterations.

    verbose : bool
        If True, L2-norm of residual r is printed at each iteration.

    Returns
    -------
    x : spl.linalg.basic.Vector
        Converged solution.

    """
    from math import sqrt

    n = A.shape[0]

    assert( A.shape == (n,n) )
    assert( b.shape == (n, ) )

    # First guess of solution
    if x0 is None:
        x = 0.0 * b.copy()
    else:
        assert( x0.shape == (n,) )
        x = x0.copy()

    # First values
    r = b - A.dot(x)

    nrmr0_sqr = r.dot(r)
    tol_sqr = tol**2

    psolve = eval(pc)
    s = psolve(A, r)
    p = s
    sr = s.dot(r)

    if verbose:
        print( "CG solver:" )
        print( "+---------+---------------------+")
        print( "+ Iter. # | L2-norm of residual |")
        print( "+---------+---------------------+")
        template = "| {:7d} | {:19.2e} |"

    # Iterate to convergence
    for k in range(1, maxiter+1):

        q = A.dot(p)
        alpha  = sr / p.dot(q)

        x  = x + alpha*p
        r  = r - alpha*q

        s = A.dot(r)

        nrmr_sqr = r.dot(r)

        if nrmr_sqr < tol_sqr*nrmr0_sqr:
            k -= 1
            break

        s = psolve(A, r)

        srold = sr
        sr = s.dot(r)

        beta = sr/srold

        p = s + beta*p

        if verbose:
            print( template.format(k, sqrt(nrmr_sqr)))

    if verbose:
        print( "+---------+---------------------+")

    # Convergence information
    info = {'niter': k, 'success': nrmr_sqr < tol_sqr*nrmr0_sqr, 'res_norm': sqrt(nrmr_sqr) }

    return x, info
# ...

# ...
def jacobi(A, b):
    """
    Jacobi preconditioner.
    ----------
    A : spl.linalg.stencil.StencilMatrix
        Left-hand-side matrix A of linear system.

    b : spl.linalg.stencil.StencilVector
        Right-hand-side vector of linear system.

    Returns
    -------
    x : spl.linalg.stencil.StencilVector
        Converged solution.

    """
    from spl.linalg.stencil import StencilVector

    n = A.shape[0]

    assert(A.shape == (n,n))
    assert(b.shape == (n, ))

    V = b.space
    x = StencilVector(V)

    # ...
    if V.ndim == 1:
        [s1] = V.starts
        [e1] = V.ends
        [p1] = V.pads

        x[:] = 0.

        for i1 in range(s1, e1+1):
                x[i1] = A[i1, 0]
                x[i1] = b[i1]/ x[i1]

    elif V.ndim == 2:
        [s1, s2] = V.starts
        [e1, e2] = V.ends
        [p1, p2] = V.pads

        x[:,:] = 0.

        for i1 in range(s1, e1+1):
            for i2 in range(s2, e2+1):
                x[i1, i2] = A[i1, i2, 0, 0]
                x[i1, i2] = b[i1, i2]/ x[i1, i2]

    elif V.ndim == 3:
        [s1, s2, s3] = V.starts
        [e1, e2, e3] = V.ends
        [p1, p2, p3] = V.pads

        x[:,:, :] = 0.

        for i1 in range(s1, e1+1):
            for i2 in range(s2, e2+1):
                for i3 in range(s3, e3+1):
                    x[i1, i2. i3] = A[i1, i2, i3, 0, 0, 0]
                    x[i1, i2, i3] = b[i1, i2, i3]/ x[i1, i2, i3]
    #...

    x.update_ghost_regions()

    return x
# ...

# ...
def weighted_jacobi(A, b, x0=None, omega= 2./3, tol=1e-10, maxiter=100, verbose=False):
    """
    Weighted Jacobi iterative preconditioner.

    Parameters
    ----------
    A : spl.linalg.stencil.StencilMatrix
        Left-hand-side matrix A of linear system.

    b : spl.linalg.stencil.StencilVector
        Right-hand-side vector of linear system.

    x0 : spl.linalg.basic.Vector
        First guess of solution for iterative solver (optional).

    omega : float
        The weight parameter (optional). Default value equal to 2/3.

    tol : float
        Absolute tolerance for L2-norm of residual r = A*x - b.

    maxiter: int
        Maximum number of iterations.

    verbose : bool
        If True, L2-norm of residual r is printed at each iteration.

    Returns
    -------
    x : spl.linalg.stencil.StencilVector
        Converged solution.

    """
    from math import sqrt
    from spl.linalg.stencil import StencilVector

    n = A.shape[0]

    assert(A.shape == (n,n))
    assert(b.shape == (n, ))

    V  = b.space
    s = V.starts
    e = V.ends

    # First guess of solution
    if x0 is None:
        x = 0.0 * b.copy()
    else:
        assert( x0.shape == (n,) )
        x = x0.copy()

    dr = 0.0 * b.copy()
    tol_sqr = tol**2

    if verbose:
        print( "Weighted Jacobi iterative method:" )
        print( "+---------+---------------------+")
        print( "+ Iter. # | L2-norm of residual |")
        print( "+---------+---------------------+")
        template = "| {:7d} | {:19.2e} |"

    # Iterate to convergence
    for k in range(1, maxiter+1):
        r = b - A.dot(x)

        # TODO build new external method get_diagonal and add 3d case
        if V.ndim ==1:
            for i1 in range(s[0], e[0]+1):
                dr[i1] = omega*r[i1]/A[i1, 0]

        elif V.ndim ==2:
            for i1 in range(s[0], e[0]+1):
                for i2 in range(s[1], e[1]+1):
                    dr[i1, i2] = omega*r[i1, i2]/A[i1, i2, 0, 0]
        # ...
        dr.update_ghost_regions()

        x  = x + dr

        nrmr = dr.dot(dr)
        if nrmr < tol_sqr:
            k -= 1
            break

        if verbose:
            print( template.format(k, sqrt(nrmr)))

    if verbose:
        print( "+---------+---------------------+")

    # Convergence information
    info = {'niter': k, 'success': nrmr < tol_sqr, 'res_norm': sqrt(nrmr) }

    return x
# ...
