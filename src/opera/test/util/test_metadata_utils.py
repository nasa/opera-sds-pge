#!/usr/bin/env python

"""
======================
test_metadata_utils.py
======================

Unit tests for the util/metadata_utils.py module.

"""

import tempfile
import os
import unittest
from unittest import skipIf

from opera.util.metadata_utils import create_test_rtc_metadata_product
from opera.util.metadata_utils import get_geographic_boundaries_from_mgrs_tile
from opera.util.metadata_utils import get_rtc_s1_product_metadata


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


class MetadataUtilsTestCase(unittest.TestCase):
    """Unit test Metadata Utilities"""

    @skipIf(not osr_is_available(), reason="osgeo.osr is not installed on the local instance")
    def test_get_geographic_boundaries_from_mgrs_tile_nominal(self):
        """Reproduce ADT results from values provided with code"""
        lat_min, lat_max, lon_min, lon_max = get_geographic_boundaries_from_mgrs_tile('15SXR')

        self.assertAlmostEqual(lat_min, 31.616027943130398)
        self.assertAlmostEqual(lat_max, 32.6212369766609)
        self.assertAlmostEqual(lon_min, -91.94552881416524)
        self.assertAlmostEqual(lon_max, -90.76425651871281)

    @skipIf(not osr_is_available(), reason="osgeo.osr is not installed on the local instance")
    def test_get_geographic_boundaries_from_mgrs_tile_leading_T(self):
        """Test MGRS tile code conversion when code starts with T"""
        lat_min, lat_max, lon_min, lon_max = get_geographic_boundaries_from_mgrs_tile('T15SXR')

        self.assertAlmostEqual(lat_min, 31.616027943130398)
        self.assertAlmostEqual(lat_max, 32.6212369766609)
        self.assertAlmostEqual(lon_min, -91.94552881416524)
        self.assertAlmostEqual(lon_max, -90.76425651871281)

    @skipIf(not osr_is_available(), reason="osgeo.osr is not installed on the local instance")
    def test_get_geographic_boundaries_from_mgrs_tile_invalid_tile(self):
        """Test MGRS tile code conversion with an invalid code"""
        self.assertRaises(RuntimeError, get_geographic_boundaries_from_mgrs_tile, 'X15SXR')

    def test_get_rtc_s1_product_metadata(self):
        """Test retrieval of product metadata from HDF5 files"""
        file_name = os.path.join(tempfile.gettempdir(), "test_metadata_file.hdf5")
        create_test_rtc_metadata_product(file_name)

        try:
            product_output = get_rtc_s1_product_metadata(file_name)

            self.assertAlmostEqual(product_output['frequencyA']['centerFrequency'], 5405000454.33435)
            self.assertEqual(product_output['orbit']['orbitType'], "POE")
            self.assertEqual(product_output['processingInformation']['inputs']['demSource'], 'dem.tif')
            for po,eo in zip(product_output['processingInformation']['inputs']['auxcalFiles'],
                             ['calibration-s1b-iw1-slc-vv-20180504t104508-20180504t104533-010770-013aee-004.xml',
                              'noise-s1b-iw1-slc-vv-20180504t104508-20180504t104533-010770-013aee-004.xml']):
                self.assertEqual(po, eo)
            self.assertEqual(product_output['processingInformation']['algorithms']['geocoding'], 'area_projection')
            self.assertEqual(product_output['identification']['trackNumber'], 147170)

        finally:
            os.remove(file_name)


if __name__ == "__main__":
    unittest.main()
