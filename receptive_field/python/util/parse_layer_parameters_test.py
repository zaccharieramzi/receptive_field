# coding=utf-8
# Copyright 2019 Google LLC.
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

"""Tests for parse_layer_parameters module."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from absl.testing import parameterized
from receptive_field.python.util import graph_compute_order
from receptive_field.python.util import parse_layer_parameters
import tensorflow as tf
import tf_slim as slim


def create_test_network(placeholder_resolution, convert_variables_to_constants):
  """Convolutional neural network for test.

  Args:
    placeholder_resolution: Resolution to use for input placeholder. Used for
      height and width dimensions.
    convert_variables_to_constants: Whether to convert variables to constants.

  Returns:
    name_to_node: Dict keyed by node name, each entry containing the node's
      NodeDef.
  """
  g = tf.Graph()
  sess = tf.Session(graph=g)
  with g.as_default():
    # An input test image with unknown spatial resolution.
    x = tf.placeholder(
        tf.float32, (1, placeholder_resolution, placeholder_resolution, 1),
        name='input_image')
    # Left branch before first addition.
    l1 = slim.conv2d(x, 1, [1, 1], stride=4, scope='L1', padding='VALID')
    # Right branch before first addition.
    l2_pad = tf.pad(x, [[0, 0], [1, 0], [1, 0], [0, 0]], name='L2_pad')
    l2 = slim.conv2d(l2_pad, 1, [3, 3], stride=2, scope='L2', padding='VALID')
    l3 = slim.max_pool2d(l2, [3, 3], stride=2, scope='L3', padding='SAME')
    # First addition.
    l4 = tf.nn.relu(l1 + l3, name='L4_relu')
    # Left branch after first addition.
    l5 = slim.conv2d(l4, 1, [1, 1], stride=2, scope='L5', padding='SAME')
    # Right branch after first addition.
    l6 = slim.conv2d(l4, 1, [3, 3], stride=2, scope='L6', padding='SAME')
    # Final addition.
    tf.add(l5, l6, name='L7_add')

    if convert_variables_to_constants:
      sess.run(tf.global_variables_initializer())
      graph_def = tf.graph_util.convert_variables_to_constants(
          sess, g.as_graph_def(), ['L7_add'])
    else:
      graph_def = g.as_graph_def()

  name_to_node = graph_compute_order.parse_graph_nodes(graph_def)
  return name_to_node


class ParseLayerParametersTest(tf.test.TestCase, parameterized.TestCase):

  @parameterized.named_parameters(('NonePlaceholder', None, False),
                                  ('224Placeholder', 224, False),
                                  ('NonePlaceholderVarAsConst', None, True),
                                  ('224PlaceholderVarAsConst', 224, True))
  def testParametersAreParsedCorrectly(self, placeholder_resolution,
                                       convert_variables_to_constants):
    """Checks parameters from create_test_network() are parsed correctly."""
    name_to_node = create_test_network(placeholder_resolution,
                                       convert_variables_to_constants)

    # L1.
    l1_node_name = 'L1/Conv2D'
    l1_params = parse_layer_parameters.get_layer_params(
        name_to_node[l1_node_name], name_to_node)
    expected_l1_params = (1, 1, 4, 4, 0, 0, 0, 0)
    self.assertEqual(l1_params, expected_l1_params)

    # L2 padding.
    l2_pad_name = 'L2_pad'
    l2_pad_params = parse_layer_parameters.get_layer_params(
        name_to_node[l2_pad_name], name_to_node)
    expected_l2_pad_params = (1, 1, 1, 1, 1, 1, 1, 1)
    self.assertEqual(l2_pad_params, expected_l2_pad_params)

    # L2.
    l2_node_name = 'L2/Conv2D'
    l2_params = parse_layer_parameters.get_layer_params(
        name_to_node[l2_node_name], name_to_node)
    expected_l2_params = (3, 3, 2, 2, 0, 0, 0, 0)
    self.assertEqual(l2_params, expected_l2_params)

    # L3.
    l3_node_name = 'L3/MaxPool'
    # - Without knowing input size.
    l3_params = parse_layer_parameters.get_layer_params(
        name_to_node[l3_node_name], name_to_node)
    expected_l3_params = (3, 3, 2, 2, None, None, None, None)
    self.assertEqual(l3_params, expected_l3_params)
    # - Input size is even.
    l3_even_params = parse_layer_parameters.get_layer_params(
        name_to_node[l3_node_name], name_to_node, input_resolution=[4, 4])
    expected_l3_even_params = (3, 3, 2, 2, 0, 0, 1, 1)
    self.assertEqual(l3_even_params, expected_l3_even_params)
    # - Input size is odd.
    l3_odd_params = parse_layer_parameters.get_layer_params(
        name_to_node[l3_node_name], name_to_node, input_resolution=[5, 5])
    expected_l3_odd_params = (3, 3, 2, 2, 1, 1, 2, 2)
    self.assertEqual(l3_odd_params, expected_l3_odd_params)

    # L4.
    l4_node_name = 'L4_relu'
    l4_params = parse_layer_parameters.get_layer_params(
        name_to_node[l4_node_name], name_to_node)
    expected_l4_params = (1, 1, 1, 1, 0, 0, 0, 0)
    self.assertEqual(l4_params, expected_l4_params)

    # L5.
    l5_node_name = 'L5/Conv2D'
    l5_params = parse_layer_parameters.get_layer_params(
        name_to_node[l5_node_name], name_to_node)
    expected_l5_params = (1, 1, 2, 2, 0, 0, 0, 0)
    self.assertEqual(l5_params, expected_l5_params)

    # L6.
    l6_node_name = 'L6/Conv2D'
    # - Without knowing input size.
    l6_params = parse_layer_parameters.get_layer_params(
        name_to_node[l6_node_name], name_to_node)
    expected_l6_params = (3, 3, 2, 2, None, None, None, None)
    self.assertEqual(l6_params, expected_l6_params)
    # - Input size is even.
    l6_even_params = parse_layer_parameters.get_layer_params(
        name_to_node[l6_node_name], name_to_node, input_resolution=[4, 4])
    expected_l6_even_params = (3, 3, 2, 2, 0, 0, 1, 1)
    self.assertEqual(l6_even_params, expected_l6_even_params)
    # - Input size is odd.
    l6_odd_params = parse_layer_parameters.get_layer_params(
        name_to_node[l6_node_name], name_to_node, input_resolution=[5, 5])
    expected_l6_odd_params = (3, 3, 2, 2, 1, 1, 2, 2)
    self.assertEqual(l6_odd_params, expected_l6_odd_params)

    # L7.
    l7_node_name = 'L7_add'
    l7_params = parse_layer_parameters.get_layer_params(
        name_to_node[l7_node_name], name_to_node)
    expected_l7_params = (1, 1, 1, 1, 0, 0, 0, 0)
    self.assertEqual(l7_params, expected_l7_params)


if __name__ == '__main__':
  tf.test.main()
