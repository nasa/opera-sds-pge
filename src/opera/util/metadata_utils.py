#!/usr/bin/env python3

"""
=================
metadata_utils.py
=================

ISO metadata utilities for use with OPERA PGEs.

"""

from functools import lru_cache
import h5py
import numpy as np
import mgrs

class MockOsr:  # pragma: no cover
    """
    Mock class for the osgeo.osr module.

    This class is defined so the opera-sds-pge project does not require the
    Geospatial Data Abstraction Library (GDAL) as an explicit dependency for
    developers. When PGE code is eventually run from within a Docker container,
    osgeo.osr should always be installed and importable.
    """

    # pylint: disable=all
    class MockSpatialReference:
        """Mock class for the osgeo.osr module"""

        def SetWellKnownGeogCS(self, name):
            """Mock implementation for osr.SetWellKnownGeogCS"""
            pass

        def SetUTM(self, zone, north=True):
            """Mock implementation for osr.SetUTM"""
            self.zone = zone
            self.hemi = "N" if north else "S"

    class MockCoordinateTransformation:
        """Mock class for the osgeo.osr.CoordinateTransformation class"""

        def __init__(self, src, dest):
            self.src = src
            self.dest = dest

        def TransformPoint(self, x, y, z):
            """Mock implementation for CoordinateTransformation.TransformPoint"""
            # Use mgrs to convert UTM back to a tile ID, then covert to rough
            # lat/lon, this should be accurate enough for development testing
            mgrs_obj = mgrs.MGRS()
            mgrs_tile = mgrs_obj.UTMToMGRS(self.src.zone, self.src.hemi, x, y)
            lat, lon = mgrs_obj.toLatLon(mgrs_tile)
            return lat, lon, z

    @staticmethod
    def SpatialReference():
        """Mock implementation for osgeo.osr.SpatialReference"""
        return MockOsr.MockSpatialReference()

    @staticmethod
    def CoordinateTransformation(src, dest):
        """Mock implementation for osgeo.osr.CoordinateTransformation"""
        return MockOsr.MockCoordinateTransformation(src, dest)


# When running a PGE within a Docker image delivered from ADT, the gdal import
# below should work. When running in a dev environment, the import will fail
# resulting in the MockGdal class being substituted instead.
try:
    from osgeo import osr
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    osr = MockOsr                           # pragma: no cover


def get_sensor_from_spacecraft_name(spacecraft_name):
    """
    Returns the HLS sensor short name from the full spacecraft name.
    The short name is used with output file naming conventions for DSWx-HLS
    products

    Parameters
    ----------
    spacecraft_name : str
        Name of the spacecraft to translate to a sensor short name.

    Returns
    -------
    sensor_shortname : str
        The sensor shortname for the provided spacecraft name

    Raises
    ------
    RuntimeError
        If an unknown spacecraft name is provided.

    """
    try:
        return {
            'LANDSAT-8': 'L8',
            'LANDSAT-9': 'L9',
            'SENTINEL-2A': 'S2A',
            'SENTINEL-2B': 'S2B'
        }[spacecraft_name.upper()]
    except KeyError:
        raise RuntimeError(f"Unknown spacecraft name '{spacecraft_name}'")


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

            if lat_min is None or lat_min > lat:
                lat_min = lat
            if lat_max is None or lat_max < lat:
                lat_max = lat
            if lon_min is None or lon_min > lon:
                lon_min = lon
            if lon_max is None or lon_max < lon:
                lon_max = lon

    return lat_min, lat_max, lon_min, lon_max


@lru_cache
def get_hdf5_group_as_dict(file_name, group_path):
    """
    Returns HDF5 group variable data as a python dict for a given file and group path.
    Group attributes are not included.

    Parameters
    ----------
    file_name : str
        file system path and filename for the HDF5 file to use.
    group_path : str
        group path within the HDF5 file.

    Returns
    -------
    group_dict : dict
        python dict containing variable data from the group path location.
    """
    group_dict = {}
    with h5py.File(file_name, 'r') as hf:
        group_object = hf.get(group_path)
        if group_object is None:
            raise RuntimeError(f"An error occurred retrieving group '{group_path}' from file '{file_name}'.")

        group_dict = convert_h5py_group_to_dict(group_object)

    return group_dict


def convert_h5py_group_to_dict(group_object):
    """
    Returns HDF5 group variable data as a python dict for a given h5py group object.
    Recursively calls itself to process sub-groups.
    Group attributes are not included.
    Byte sequences are converted to python strings which will probably cause issues
    with non-text data.

    Parameters
    ----------
    group_object : h5py._hl.group.Group
        h5py Group object to be converted to a dict.

    Returns
    -------
    converted_dict : dict
        python dict containing variable data from the group object.
        data is copied from the h5py group object to a python dict.
    """
    converted_dict = {}
    for key,val in group_object.items():

        if isinstance(val, h5py.Dataset):
            if type(val[()]) is np.ndarray:
                if isinstance(val[0], (bytes, np.bytes_)):
                    # decode bytes to str
                    converted_dict[key] = val.asstr()[()]
                else:
                    converted_dict[key] = val[()]
            else:
                if isinstance(val[()], (bytes, np.bytes_)):
                    # decode bytes to str
                    converted_dict[key] = val.asstr()[()]
                else:
                    converted_dict[key] = val[()]
        elif isinstance(val, h5py.Group):
            converted_dict[key] = convert_h5py_group_to_dict(val)

    return converted_dict


def get_rtc_s1_product_metadata(file_name):
    """
    Returns a python dict containing the RTC-S1 product_output metadata
    which will be used with the ISO metadata template.

    Parameters
    ----------
    file_name : str
        the RTC-S1 product file to obtain metadata from.

    Returns
    -------
    product_output : dict
        python dict containing the HDF5 file metadata which is used in the
        ISO template.
    """
    product_output = {
        'frequencyA' : get_hdf5_group_as_dict(file_name, "/science/CSAR/RTC/grids/frequencyA"),
        'processingInformation' : get_hdf5_group_as_dict(file_name, "/science/CSAR/RTC/metadata/processingInformation"),
        'orbit' : get_hdf5_group_as_dict(file_name, "/science/CSAR/RTC/metadata/orbit"),
        'identification' : get_hdf5_group_as_dict(file_name, "/science/CSAR/identification")
    }

    return product_output
