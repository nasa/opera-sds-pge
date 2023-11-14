#!/usr/bin/env python

"""
=====================
test_dataset_utils.py
=====================

Unit tests for the util/dataset_utils.py module.

"""

import os
import unittest
from os.path import abspath, join
from re import match

from pkg_resources import resource_filename

from opera.util.dataset_utils import get_hls_filename_fields
from opera.util.dataset_utils import parse_bounding_polygon_from_wkt


class DatasetUtilsTestCase(unittest.TestCase):
    """Unit test Image Utilities"""

    test_dir = None
    starting_dir = None

    @classmethod
    def setUpClass(cls) -> None:
        """Set directories"""
        cls.starting_dir = abspath(os.curdir)
        cls.test_dir = resource_filename(__name__, "")
        cls.data_dir = join(cls.test_dir, os.pardir, "data")

        os.chdir(cls.test_dir)

    @classmethod
    def tearDownClass(cls) -> None:
        """Return to starting directory"""
        os.chdir(cls.starting_dir)

    def test_get_hls_filename_fields(self):
        """Test get_get_hls_filename_fields()"""
        # Use an example HLS dataset name
        file_name = 'HLS.S30.T53SMS.2020276T013701.v1.5'

        # Call the function
        hls_file_fields = get_hls_filename_fields(file_name)

        # Verify a dictionary is returned
        self.assertIsInstance(hls_file_fields, dict)

        # Check the key names/values
        self.assertIn('product', hls_file_fields)
        self.assertIn('tile_id', hls_file_fields)
        self.assertIn('collection_version', hls_file_fields)
        self.assertEqual(hls_file_fields['short_name'], 'S30')
        self.assertEqual(hls_file_fields['collection_version'], 'v1.5')

        # Verify the conversion from Julian
        self.assertNotEqual(match(r'\d{8}T\d{6}\b', hls_file_fields['acquisition_time']), None)

    def test_parse_bounding_polygon_from_wkt(self):
        """Test dataset_utils.parse_bounding_polygon_from_wkt()"""
        sample_wkt_polygon = "POLYGON ((1 1, 2 2, 3 3, 4 4))"

        parsed_gml_polygon = parse_bounding_polygon_from_wkt(sample_wkt_polygon)
        expected_gml_polygon = "(1 1 2 2 3 3 4 4)"

        self.assertEqual(parsed_gml_polygon, expected_gml_polygon)

        sample_wkt_multipolygon = "MULTIPOLYGON    ((1 1, 2 2, 3 3, 4 4), (4 4, 3 3, 2 2, 1 1))"

        parsed_gml_multipolygon = parse_bounding_polygon_from_wkt(sample_wkt_multipolygon)
        expected_gml_multipolygon = "(1 1 2 2 3 3 4 4) (4 4 3 3 2 2 1 1)"

        self.assertEqual(parsed_gml_multipolygon, expected_gml_multipolygon)

        sample_invalid_polygon = "POLYGON(1,2,3,4,5,6,7,8)"

        with self.assertRaises(ValueError):
            parse_bounding_polygon_from_wkt(sample_invalid_polygon)
