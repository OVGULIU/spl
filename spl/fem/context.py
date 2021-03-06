# coding: utf-8
# Copyright 2018 Yaman Güçlü

from mpi4py import MPI
import h5py
import yaml

from spl.fem.basic        import FemField
from spl.fem.splines      import SplineSpace
from spl.fem.tensor       import TensorFemSpace
from spl.mapping.discrete import SplineMapping

__all__ = ['fem_context']

#==============================================================================
def fem_context( filename, comm=MPI.COMM_WORLD ):
    """
    Create tensor-product spline space and mapping from geometry input file
    in HDF5 format (single-patch only).

    Parameters
    ----------
    filename : str
      Name of HDF5 input file.

    comm : mpi4py.Comm
      MPI communicator.

    Results
    -------
    w : TensorFemSpace
      Tensor-product spline space.

    m : SplineMapping
      Tensor-product spline mapping.

    """
    if comm.size > 1:
        kwargs = dict( driver='mpio', comm=comm )
    else:
        kwargs = {}

    h5  = h5py.File( filename, mode='r', **kwargs )
    yml = yaml.load( h5['geometry.yml'].value )

    ldim = yml['ldim']
    pdim = yml['pdim']

    num_patches = len( yml['patches'] )

    if num_patches == 0:

        h5.close()
        raise ValueError( "Input file contains no patches." )

    elif num_patches == 1:

        item  = yml['patches'][0]
        patch = h5[item['name']]

        degree   = [int (p) for p in patch.attrs['degree'  ]]
        periodic = [bool(b) for b in patch.attrs['periodic']]
        nbasis   = [int (n) for n in patch.attrs['shape'   ]]
        knots    = [patch['knots_{}'.format(d)].value for d in range( ldim )]
        spaces   = [SplineSpace( degree=p, knots=k, periodic=b )
                    for p,k,b in zip( degree, knots, periodic )]

        tensor_space = TensorFemSpace( *spaces, comm=comm )
        mapping      = SplineMapping.from_control_points( tensor_space, patch['points'] )

        h5.close()
        return tensor_space, mapping

    else:
        # TODO: multipatch geometry
        h5.close()
        raise NotImplementedError( "SPL library cannot handle multipatch geometries yet." )
