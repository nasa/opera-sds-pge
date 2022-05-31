#!/usr/bin/env python3
#

"""
============
metadata_utils.py
============

ISO metadata utilities for use with OPERA PGEs.

"""

from osgeo import gdal
from osgeo import osr
import mgrs

def get_geographic_boundaries_from_mgrs_tile(mgrs_tile_name, verbose=False):
    """
    Returns the Lat/Lon min/max values that comprise the bounding box for a given mgrs tile region.

    Parameters
    ----------
    mgrs_tile_name : str
        MGRS tile name
    Returns
    -------
    lat_min : float
        minimum latitude of bounding box
    lat_max : float
        maximum latitude of bounding box
    lon_min : float
        minimum longitude of bounding box
    lon_max : float
        maximum longitude of bounding box
    """
 
    mgrs_obj = mgrs.MGRS()
    lower_left_utm_coordinate = mgrs_obj.MGRSToUTM(mgrs_tile_name)
    utm_zone = lower_left_utm_coordinate[0]
    is_northern = lower_left_utm_coordinate[1] == 'N'
    x_min = lower_left_utm_coordinate[2]
    y_min = lower_left_utm_coordinate[3]
 
    # create UTM spatial reference
    utm_coordinate_system = osr.SpatialReference()
    utm_coordinate_system.SetWellKnownGeogCS("WGS84")
    utm_coordinate_system.SetUTM(utm_zone, is_northern)
 
    # create geographic (lat/lon) spatial reference
    wgs84_coordinate_system = osr.SpatialReference()
    wgs84_coordinate_system.SetWellKnownGeogCS("WGS84")
 
    # create transformation of coordinates from UTM to geographic (lat/lon)
    transformation = osr.CoordinateTransformation(utm_coordinate_system,
                                                  wgs84_coordinate_system)
 
    # compute boundaries
    elevation = 0
    lat_min = None
    lat_max = None
    lon_min = None
    lon_max = None
 
    for offset_x_multiplier in range(2):
        for offset_y_multiplier in range(2):
 
            x = x_min + offset_x_multiplier * 109.8 * 1000
            y = y_min + offset_y_multiplier * 109.8 * 1000
            lat, lon, z = transformation.TransformPoint(x, y, elevation)
 
            if verbose:
                print('')
                print('x:', x)
                print('y:', y)
                print('lon:', lon)
                print('lat:', lat)
 
            if lat_min is None or lat_min > lat:
                lat_min = lat
            if lat_max is None or lat_max < lat:
                lat_max = lat
            if lon_min is None or lon_min > lon:
                lon_min = lon
            if lon_max is None or lon_max < lon:
                lon_max = lon
 
    if verbose:
        print('')
        print('lat_min:', lat_min)
        print('lat_max:', lat_max)
        print('lon_min:', lon_min)
        print('lon_max:', lon_max)
        print('')
 
    return lat_min, lat_max, lon_min, lon_max
