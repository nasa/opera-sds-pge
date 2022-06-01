#!/usr/bin/env python

"""
======================
test_metadata_utils.py
======================

Unit tests for the util/metadata_utils.py module.

"""

import unittest
from unittest import skipIf

from opera.util.metadata_utils import get_geographic_boundaries_from_mgrs_tile


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


if __name__ == "__main__":
    unittest.main()
