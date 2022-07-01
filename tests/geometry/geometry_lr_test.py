# Copyright 2022 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Lint as: python3
"""Test Low-Rank Geometry."""

import jax
import jax.numpy as jnp
import numpy as np
from absl.testing import absltest, parameterized

from ott.geometry import geometry, low_rank, pointcloud


class LRGeometryTest(parameterized.TestCase):

  def setUp(self):
    super().setUp()
    self.rng = jax.random.PRNGKey(0)

  def test_apply(self):
    """Test application of cost to vec or matrix."""
    n, m, r = 17, 11, 7
    keys = jax.random.split(self.rng, 5)
    c1 = jax.random.normal(keys[0], (n, r))
    c2 = jax.random.normal(keys[1], (m, r))
    c = jnp.matmul(c1, c2.T)
    bias = 0.27
    geom = geometry.Geometry(c + bias)
    geom_lr = low_rank.LRCGeometry(c1, c2, bias=bias)
    for dim, axis in ((m, 1), (n, 0)):
      for mat_shape in ((dim, 2), (dim,)):
        mat = jax.random.normal(keys[2], mat_shape)
        np.testing.assert_allclose(
            geom.apply_cost(mat, axis=axis),
            geom_lr.apply_cost(mat, axis=axis),
            rtol=1e-4
        )

  @parameterized.parameters(['mean', 'max_cost', 'max_bound', 42.])
  def test_conversion_pointcloud(self, scale_cost):
    """Test conversion from PointCloud to LRCGeometry."""
    n, m, d = 17, 11, 3
    keys = jax.random.split(self.rng, 3)
    x = jax.random.normal(keys[0], (n, d))
    y = jax.random.normal(keys[1], (m, d))

    geom = pointcloud.PointCloud(x, y, scale_cost=scale_cost)
    geom_lr = geom.to_LRCGeometry()

    self.assertEqual(geom._scale_cost, geom_lr._scale_cost)
    np.testing.assert_allclose(
        geom.inv_scale_cost, geom_lr.inv_scale_cost, rtol=1e-6, atol=1e-6
    )
    for dim, axis in ((m, 1), (n, 0)):
      for mat_shape in ((dim, 2), (dim,)):
        mat = jax.random.normal(keys[2], mat_shape)
        np.testing.assert_allclose(
            geom.apply_cost(mat, axis=axis),
            geom_lr.apply_cost(mat, axis=axis),
            rtol=1e-4
        )

  def test_apply_squared(self):
    """Test application of squared cost to vec or matrix."""
    n, m = 27, 25
    keys = jax.random.split(self.rng, 5)
    for r in [3, 15]:
      c1 = jax.random.normal(keys[0], (n, r))
      c2 = jax.random.normal(keys[1], (m, r))
      c = jnp.matmul(c1, c2.T)
      geom = geometry.Geometry(c)
      geom2 = geometry.Geometry(c ** 2)
      geom_lr = low_rank.LRCGeometry(c1, c2)
      for dim, axis in ((m, 1), (n, 0)):
        for mat_shape in ((dim, 2), (dim,)):
          mat = jax.random.normal(keys[2], mat_shape)
          out_lr = geom_lr.apply_square_cost(mat, axis=axis)
          np.testing.assert_allclose(
              geom.apply_square_cost(mat, axis=axis), out_lr, rtol=5e-4
          )
          np.testing.assert_allclose(
              geom2.apply_cost(mat, axis=axis), out_lr, rtol=5e-4
          )

  def test_add_lr_geoms(self):
    """Test application of cost to vec or matrix."""
    n, m, r, q = 17, 11, 7, 2
    keys = jax.random.split(self.rng, 5)
    c1 = jax.random.normal(keys[0], (n, r))
    c2 = jax.random.normal(keys[1], (m, r))
    d1 = jax.random.normal(keys[0], (n, q))
    d2 = jax.random.normal(keys[1], (m, q))

    c = jnp.matmul(c1, c2.T)
    d = jnp.matmul(d1, d2.T)
    geom = geometry.Geometry(c + d)

    geom_lr_c = low_rank.LRCGeometry(c1, c2)
    geom_lr_d = low_rank.LRCGeometry(d1, d2)
    geom_lr = low_rank.add_lrc_geom(geom_lr_c, geom_lr_d)

    for dim, axis in ((m, 1), (n, 0)):
      mat = jax.random.normal(keys[1], (dim, 2))
      np.testing.assert_allclose(
          geom.apply_cost(mat, axis=axis),
          geom_lr.apply_cost(mat, axis=axis),
          rtol=1e-4
      )
      vec = jax.random.normal(keys[1], (dim,))
      np.testing.assert_allclose(
          geom.apply_cost(vec, axis=axis),
          geom_lr.apply_cost(vec, axis=axis),
          rtol=1e-4
      )

  @parameterized.product(fn=[lambda x: x + 10, lambda x: x * 2], axis=[0, 1])
  def test_apply_affine_function_efficient(self, fn, axis):
    n, m, d = 21, 13, 3
    keys = jax.random.split(self.rng, 3)
    x = jax.random.normal(keys[0], (n, d))
    y = jax.random.normal(keys[1], (m, d))
    vec = jax.random.normal(keys[2], (n if axis == 0 else m,))

    geom = pointcloud.PointCloud(x, y)

    res_eff = geom.apply_cost(vec, axis=axis, fn=fn, is_linear=True)
    res_ineff = geom.apply_cost(vec, axis=axis, fn=fn, is_linear=False)

    if fn(0.0) == 0.0:
      np.testing.assert_allclose(res_eff, res_ineff, rtol=1e-4, atol=1e-4)
    else:
      self.assertRaises(
          AssertionError,
          np.testing.assert_allclose,
          res_ineff,
          res_eff,
          rtol=1e-4,
          atol=1e-4
      )


if __name__ == '__main__':
  absltest.main()
