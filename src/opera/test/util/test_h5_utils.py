#!/usr/bin/env python

"""
======================
test_h5_utils.py
======================

Unit tests for the util/h5_utils.py module.

"""

import os
import tempfile
import unittest

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

    # @skipIf(not osr_is_available(), reason="osgeo.osr is not installed on the local instance")
    # def test_get_geographic_boundaries_from_mgrs_tile_nominal(self):
    #     """Reproduce ADT results from values provided with code"""
    #     lat_min, lat_max, lon_min, lon_max = get_geographic_boundaries_from_mgrs_tile('15SXR')
    #
    #     self.assertAlmostEqual(lat_min, 31.572733739486036)
    #     self.assertAlmostEqual(lat_max, 32.577473659397235)
    #     self.assertAlmostEqual(lon_min, -91.99766472766642)
    #     self.assertAlmostEqual(lon_max, -90.81751155385777)
    #
    # @skipIf(not osr_is_available(), reason="osgeo.osr is not installed on the local instance")
    # def test_get_geographic_boundaries_from_mgrs_tile_leading_T(self):
    #     """Test MGRS tile code conversion when code starts with T"""
    #     lat_min, lat_max, lon_min, lon_max = get_geographic_boundaries_from_mgrs_tile('T15SXR')
    #
    #     self.assertAlmostEqual(lat_min, 31.572733739486036)
    #     self.assertAlmostEqual(lat_max, 32.577473659397235)
    #     self.assertAlmostEqual(lon_min, -91.99766472766642)
    #     self.assertAlmostEqual(lon_max, -90.81751155385777)
    #
    # @skipIf(not osr_is_available(), reason="osgeo.osr is not installed on the local instance")
    # def test_get_geographic_boundaries_from_mgrs_tile_invalid_tile(self):
    #     """Test MGRS tile code conversion with an invalid code"""
    #     self.assertRaises(RuntimeError, get_geographic_boundaries_from_mgrs_tile, 'X15SXR')
    #
    # @skipIf(not osr_is_available(), reason="osgeo.osr is not installed on the local instance")
    # def test_get_geographic_boundaries_from_mgrs_tile_nominal_antimeridian(self):
    #     """Test MGRS tile code conversion with a tile that crosses the anti-meridian"""
    #     lat_min, lat_max, lon_min, lon_max = get_geographic_boundaries_from_mgrs_tile('T60VXQ')
    #
    #     self.assertAlmostEqual(lat_min, 62.13198085489144)
    #     self.assertAlmostEqual(lat_max, 63.16076767648831)
    #     self.assertAlmostEqual(lon_min, 178.82637550795243)
    #     self.assertAlmostEqual(lon_max, -178.93677941363356)
    #
    # @skipIf(not osr_is_available(), reason="osgeo.osr is not installed on the local instance")
    # def test_translate_utm_bbox_to_lat_lon(self):
    #     """Test translation of a UTM bounding box to lat/lon"""
    #     # Derived from bounding box of static layer products for granule
    #     # S1B_IW_SLC__1SDV_20180504T104507_20180504T104535_010770_013AEE_919F
    #     utm_bounding_box = [200700.0, 9391650.0, 293730.0, 9440880.0]
    #     epsg_code = 32718  # UTM S Zone 18
    #
    #     lat_lon_bounding_box = translate_utm_bbox_to_lat_lon(utm_bounding_box, epsg_code)
    #     expected_bounding_box = [-5.497645682689766,  # lat_min
    #                              -5.055731551544852,  # lat_max
    #                              -77.70109080363252,  # lon_min
    #                              -76.86056393945721]  # lon_max
    #
    #     # Round off last couple digits since they can vary based on precision error
    #     lat_lon_bounding_box = list(map(lambda x: round(x, ndigits=12), lat_lon_bounding_box))
    #     expected_bounding_box = list(map(lambda x: round(x, ndigits=12), expected_bounding_box))
    #
    #     self.assertListEqual(list(lat_lon_bounding_box), expected_bounding_box)

    def test_get_disp_s1_product_metadata(self):
        """Test retrieval of product metadata from HDF5 files"""
        file_name = os.path.join(tempfile.gettempdir(), "test_disp_metadata_file.hdf5")
        create_test_disp_metadata_product(file_name)

        try:
            product_output = get_disp_s1_product_metadata(file_name)

            self.assertEqual(product_output['identification']['frame_id'], 123)
            self.assertIn("input_file_group",
                          product_output['identification']['pge_runconfig'])
            self.assertIn("log_file",
                          product_output['identification']['pge_runconfig'])
            self.assertEqual(product_output['identification']['product_version'], "0.1")
            self.assertEqual(product_output['identification']['software_version'], "0.1.2")

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
