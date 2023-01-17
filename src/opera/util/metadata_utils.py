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
from mgrs.core import MGRSError

S1_SLC_HDF5_PREFIX = "/science/SENTINEL1"
"""Prefix used to index metadata within SLC-based HDF5 products"""


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
        'frequencyA' : get_hdf5_group_as_dict(file_name, f"{S1_SLC_HDF5_PREFIX}/RTC/grids/frequencyA"),
        'processingInformation' : get_hdf5_group_as_dict(file_name, f"{S1_SLC_HDF5_PREFIX}/RTC/metadata/processingInformation"),
        'orbit' : get_hdf5_group_as_dict(file_name, f"{S1_SLC_HDF5_PREFIX}/RTC/metadata/orbit"),
        'identification' : get_hdf5_group_as_dict(file_name, f"{S1_SLC_HDF5_PREFIX}/identification")
    }

    return product_output


def create_test_rtc_metadata_product(file_path):
    """
    Creates a dummy RTC HDF5 product with expected metadata fields.
    This function is intended for use with unit tests, but is included in this
    module, so it will be importable from within a built container.

    Parameters
    ----------
    file_path : str
        Full path to write the dummy RTC HDF5 product to.

    """
    with h5py.File(file_path, 'w') as outfile:
        frequencyA_grp = outfile.create_group(f"{S1_SLC_HDF5_PREFIX}/RTC/grids/frequencyA")
        centerFrequency_dset = frequencyA_grp.create_dataset("centerFrequency", data=5405000454.33435, dtype='float64')
        centerFrequency_dset.attrs['description'] = np.string_("Center frequency of the processed image in Hz")
        xCoordinateSpacing_dset = frequencyA_grp.create_dataset("xCoordinateSpacing", data=30.0, dtype='float64')
        xCoordinates_dset = frequencyA_grp.create_dataset("xCoordinates", data=np.zeros((10,)), dtype='float64')
        yCoordinateSpacing_dset = frequencyA_grp.create_dataset("yCoordinateSpacing", data=30.0, dtype='float64')
        yCoordinates_dset = frequencyA_grp.create_dataset("yCoordinates", data=np.zeros((10,)), dtype='float64')
        projection_dset = frequencyA_grp.create_dataset("projection", data=b'1234')
        listOfPolarizations_dset = frequencyA_grp.create_dataset("listOfPolarizations", data=np.array([b'VV', b'VH']))
        rangeBandwidth_dset = frequencyA_grp.create_dataset('rangeBandwidth', data=56500000.0, dtype='float64')
        azimuthBandwidth_dset = frequencyA_grp.create_dataset('azimuthBandwidth', data=56500000.0, dtype='float64')
        slantRangeSpacing_dset = frequencyA_grp.create_dataset('slantRangeSpacing', data=2.32956, dtype='float64')
        zeroDopplerTimeSpacing_dset = frequencyA_grp.create_dataset('zeroDopplerTimeSpacing', data=0.002055, dtype='float64')
        faradayRotationFlag_dset = frequencyA_grp.create_dataset('faradayRotationFlag', data=True, dtype='bool')
        noiseCorrectionFlag_dset = frequencyA_grp.create_dataset('noiseCorrectionFlag', data=True, dtype='bool')
        polarizationOrientationFlag_dset = frequencyA_grp.create_dataset('polarizationOrientationFlag', data=True, dtype='bool')
        radiometricTerrainCorrectionFlag_dset = frequencyA_grp.create_dataset('radiometricTerrainCorrectionFlag', data=True, dtype='bool')

        orbit_grp = outfile.create_group(f"{S1_SLC_HDF5_PREFIX}/RTC/metadata/orbit")
        orbitType_dset = orbit_grp.create_dataset("orbitType", data=b'POE')
        interpMethod_dest = orbit_grp.create_dataset("interpMethod", data=b'Hermite')
        referenceEpoch_dset = orbit_grp.create_dataset("referenceEpoch", data=b'2018-05-02T10:45:07.581333000')

        processingInformation_inputs_grp = outfile.create_group(f"{S1_SLC_HDF5_PREFIX}/RTC/metadata/processingInformation/inputs")
        demSource_dset = processingInformation_inputs_grp.create_dataset("demSource", data=b'dem.tif')
        auxcalFiles = np.array([b'calibration-s1b-iw1-slc-vv-20180504t104508-20180504t104533-010770-013aee-004.xml',
                                b'noise-s1b-iw1-slc-vv-20180504t104508-20180504t104533-010770-013aee-004.xml'])
        auxcalFiles_dset = processingInformation_inputs_grp.create_dataset("auxcalFiles", data=auxcalFiles)
        configFiles_dset = processingInformation_inputs_grp.create_dataset("configFiles", data=b'rtc_s1.yaml')
        l1SlcGranules = np.array([b'S1B_IW_SLC__1SDV_20180504T104507_20180504T104535_010770_013AEE_919F.zip'])
        l1SlcGranules_dset = processingInformation_inputs_grp.create_dataset("l1SlcGranules", data=l1SlcGranules)
        orbitFiles = np.array([b'S1B_OPER_AUX_POEORB_OPOD_20180524T110543_V20180503T225942_20180505T005942.EOF'])
        orbitFiles_dset = processingInformation_inputs_grp.create_dataset("orbitFiles", data=orbitFiles)

        processingInformation_algorithms_grp = outfile.create_group(
            f"{S1_SLC_HDF5_PREFIX}/RTC/metadata/processingInformation/algorithms")
        demInterpolation_dset = processingInformation_algorithms_grp.create_dataset("demInterpolation", data=b'biquintic')
        geocoding_dset = processingInformation_algorithms_grp.create_dataset("geocoding", data=b'area_projection')
        radiometricTerrainCorrection_dset = processingInformation_algorithms_grp.create_dataset("radiometricTerrainCorrection", data=b'area_projection')
        rtcVersion_dset = processingInformation_algorithms_grp.create_dataset("RTCVersion", data=b'0.2')
        isceVersion_dset = processingInformation_algorithms_grp.create_dataset("ISCEVersion", data=b'0.8.0-dev')
        s1ReaderVersion_dset = processingInformation_algorithms_grp.create_dataset("S1ReaderVersion", data=b'1.2.3')

        identification_grp = outfile.create_group(f"{S1_SLC_HDF5_PREFIX}/identification")
        absoluteOrbitNumber_dset = identification_grp.create_dataset("absoluteOrbitNumber", data=10770, dtype='int64')
        boundingPolygon_dset = identification_grp.create_dataset("boundingPolygon", data=b'POLYGON ((399015 3859970, 398975 3860000, ..., 399015 3859970))')
        burstID_dset = identification_grp.create_dataset("burstID", data=b't069_147170_iw1')
        diagnosticModeFlag_dset = identification_grp.create_dataset("diagnosticModeFlag", data=False, dtype='bool')
        isGeocodedFlag = identification_grp.create_dataset("isGeocoded", data=True, dtype='bool')
        isUrgentObservation_dset = identification_grp.create_dataset("isUrgentObservation", data=np.array([False, True]), dtype='bool')
        lookDirection_dset = identification_grp.create_dataset("lookDirection", data=b'Right')
        listOfFrequencies_dset = identification_grp.create_dataset("listOfFrequencies", data=np.array([b'A']))
        missionId_dest = identification_grp.create_dataset("missionId", data=b'S1B')
        orbitPassDirection_dset = identification_grp.create_dataset("orbitPassDirection", data=b'Descending')
        plannedDatatakeId_dset = identification_grp.create_dataset("plannedDatatakeId", data=np.array([b'datatake1', b'datatake2']))
        plannedObservationId_dset = identification_grp.create_dataset("plannedObservationId", data=np.array([b'obs1', b'obs2']))
        processingType_dset = identification_grp.create_dataset("processingType", data=b'UNDEFINED')
        productType_dset = identification_grp.create_dataset("productType", data=b'SLC')
        productVersion_dset = identification_grp.create_dataset("productVersion", data=b'1.0')
        trackNumber_dset = identification_grp.create_dataset("trackNumber", data=147170, dtype='int64')
        zeroDopplerEndTime_dset = identification_grp.create_dataset("zeroDopplerEndTime", data=b'2018-05-04T10:45:11.501279')
        zeroDopplerStartTime_dset = identification_grp.create_dataset("zeroDopplerStartTime", data=b'2018-05-04T10:45:08.436445')

def get_cslc_s1_product_metadata(file_name):
    """
    Returns a python dict containing the CSLC S1 metadata
    which will be used with the ISO metadata template.

    Parameters
    ----------
    file_name : str
        the CSLC S1 metadata file.

    Returns
    -------
    cslc_metadata : dict
        python dict containing the HDF5 file metadata which is used in the
        ISO template.
    """
    cslc_metadata = {
        'identification' : get_hdf5_group_as_dict(file_name, "/science/SENTINEL1/identification"),
        'grids' : get_hdf5_group_as_dict(file_name, "/science/SENTINEL1/CSLC/grids"),
        'corrections' : get_hdf5_group_as_dict(file_name, "/science/SENTINEL1/CSLC/corrections"),
        'processing_information' : get_hdf5_group_as_dict(file_name, "/science/SENTINEL1/CSLC/metadata/processing_information"),
        'orbit' : get_hdf5_group_as_dict(file_name, "/science/SENTINEL1/CSLC/metadata/orbit")
    }

    return cslc_metadata

def create_test_cslc_metadata_product(file_path):
    """
    Creates a dummy CSLC h5 metadata file with expected groups and datasets.
    This function is intended for use with unit tests, but is included in this
    module, so it will be importable from within a built container.

    Parameters
    ----------
    file_path : str
        Full path to write the dummy CSLC H5 metadata file to.

    """
    with h5py.File(file_path, 'w') as outfile:
        identification_grp = outfile.create_group("/science/SENTINEL1/identification")
        absolute_orbit_number_dset = identification_grp.create_dataset("absolute_orbit_number", data=43011, dtype='int64')
        burst_id_dset = identification_grp.create_dataset("burst_id", data=np.string_("t064_135518_iw1"))

        grids_grp = outfile.create_group("/science/SENTINEL1/CSLC/grids")
        projection_dset = grids_grp.create_dataset("projection", data=32611, dtype='int32')
        y_spacing_dset = grids_grp.create_dataset("y_spacing", data=-10.0, dtype='float64')

        corrections_grp = outfile.create_group("/science/SENTINEL1/CSLC/corrections")
        zero_doppler_time_spacing_dset = corrections_grp.create_dataset("zero_doppler_time_spacing", data=0.027999999991152436, dtype='float64')

        processing_information_grp = outfile.create_group("/science/SENTINEL1/CSLC/metadata/processing_information")
        algorithms_grp = outfile.create_group("/science/SENTINEL1/CSLC/metadata/processing_information/algorithms")
        COMPASS_version_dset = algorithms_grp.create_dataset("COMPASS_version", data=np.string_("0.1.3"))

        orbit_grp = outfile.create_group("/science/SENTINEL1/CSLC/metadata/orbit")
        orbit_direction_dset = orbit_grp.create_dataset("orbit_direction", data=np.string_("Ascending"))
