#!/usr/bin/env python

"""
================
test_h5_utils.py
================

Unit tests for the util/h5_utils.py module.

"""

import os
import tempfile
import unittest

import numpy as np

from opera.util.h5_utils import create_test_cslc_metadata_product
from opera.util.h5_utils import create_test_disp_metadata_product
from opera.util.h5_utils import create_test_rtc_metadata_product
from opera.util.h5_utils import get_cslc_s1_product_metadata
from opera.util.h5_utils import get_disp_s1_product_metadata
from opera.util.h5_utils import get_rtc_s1_product_metadata


def osr_is_available():
    """
    Helper function to check for a local installation of the Python bindings for
    the Geospatial Data Abstraction Library (GDAL).
    Used to skip tests that require GDAL if it is not available.
    """
    try:
        from osgeo import osr  # noqa: F401
        return True
    except (ImportError, ModuleNotFoundError):
        return False


class H5UtilsTestCase(unittest.TestCase):
    """Unit test H5 Utilities"""

    def test_get_disp_s1_product_metadata(self):
        """Test retrieval of product metadata from HDF5 files"""
        file_name = os.path.join(tempfile.gettempdir(), "test_disp_metadata_file.hdf5")
        create_test_disp_metadata_product(file_name)

        try:
            product_output = get_disp_s1_product_metadata(file_name)

            np.testing.assert_array_equal(product_output['x'], np.zeros(10,))
            np.testing.assert_array_equal(product_output['y'], np.zeros(10,))
            self.assertEqual(product_output['identification']['frame_id'], 123)
            self.assertEqual(product_output['identification']['product_version'], "0.2")
            self.assertEqual(product_output['identification']['reference_zero_doppler_start_time'],
                             "2017-02-17 13:27:50.139658")
            self.assertEqual(product_output['identification']['reference_zero_doppler_end_time'],
                             "2017-02-17 13:27:55.979493")
            self.assertEqual(product_output['identification']['secondary_zero_doppler_start_time'],
                             "2017-04-30 13:27:52.049224")
            self.assertEqual(product_output['identification']['secondary_zero_doppler_end_time'],
                             "2017-04-30 13:27:57.891116")
            self.assertEqual(product_output['identification']['bounding_polygon'],
                             "POLYGON ((-119.26 39.15, -119.32 39.16, -119.22 39.32, -119.26 39.15))")
            self.assertEqual(product_output['identification']['radar_wavelength'], 0.05546576)
            self.assertEqual(product_output['identification']['reference_datetime'], "2022-11-07 00:00:00.000000")
            self.assertEqual(product_output['identification']['secondary_datetime'], "2022-12-13 00:00:00.000000")
            self.assertEqual(product_output['identification']['average_temporal_coherence'], 0.9876175064678105)
            self.assertEqual(product_output['identification']['mission_id'], 'S1A')
            self.assertEqual(product_output['identification']['look_direction'], 'Right')
            self.assertEqual(product_output['identification']['track_number'], 27)
            self.assertEqual(product_output['identification']['orbit_pass_direction'], "Descending")
            self.assertEqual(product_output['metadata']['disp_s1_software_version'], "0.2.7")
            self.assertEqual(product_output['metadata']['dolphin_software_version'], "0.15.3")
            self.assertIn("input_file_group", product_output['metadata']['pge_runconfig'])
            self.assertIn("log_file", product_output['metadata']['pge_runconfig'])

        finally:
            os.remove(file_name)

    def test_get_rtc_s1_product_metadata(self):
        """Test retrieval of product metadata from HDF5 files"""
        file_name = os.path.join(tempfile.gettempdir(), "test_rtc_metadata_file.hdf5")
        create_test_rtc_metadata_product(file_name)

        try:
            product_output = get_rtc_s1_product_metadata(file_name)

            self.assertEqual(product_output['orbit']['orbitType'], "POE")
            self.assertEqual(product_output['processingInformation']['inputs']['demSource'], 'dem.tif')
            for po, eo in zip(product_output['processingInformation']['inputs']['annotationFiles'],
                              ['calibration-s1b-iw1-slc-vv-20180504t104508-20180504t104533-010770-013aee-004.xml',
                               'noise-s1b-iw1-slc-vv-20180504t104508-20180504t104533-010770-013aee-004.xml']):
                self.assertEqual(po, eo)
            self.assertEqual(product_output['processingInformation']['algorithms']['geocoding'], 'area_projection')
            self.assertEqual(product_output['identification']['trackNumber'], 147170)

        finally:
            os.remove(file_name)

    def test_get_cslc_s1_product_metadata(self):
        """Test retrieval of product metadata from HDF5 files"""
        file_name = os.path.join(tempfile.gettempdir(), "test_cslc_metadata_file.hdf5")
        create_test_cslc_metadata_product(file_name)

        try:
            product_metadata = get_cslc_s1_product_metadata(file_name)

            self.assertEqual(product_metadata['identification']['absolute_orbit_number'], 43011)
            self.assertEqual(product_metadata['identification']['burst_id'], 't064_135518_iw1')
            self.assertEqual(product_metadata['data']['projection'], 32611)
            self.assertAlmostEqual(product_metadata['data']['y_spacing'], -10.0)
            self.assertEqual(product_metadata['processing_information']['algorithms']['COMPASS_version'], '0.1.3')
            self.assertEqual(product_metadata['orbit']['orbit_direction'], 'Ascending')

        finally:
            os.remove(file_name)


if __name__ == "__main__":
    unittest.main()
