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
test_metadata_utils.py
=================

Unit tests for the util/metadata_utils.py module.

"""

import unittest
from unittest import skipIf

def mgrs_osr_gdal_are_available():
    """
    Helper function to check for a local installation of the Python bindings for
    the Geospatial Data Abstraction Library (GDAL), osr and mgrs.
    Used to skip tests that require GDAL if it's not available.
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
    def test_get_geographic_boundaries_from_mgrs_tile(self):
        from opera.util.metadata_utils import get_geographic_boundaries_from_mgrs_tile

        """ Reproduce ADT results from values provided with code """
        lat_min, lat_max, lon_min, lon_max = get_geographic_boundaries_from_mgrs_tile('15SXR', verbose=True)

        self.assertAlmostEqual(lat_min, 31.616027943130398)
        self.assertAlmostEqual(lat_max, 32.6212369766609)
        self.assertAlmostEqual(lon_min, -91.94552881416524)
        self.assertAlmostEqual(lon_max, -90.76425651871281)

if __name__ == "__main__":
    unittest.main()
