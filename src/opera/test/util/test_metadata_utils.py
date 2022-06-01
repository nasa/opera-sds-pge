#!/usr/bin/env python

"""
=================
test_metadata_utils.py
=================

Unit tests for the util/metadata_utils.py module.

"""

import unittest
from unittest import skipIf

try:
    # If mgrs, osr, or gdal are not available for import, this will raise an exception
    from opera.util.metadata_utils import get_geographic_boundaries_from_mgrs_tile
except:
    pass

def mgrs_osr_gdal_are_available():
    """
    Helper function to check for a local installation of the Python bindings for
    the Geospatial Data Abstraction Library (GDAL), osr and mgrs.
    Used to skip tests that require GDAL, osr or mgrs if they are not available.
    """
    try:
        from osgeo import gdal  # noqa: F401
        from osgeo import osr  # noqa: F401
        import mgrs  # noqa: F401
        return True
    except (ImportError, ModuleNotFoundError):
        return False


class MetadataUtilsTestCase(unittest.TestCase):
    """Unit test Metadata Utilities"""

    @skipIf(not mgrs_osr_gdal_are_available(), reason="gdal, osr, and/or mgrs is not installed on the local instance")
    def test_get_geographic_boundaries_from_mgrs_tile_nominal(self):

        """ Reproduce ADT results from values provided with code """
        lat_min, lat_max, lon_min, lon_max = get_geographic_boundaries_from_mgrs_tile('15SXR')

        self.assertAlmostEqual(lat_min, 31.616027943130398)
        self.assertAlmostEqual(lat_max, 32.6212369766609)
        self.assertAlmostEqual(lon_min, -91.94552881416524)
        self.assertAlmostEqual(lon_max, -90.76425651871281)

    @skipIf(not mgrs_osr_gdal_are_available(), reason="gdal, osr, and/or mgrs is not installed on the local instance")
    def test_get_geographic_boundaries_from_mgrs_tile_leading_T(self):

        lat_min, lat_max, lon_min, lon_max = get_geographic_boundaries_from_mgrs_tile('T15SXR')

        self.assertAlmostEqual(lat_min, 31.616027943130398)
        self.assertAlmostEqual(lat_max, 32.6212369766609)
        self.assertAlmostEqual(lon_min, -91.94552881416524)
        self.assertAlmostEqual(lon_max, -90.76425651871281)

    @skipIf(not mgrs_osr_gdal_are_available(), reason="gdal, osr, and/or mgrs is not installed on the local instance")
    def test_get_geographic_boundaries_from_mgrs_tile_invalid_tile(self):

        self.assertRaises(RuntimeError, get_geographic_boundaries_from_mgrs_tile, 'X15SXR')

if __name__ == "__main__":
    unittest.main()
