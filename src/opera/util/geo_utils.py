#!/usr/bin/env python3

"""
============
geo_utils.py
============

Utilities used for working with geographic coordinates

"""


import mgrs
from mgrs.core import MGRSError
from unittest.mock import MagicMock

from opera.util.dataset_utils import parse_bounding_polygon_from_wkt
from opera.util.mock_utils import MockOsr

# When running a PGE within a Docker image delivered from ADT, the gdal import
# below should work. When running in a dev environment, the import will fail
# resulting in the MockGdal class being substituted instead.

# pylint: disable=invalid-name
try:
    from osgeo import osr

    osr.UseExceptions()
except ImportError:  # pragma: no cover
    osr = MockOsr                           # pragma: no cover
# pylint: enable=invalid-name

# Not all PGEs require the opera_utils and shapely libraries. The imports
# below should work for those that require it, but will fall back to 
# MagicMocks for those that don't.

# pylint: disable=import-error,invalid-name 
try:
    import opera_utils
    from shapely import union_all, affinity
    from shapely.geometry import MultiPolygon
except (ImportError, ModuleNotFoundError): # pragma: no cover
    opera_utils = MagicMock()           # pragma: no cover
    union_all = MagicMock()             # pragma: no cover
    affinity = MagicMock()              # pragma: no cover
    MultiPolygon = MagicMock()          # pragma: no cover
# pylint: enable=import-error,invalid-name 


def translate_utm_bbox_to_lat_lon(bbox, epsg_code):
    """
    Translates a bounding box defined in UTM coordinates to Lat/Lon.

    Parameters
    ----------
    bbox : iterable
        The bounding box to transform. Expected order is xmin, ymin, xmax, ymax.
    epsg_code : int
        The EPSG code associated with the bounding box UTM coordinate convention.

    Raises
    ------
    RuntimeError
        If the coordinate transformation fails for any reason.

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
    # Set up the coordinate systems and point transformation objects
    utm_coordinate_system = osr.SpatialReference()
    result = utm_coordinate_system.ImportFromEPSG(epsg_code)

    if result:
        raise RuntimeError(f'Unrecognized EPSG code: {epsg_code}')

    wgs84_coordinate_system = osr.SpatialReference()
    wgs84_coordinate_system.SetWellKnownGeogCS("WGS84")

    transformation = osr.CoordinateTransformation(utm_coordinate_system, wgs84_coordinate_system)

    # Transform the min/max points from UTM to Lat/Lon
    elevation = 0
    xmin, ymin, xmax, ymax = bbox

    lat_min, lon_min, _ = transformation.TransformPoint(xmin, ymin, elevation)
    lat_max, lon_max, _ = transformation.TransformPoint(xmax, ymax, elevation)

    return lat_min, lat_max, lon_min, lon_max


def get_geographic_boundaries_from_mgrs_tile(mgrs_tile_name):
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

    Raises
    ------
    RuntimeError
        If an invalid MGRS tile code is provided.

    """
    # mgrs_tile_name may begin with the letter T which must be removed
    if mgrs_tile_name.startswith('T'):
        mgrs_tile_name = mgrs_tile_name[1:]

    mgrs_obj = mgrs.MGRS()

    try:
        lower_left_utm_coordinate = mgrs_obj.MGRSToUTM(mgrs_tile_name)
    except MGRSError as err:
        raise RuntimeError(
            f'Failed to convert MGRS tile name "{mgrs_tile_name}" to lat/lon, '
            f'reason: {str(err)}'
        )

    utm_zone = lower_left_utm_coordinate[0]
    is_northern = lower_left_utm_coordinate[1] == 'N'
    x_min = lower_left_utm_coordinate[2]  # east
    y_min = lower_left_utm_coordinate[3]  # north

    # create UTM spatial reference
    utm_coordinate_system = osr.SpatialReference()
    utm_coordinate_system.SetWellKnownGeogCS("WGS84")
    utm_coordinate_system.SetUTM(utm_zone, is_northern)

    # create geographic (lat/lon) spatial reference
    wgs84_coordinate_system = osr.SpatialReference()
    wgs84_coordinate_system.SetWellKnownGeogCS("WGS84")

    # create transformation of coordinates from UTM to geographic (lat/lon)
    transformation = osr.CoordinateTransformation(
        utm_coordinate_system, wgs84_coordinate_system
    )

    # compute boundaries
    elevation = 0
    lat_min = None
    lat_max = None
    lon_min = None
    lon_max = None

    for offset_x_multiplier in range(2):
        for offset_y_multiplier in range(2):
            # We are using MGRS 100km x 100km tiles
            # HLS tiles have 4.9 km of margin => width/length = 109.8 km
            x = x_min - 4.9 * 1000 + offset_x_multiplier * 109.8 * 1000   # pylint: disable=invalid-name
            y = y_min - 4.9 * 1000 + offset_y_multiplier * 109.8 * 1000   # pylint: disable=invalid-name

            lat, lon, z = transformation.TransformPoint(x, y, elevation)  # pylint: disable=invalid-name,unused-variable

            # wrap longitude values within the range [-180, +180]
            if lon < -180:
                lon += 360
            elif lon > 180:
                lon -= 360

            if lat_min is None or lat_min > lat:
                lat_min = lat
            if lat_max is None or lat_max < lat:
                lat_max = lat

            # The computation of min and max longitude values may be affected
            # by antimeridian crossing. Notice that: 179 degrees +
            # 2 degrees = -179 degrees
            #
            # The condition `abs(lon_min - lon) < 180`` tests if both longitude
            # values are both at the same side of the dateline (either left
            # or right).
            #
            # The conditions `> 100` and `< 100` are used to test if the
            # longitude point is on the left side of the antimeridian crossing
            # (`> 100`) or on the right side (`< 100`)
            #
            # We also want to check if the point is at the west or east
            # side of the tile.
            # Points at the west, i.e, where offset_x_multiplier == 0
            # may update `lon_min`
            if (offset_x_multiplier == 0 and
                    (lon_min is None or
                     (abs(lon_min - lon) < 180 and lon_min > lon) or
                     (lon > 100 and lon_min < -100))):
                lon_min = lon

            # Points at the east, i.e, where offset_x_multiplier == 1
            # may update `lon_max`
            if (offset_x_multiplier == 1 and
                    (lon_max is None or
                     (abs(lon_max - lon) < 180 and lon_max < lon) or
                     (lon < -100 and lon_max > 100))):
                lon_max = lon

    return lat_min, lat_max, lon_min, lon_max


def get_gml_polygon_from_frame(frame_id, frame_geometries):
    """
    Returns the GML formatted polygon string for a single frame.

    Parameters
    ----------
    frame_id : int
        The ID of the frame to get the bounding box for.
    frame_geometries : str
        The path to the geojson containing frame geometries.

    Returns
    -------
    bounding_polygon_gml_str : str
        GML formatted bounding polygon string
        
    """
    gdf_frames = opera_utils.get_frame_geodataframe(
        frame_ids=[frame_id],
        json_file=frame_geometries
    )
    
    polygon = gdf_frames.loc[frame_id].geometry
    
    # Handles the case where polygon crosses the anti-meridian
    # Translate the polygon with negative longitudes to be right of +180
    if isinstance(polygon, MultiPolygon):
        gg_neg, gg_pos = polygon.geoms
        polygon = union_all([gg_pos, affinity.translate(gg_neg, 360)])

    bounding_polygon_gml_str = parse_bounding_polygon_from_wkt(polygon.wkt)
    return bounding_polygon_gml_str
