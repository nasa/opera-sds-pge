#!/usr/bin/env python

"""
==================
test_tiff_utils.py
==================

Unit tests for the util/tiff_utils.py module.

"""

import os
import unittest
from datetime import datetime
from os.path import abspath, join
from unittest import skipIf

from opera.test import path

from opera.util.tiff_utils import get_geotiff_dimensions
from opera.util.tiff_utils import get_geotiff_hls_dataset
from opera.util.tiff_utils import get_geotiff_hls_product_version
from opera.util.tiff_utils import get_geotiff_metadata
from opera.util.tiff_utils import get_geotiff_processing_datetime
from opera.util.tiff_utils import get_geotiff_spacecraft_name


def gdal_is_available():
    """
    Helper function to check for a local installation of the Python bindings for
    the Geospatial Data Abstraction Library (GDAL).
    Used to skip tests that require GDAL if it's not available.
    """
    try:
        from osgeo import gdal  # noqa: F401
        return True
    except (ImportError, ModuleNotFoundError):
        return False


class TiffUtilsTestCase(unittest.TestCase):
    """Unit test Tiff Utilities"""

    test_dir = None
    starting_dir = None

    @classmethod
    def setUpClass(cls) -> None:
        """Set directories"""
        cls.starting_dir = abspath(os.curdir)
        with path('opera.test', 'util') as test_dir_path:
            cls.test_dir = str(test_dir_path)
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
        self.assertIsInstance(get_geotiff_processing_datetime(input_dswx_hls_file), datetime)
        self.assertEqual(get_geotiff_processing_datetime(input_dswx_hls_file), datetime(2022, 1, 31, 21, 54, 26))
        self.assertEqual(get_geotiff_hls_product_version(input_dswx_hls_file), '0.1')
        self.assertEqual(get_geotiff_spacecraft_name(input_dswx_hls_file), 'SENTINEL-2A')

        # Now try with an L30 (Landsat-8) DSWx-HLS file
        input_dswx_hls_file = join(self.data_dir, "sample_l30_dswx_hls.tif")

        l30_metadata = get_geotiff_metadata(input_dswx_hls_file)

        self.assertIsInstance(l30_metadata, dict)
        self.assertIn('PROJECT', l30_metadata)
        self.assertEqual(l30_metadata['PROJECT'], 'OPERA')

        # Try the other utility functions
        self.assertEqual(get_geotiff_hls_dataset(input_dswx_hls_file), 'HLS.L30.T22VEQ.2021248T143156.v2.0')
        self.assertIsInstance(get_geotiff_processing_datetime(input_dswx_hls_file), datetime)
        self.assertEqual(get_geotiff_processing_datetime(input_dswx_hls_file), datetime(2022, 1, 7, 19, 25, 31))
        self.assertEqual(get_geotiff_hls_product_version(input_dswx_hls_file), '0.1')
        self.assertEqual(get_geotiff_spacecraft_name(input_dswx_hls_file), 'LANDSAT-8')

        # Try with a missing file
        with self.assertRaises(RuntimeError):
            get_geotiff_metadata('non-existent-file.tif')
            get_geotiff_metadata(input_dswx_hls_file)

        # Try with an invalid file type
        with self.assertRaises(RuntimeError):
            get_geotiff_metadata(join(self.data_dir, "valid_runconfig_full.yaml"))

    @skipIf(not gdal_is_available(), reason="GDAL is not installed on the local instance")
    def test_get_geotiff_dimensions(self):
        input_tiff = join(self.data_dir, "sample_s30_dswx_hls.tif")

        raster_width, raster_height = get_geotiff_dimensions(input_tiff)

        self.assertEqual(raster_width, 3660)
        self.assertEqual(raster_height, 3660)


if __name__ == "__main__":
    unittest.main()
