#!/usr/bin/env python

"""
=================
test_geo_utils.py
=================

Unit tests for the util/geo_utils.py module.

"""

import os
import unittest
from importlib.resources import files
from os.path import abspath, join
from unittest import skipIf

from opera.test import path

from opera.util.geo_utils import get_geographic_boundaries_from_mgrs_tile
from opera.util.geo_utils import translate_utm_bbox_to_lat_lon
from opera.util.geo_utils import get_gml_polygon_from_frame


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


def opera_utils_is_available():
    """
    Helper function to check for a local installation of the
    opera_utils library. 
    Used to skip tests that require opera_utils if it is not available.
    """
    try:
        import opera_utils # noqa: F401
        return True
    except (ImportError, ModuleNotFoundError):
        return False


class GeoUtilsTestCase(unittest.TestCase):
    """Unit test Image Utilities"""

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

    @skipIf(not osr_is_available(), reason="osgeo.osr is not installed on the local instance")
    def test_get_geographic_boundaries_from_mgrs_tile_nominal(self):
        """Reproduce ADT results from values provided with code"""
        lat_min, lat_max, lon_min, lon_max = get_geographic_boundaries_from_mgrs_tile('15SXR')

        self.assertAlmostEqual(lat_min, 31.572733739486036)
        self.assertAlmostEqual(lat_max, 32.577473659397235)
        self.assertAlmostEqual(lon_min, -91.99766472766642)
        self.assertAlmostEqual(lon_max, -90.81751155385777)

    @skipIf(not osr_is_available(), reason="osgeo.osr is not installed on the local instance")
    def test_get_geographic_boundaries_from_mgrs_tile_leading_T(self):
        """Test MGRS tile code conversion when code starts with T"""
        lat_min, lat_max, lon_min, lon_max = get_geographic_boundaries_from_mgrs_tile('T15SXR')

        self.assertAlmostEqual(lat_min, 31.572733739486036)
        self.assertAlmostEqual(lat_max, 32.577473659397235)
        self.assertAlmostEqual(lon_min, -91.99766472766642)
        self.assertAlmostEqual(lon_max, -90.81751155385777)

    @skipIf(not osr_is_available(), reason="osgeo.osr is not installed on the local instance")
    def test_get_geographic_boundaries_from_mgrs_tile_invalid_tile(self):
        """Test MGRS tile code conversion with an invalid code"""
        self.assertRaises(RuntimeError, get_geographic_boundaries_from_mgrs_tile, 'X15SXR')

    @skipIf(not osr_is_available(), reason="osgeo.osr is not installed on the local instance")
    def test_get_geographic_boundaries_from_mgrs_tile_nominal_antimeridian(self):
        """Test MGRS tile code conversion with a tile that crosses the anti-meridian"""
        lat_min, lat_max, lon_min, lon_max = get_geographic_boundaries_from_mgrs_tile('T60VXQ')

        self.assertAlmostEqual(lat_min, 62.13198085489144)
        self.assertAlmostEqual(lat_max, 63.16076767648831)
        self.assertAlmostEqual(lon_min, 178.82637550795243)
        self.assertAlmostEqual(lon_max, -178.93677941363356)

    @skipIf(not osr_is_available(), reason="osgeo.osr is not installed on the local instance")
    def test_translate_utm_bbox_to_lat_lon(self):
        """Test translation of a UTM bounding box to lat/lon"""
        # Derived from bounding box of static layer products for granule
        # S1B_IW_SLC__1SDV_20180504T104507_20180504T104535_010770_013AEE_919F
        utm_bounding_box = [200700.0, 9391650.0, 293730.0, 9440880.0]
        epsg_code = 32718  # UTM S Zone 18

        lat_lon_bounding_box = translate_utm_bbox_to_lat_lon(utm_bounding_box, epsg_code)
        expected_bounding_box = [-5.497645682689766,  # lat_min
                                 -5.055731551544852,  # lat_max
                                 -77.70109080363252,  # lon_min
                                 -76.86056393945721]  # lon_max

        # Round off last couple digits since they can vary based on precision error
        lat_lon_bounding_box = list(map(lambda x: round(x, ndigits=12), lat_lon_bounding_box))
        expected_bounding_box = list(map(lambda x: round(x, ndigits=12), expected_bounding_box))

        self.assertListEqual(list(lat_lon_bounding_box), expected_bounding_box)

    @skipIf(not opera_utils_is_available(), reason="opera_utils is not installed on the local instance")
    def test_bounding_polygon_from_frame(self):
        """
        Test execution of the get_polygon_str_from_frame function which extracts 
        geospatial information for a given frame and converts to a polygon wkt string.
        Runs for a nominal frame as well as a frame known to cross the antimeridian,
        testing both Polygon and Multipolygon support in the function.
        """
        FRAME_GEOMETRIES = str(files('opera').joinpath('pge/disp_s1/data/frame-geometries-simple-0.9.0.geojson'))
        
        # Test nominal frame
        bounding_polygon_gml_str = get_gml_polygon_from_frame(11115, FRAME_GEOMETRIES)
        self.assertTrue(bounding_polygon_gml_str.startswith("("))
        self.assertTrue(bounding_polygon_gml_str.endswith(")"))
        self.assertTrue(all([float(n) for n in bounding_polygon_gml_str.strip("()").split()]))
        
        # Test antimeridian crossing frame
        # All longitudes should be positive (all lats already are for this frame)
        bounding_polygon_gml_str = get_gml_polygon_from_frame(7882, FRAME_GEOMETRIES)        
        self.assertTrue(all(float(n) >= 0 for n in bounding_polygon_gml_str.strip("()").split()))
        