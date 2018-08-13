# -*- coding: utf-8 -*-
"""
Created on Thu Jul 12 16:02:06 2018

@author: nsde
"""
#%%
from .cpab1d.setup_constrains import get_constrain_matrix_1D
from .cpab2d.setup_constrains import get_constrain_matrix_2D
from .cpab3d.setup_constrains import get_constrain_matrix_3D
from .cpab1d.transformer import tf_cpab_transformer_1D
from .cpab2d.transformer import tf_cpab_transformer_2D
from .cpab3d.transformer import tf_cpab_transformer_3D
from .helper.tf_interpolate2 import tf_interpolate_1D, tf_interpolate_2D, tf_interpolate_3D
from .helper.tf_findcellidx import tf_findcellidx_1D, tf_findcellidx_2D, tf_findcellidx_3D

from .helper.utility import get_dir, save_obj, load_obj, create_dir, check_if_file_exist
from .helper.math import null

import numpy as np
import tensorflow as tf

#%%
class cpab(object):
    '''
    
    '''
    def __init__(self, tess_size, 
                 zero_boundary=True, 
                 volume_perservation=False):
        # Check input
        assert len(tess_size) > 0 and len(tess_size) <= 3, \
            '''Transformer only support 1D, 2D or 3D'''
        assert type(tess_size) == list or type(tess_size) == tuple, \
            '''Argument tess_size must be a list or tuple'''
        assert all([type(e)==int for e in tess_size]), \
            '''All elements of tess_size must be integers'''
        assert all([e > 0 for e in tess_size]), \
            '''All elements of tess_size must be positive'''
        assert type(zero_boundary) == bool, \
            '''Argument zero_boundary must be True or False'''
        assert type(volume_perservation) == bool, \
            '''Argument volume_perservation must be True or False'''
        
        # Parameters
        self._nc = tess_size
        self._ndim = len(tess_size)
        self._Ashape = [self._ndim, self._ndim+1]
        self._valid_outside = not(zero_boundary)
        self._zero_boundary = zero_boundary
        self._volume_perservation = volume_perservation
        self._domain_max = [1 for e in self._nc]
        self._domain_min = [0 for e in self._nc]
        self._inc = [(self._domain_max[i] - self._domain_min[i]) / 
                    self._nc[i] for i in range(self._ndim)]
        self._nstepsolver = 50
        
        # Special cases
        assert not(self._ndim==3 and not zero_boundary), \
            '''Non zero boundary is not implemented for 3D'''
        
        # For saving the basis
        self._dir = get_dir(__file__) + '/basis_files/'
        self._basis_name = 'cpab_basis_dim' + str(self._ndim) + '_tess' + \
                          '_'.join([str(e) for e in self._nc]) + '_' + \
                          'vo' + str(int(self._valid_outside)) + '_' + \
                          'zb' + str(int(self._zero_boundary)) + '_' + \
                          'vp' + str(int(self._volume_perservation))
        self._basis_file = self._dir + self._basis_name
        create_dir(self._dir)
        
        # Specific for the different dims
        if self._ndim == 1:
            self._nC = self._nc[0]
            get_constrain_matrix_f = get_constrain_matrix_1D
            self._transformer_tf = tf_cpab_transformer_1D
            self._interpolate_tf = tf_interpolate_1D
            self._findcellidx_tf = tf_findcellidx_1D            
        elif self._ndim == 2:
            self._nC = 4*np.prod(self._nc)
            get_constrain_matrix_f = get_constrain_matrix_2D
            self._transformer_tf = tf_cpab_transformer_2D
            self._interpolate_tf = tf_interpolate_2D
            self._findcellidx_tf = tf_findcellidx_2D
        elif self._ndim == 3:
            self._nC = 6*np.prod(self._nc)
            get_constrain_matrix_f = get_constrain_matrix_3D
            self._transformer_tf = tf_cpab_transformer_3D
            self._interpolate_tf = tf_interpolate_3D
            self._findcellidx_tf = tf_findcellidx_3D
            
        # Check if we have already created the basis
        if not check_if_file_exist(self._basis_file+'.pkl'):
            # Get constrain matrix
            L = get_constrain_matrix_f(self._nc, self._domain_min, self._domain_max,
                                       self._valid_outside, self._zero_boundary,
                                       self._volume_perservation)
                
            # Find null space of constrain matrix
            B = null(L)
            self._constrain_mat = L
            self._basis = B
            self._D, self._d = B.shape
            
            # Save basis as pkl file
            obj = {'basis': self._basis, 'constrains': self._constrain_mat, 'ndim': self._ndim,
                   'D': self._D, 'd': self._d, 'nc': self._nc, 'nC': self._nC,
                   'Ashape': self._Ashape, 'nstepsolver': self._nstepsolver}
            save_obj(obj, self._basis_file)
            save_obj(obj, self._dir + 'current_basis')
            
        else: # if it exist, just load it
            file = load_obj(self._basis_file)
            self._basis = file['basis']
            self._constrain_mat = file['constrains']
            self._D = file['D']
            self._d = file['d']
            
            # Save as the current basis
            obj = {'basis': self._basis, 'constrains': self._constrain_mat, 'ndim': self._ndim,
                   'D': self._D, 'd': self._d, 'nc': self._nc, 'nC': self._nC,
                   'Ashape': self._Ashape, 'nstepsolver': self._nstepsolver}
            save_obj(obj, self._dir + 'current_basis')
            
        # To run tensorflow
        self._sess = tf.Session()
        self._sess.run(tf.global_variables_initializer())
        
        # Make some placeholders
        theta_p = tf.placeholder(tf.float32, shape=(None, self._d))
        points_p = tf.placeholder(tf.float32)
        if self._ndim == 1:
            data_p = tf.placeholder(tf.float32, shape=(None, None))
        else:
            data_p = tf.placeholder(tf.float32, shape=(None, None, None, None))
        
        # Make numpy-callable tensorflow functions
        self._transformer_np = self._sess.make_callable(self._transformer_tf(points_p, theta_p), 
                                                     [points_p, theta_p])
        self._interpolate_np = self._sess.make_callable(self._interpolate_tf(data_p, points_p), 
                                                     [data_p, points_p])
        self._findcellidx_np = self._sess.make_callable(self._findcellidx_tf(points_p, *self._nc), 
                                                     [points_p])
    
    #%%
    @property
    def get_theta_dim(self):
        return self._d
    
    #%%
    @property
    def get_basis(self):
        return self._basis
    
    #%%
    @property
    def get_params(self):
        return {'valid_outside': self._valid_outside,
                'zero_boundary': self._zero_boundary,
                'volume_perservation': self._volume_perservation,
                'Ashape': self._Ashape,
                'domain_min': self._domain_min,
                'domain_max': self._domain_max,
                'cell_increment': self._inc,
                'theta_dim': self._d,
                'original_dim': self._D}
    
    #%%
    def transform_grid(self, points, theta):
        ''' '''
        assert theta.shape[1] == self._d, \
            'Expects theta to have shape N x ' + str(self._d)
        assert points.shape[0] == self._ndim, \
            'Expects a grid of ' + str(self._ndim) + 'd points'
            
        # Call transformer
        newpoints = self._transformer_np(points, theta)
        return newpoints
    
    #%%
    def interpolate(self, data, transformed_points):
        ''' '''
        # Call interpolator
        interpolate = self._interpolate_np(data, transformed_points)
        return interpolate
    
    #%%
    def transform_data(self, data, theta):
        ''' '''
        # Create grid, call transformer, and interpolate
        points = self.uniform_meshgrid(data.shape[1:])
        new_points = self.transform(points, theta)
        new_data = self.interpolate(data, new_points)
        return new_data
    
    #%%
    def uniform_meshgrid(self, n_points):
        ''' '''
        assert len(n_points) == self._ndim, \
            'n_points needs to be a list equal to the dimensionality of the transformation'
        lin_p = [np.linspace(self._domain_min[i], self._domain_max[i], n_points[i])
                for i in range(self._ndim)]
        mesh_p = np.meshgrid(*lin_p)
        grid = np.vstack([array.flatten() for array in mesh_p])
        return grid
    
    #%%
    def sample_transformation(self, n_sample):
        ''' '''
        return np.random.normal(size=(n_sample, self._d))
    
    #%%
    def _theta2Avees(self, theta):
        Avees = self._basis.dot(theta)
        return Avees
    
    #%%
    def _Avees2As(self, Avees):
        As = np.reshape(Avees, (self._nC, *self._Ashape))
        return As
    
    #%%
    def _As2squareAs(self, As):
        squareAs = np.zeros(shape=(self._nC, self._ndim+1, self._ndim+1))
        squareAs[:,:-1,:] = As
        return squareAs
    
    #%%
    def calc_vectorfield(self, points, theta):
        # Construct the affine transformations
        Avees = self._theta2Avees(theta)
        As = self._Avees2As(Avees)
        
        # Find cells and extract correct affine transformation
        idx = self.findcellidx_f(points.T)
        Aidx = As[idx]
        
        # Make homogeneous coordinates
        points = np.expand_dims(np.vstack((points, np.ones((1, points.shape[1])))).T,2)
        
        # Do matrix-vector multiplication
        v = np.matmul(Aidx, points)
        return np.squeeze(v).T
    
    #%%
    def visualize_vectorfield(self, theta, nb_points=10):
        points = self.uniform_meshgrid([nb_points for i in range(self._ndim)])
        v = self.calc_v(points, theta)
        
        # Plot
        import matplotlib.pyplot as plt
        if self._ndim==1:
            fig = plt.figure()
            ax = fig.add_subplot(111)
            ax.quiver(points[0,:], np.zeros_like(points), v, np.zeros_like(v))
            ax.set_xlim(self._domain_min[0], self._domain_max[0])
        elif self._ndim==2:
            fig = plt.figure()
            ax = fig.add_subplot(111)
            ax.quiver(points[0,:], points[1,:], v[0,:], v[1,:])
            ax.set_xlim(self._domain_min[0], self._domain_max[0])
            ax.set_ylim(self._domain_min[1], self._domain_max[1])
        elif self._ndim==3:
            from mpl_toolkits.mplot3d import Axes3D
            fig = plt.figure()
            ax = fig.add_subplot(111, projection='3d')
            ax.quiver(points[0,:], points[1,:], points[2,:], v[0,:], v[1,:], v[2,:],
                      length=0.3, arrow_length_ratio=0.5)
            ax.set_xlim3d(self._domain_min[0], self._domain_max[0])
            ax.set_ylim3d(self._domain_min[1], self._domain_max[1])
            ax.set_zlim3d(self._domain_min[2], self._domain_max[2])
        plt.axis('equal')
        plt.title('Velocity field')
        plt.show()
        