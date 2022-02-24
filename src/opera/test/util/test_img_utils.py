#!/usr/bin/env python

#
# Copyright 2022, by the California Institute of Technology.
# ALL RIGHTS RESERVED.
# United States Government sponsorship acknowledged.
# Any commercial use must be negotiated with the Office of Technology Transfer
# at the California Institute of Technology.
# This software may be subject to U.S. export control laws and regulations.
# By accepting this document, the user agrees to comply with all applicable
# U.S. export laws and regulations. User has the responsibility to obtain
# export licenses, or other export authority as may be required, before
# exporting such information to foreign countries or providing access to
# foreign persons.
#

"""
=================
test_img_utils.py
=================

Unit tests for the util/img_utils.py module.

"""

import os
import unittest
from os.path import abspath, join
from re import match
from unittest import skipIf

from pkg_resources import resource_filename

from opera.util.img_utils import get_geotiff_hls_dataset
from opera.util.img_utils import get_geotiff_metadata
from opera.util.img_utils import get_geotiff_processing_datetime
from opera.util.img_utils import get_geotiff_product_version
from opera.util.img_utils import get_geotiff_spacecraft_name
from opera.util.img_utils import get_hls_filename_fields


def gdal_is_available():
    """
    Helper function to check for a local installation of the Python bindings for
    the Geospatial Data Abstraction Library (GDAL).
    Used to skip tests that require GDAL if it's not available.
    """
    try:
        from osgeo import gdal
        return True
    except (ImportError, ModuleNotFoundError):
        return False


class ImgUtilsTestCase(unittest.TestCase):
    """Unit test Image Utilities"""

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

    @skipIf(not gdal_is_available(), reason="GDAL is not installed on the local instance")
    def test_get_geotiff_metadata(self):
        """Tests for the various get_geotiff_* functions"""
        # Start with a sample S30 (Sentinel-1) DSWx-HLS file
        input_dswx_hls_file = join(self.data_dir, "sample_s30_dswx_hls.tif")

        s30_metadata = get_geotiff_metadata(input_dswx_hls_file)

        self.assertIsInstance(s30_metadata, dict)
        self.assertIn('PROJECT', s30_metadata)
        self.assertEqual(s30_metadata['PROJECT'], 'OPERA')

        # Try the other utility functions
        self.assertEqual(get_geotiff_hls_dataset(input_dswx_hls_file), 'HLS.S30.T15SXR.2021250T163901.v2.0')
        self.assertEqual(get_geotiff_processing_datetime(input_dswx_hls_file), '2022-01-31T21:54:26')
        self.assertEqual(get_geotiff_product_version(input_dswx_hls_file), '0.1')
        self.assertEqual(get_geotiff_spacecraft_name(input_dswx_hls_file), 'SENTINEL-2A')

        # Now try with an L30 (Landsat-8) DSWx-HLS file
        input_dswx_hls_file = join(self.data_dir, "sample_l30_dswx_hls.tif")

        l30_metadata = get_geotiff_metadata(input_dswx_hls_file)

        self.assertIsInstance(l30_metadata, dict)
        self.assertIn('PROJECT', l30_metadata)
        self.assertEqual(l30_metadata['PROJECT'], 'OPERA')

        # Try the other utility functions
        self.assertEqual(get_geotiff_hls_dataset(input_dswx_hls_file), 'HLS.L30.T22VEQ.2021248T143156.v2.0')
        self.assertEqual(get_geotiff_processing_datetime(input_dswx_hls_file), '2022-01-07T19:25:31')
        self.assertEqual(get_geotiff_product_version(input_dswx_hls_file), '0.1')
        self.assertEqual(get_geotiff_spacecraft_name(input_dswx_hls_file), 'LANDSAT-8')

        # Try with a missing file
        with self.assertRaises(RuntimeError):
            get_geotiff_metadata('non-existent-file.tif')

        # Try with an invalid file type
        with self.assertRaises(RuntimeError):
            get_geotiff_metadata(join(self.data_dir, "valid_runconfig_full.yaml"))

    def test_get_hls_filename_fields(self):
        """Test get_get_hls_filename_fields()"""
        # Use an example HLS filename
        file_name = 'HLS.S30.T53SMS.2020276T013701.v1.5.B01.tif'
        # Call the function
        hls_file_fields = get_hls_filename_fields(file_name)
        # Verify a dictionary is returned
        self.assertIsInstance(hls_file_fields, dict)
        # Check 4 of the key names
        self.assertIn('product', hls_file_fields)
        self.assertIn('tile_id', hls_file_fields)
        self.assertIn('collection_version', hls_file_fields)
        self.assertIn('band', hls_file_fields)
        # Check the other 3 Values
        self.assertEqual(hls_file_fields['short_name'], 'S30')
        self.assertEqual(hls_file_fields['sub_version'], '5')
        self.assertEqual(hls_file_fields['extension'], 'tif')
        # Verify the conversion from Julian
        self.assertNotEqual(match(r'\d{8}T\d{6}\b', hls_file_fields['acquisition_time']), None)


if __name__ == "__main__":
    unittest.main()
