#!/usr/bin/env python3

"""
============
img_utils.py
============

Image file utilities for use with OPERA PGEs.

"""
import os
from collections import namedtuple
from copy import deepcopy
from datetime import datetime
from functools import lru_cache
from os.path import exists


class MockGdal:  # pragma: no cover
    """
    Mock class for the osgeo.gdal module.

    This class is defined so the opera-sds-pge project does not require the
    Geospatial Data Abstraction Library (GDAL) as an explicit dependency for
    developers. When PGE code is eventually run from within a Docker container,
    osgeo.gdal should always be installed and importable.

    """

    # pylint: disable=all
    class MockDWSxHLSGdalDataset:
        """Mock class for gdal.Dataset objects, as returned from an Open call."""

        def __init__(self):
            self.dummy_metadata = {
                'ACCODE': 'LaSRC', 'AEROSOL_CLASS_REMAPPING_ENABLED': 'TRUE',
                'AEROSOL_NOT_WATER_TO_HIGH_CONF_WATER_FMASK_VALUES': '224,160,96',
                'AEROSOL_PARTIAL_SURFACE_AGGRESSIVE_TO_HIGH_CONF_WATER_FMASK_VALUES': '224,192,160,128,96',
                'AEROSOL_PARTIAL_SURFACE_WATER_CONSERVATIVE_TO_HIGH_CONF_WATER_FMASK_VALUES': '224,192,160,128,96',
                'AEROSOL_WATER_MODERATE_CONF_TO_HIGH_CONF_WATER_FMASK_VALUES': '224,160,96',
                'AREA_OR_POINT': 'Area', 'CLOUD_COVERAGE': '43',
                'DEM_COVERAGE': 'FULL', 'DEM_SOURCE': 'dem.tif',
                'FOREST_MASK_LANDCOVER_CLASSES': '20,50,111,113,115,116,121,123,125,126',
                'HLS_DATASET': 'HLS.L30.T22VEQ.2021248T143156.v2.0',
                'INPUT_HLS_PRODUCT_CLOUD_COVERAGE': '4',
                'INPUT_HLS_PRODUCT_SPATIAL_COVERAGE': '84',
                'LANDCOVER_COVERAGE': 'FULL', 'LANDCOVER_SOURCE': 'landcover.tif',
                'MASK_ADJACENT_TO_CLOUD_MODE': 'mask',
                'MAX_SUN_LOCAL_INC_ANGLE': '40',
                'MEAN_SUN_AZIMUTH_ANGLE': '145.002203258435',
                'MEAN_SUN_ZENITH_ANGLE': '30.7162834439185',
                'MEAN_VIEW_AZIMUTH_ANGLE': '100.089770731169',
                'MEAN_VIEW_ZENITH_ANGLE': '4.6016561116873',
                'MIN_SLOPE_ANGLE': '-5',
                'NBAR_SOLAR_ZENITH': '31.7503071022442',
                'OCEAN_MASKING_ENABLED': 'FALSE',
                'OCEAN_MASKING_SHORELINE_DISTANCE_KM': 'NOT_USED',
                'PROCESSING_DATETIME': '2022-01-31T21:54:26',
                'PRODUCT_ID': 'dswx_hls', 'PRODUCT_LEVEL': '3',
                'PRODUCT_SOURCE': 'HLS', 'PRODUCT_TYPE': 'DSWx-HLS',
                'PRODUCT_VERSION': '0.1', 'PROJECT': 'OPERA',
                'SENSING_TIME': '2021-09-05T14:31:56.9300799Z; 2021-09-05T14:32:20.8126470Z',
                'SENSOR': 'MSI',
                'SENSOR_PRODUCT_ID': 'S2A_MSIL1C_20210907T163901_N0301_R126_T15SXR_20210907T202434.SAFE',
                'SHADOW_MASKING_ALGORITHM': 'SUN_LOCAL_INC_ANGLE',
                'SHORELINE_SOURCE': 'shoreline.shp', 'SOFTWARE_VERSION': '0.1',
                'SPACECRAFT_NAME': 'Sentinel-2A', 'SPATIAL_COVERAGE': '99',
                'SPATIAL_COVERAGE_EXCLUDING_MASKED_OCEAN': '99',
                'WORLDCOVER_COVERAGE': 'FULL',
                'WORLDCOVER_SOURCE': 'worldcover.tif',
            }

        def GetMetadata(self):
            """
            Returns a subset of dummy metadata expected by the PGE.
            This function should be updated as needed for requisite metadata fields.
            """
            return deepcopy(self.dummy_metadata)

    # pylint: disable=all
    class MockDSWxS1GdalDataset:
        """
        Mock class for gdal.Dataset objects, as returned from an Open call.
        DSWx_-S1 metadata consists of 4 sections:
            1) Product Identification and Processing Information
            2) Sentinel-1 A/B product metadata.
            3) input ancillary datasets
            4) S1 product metadata
        """

        def __init__(self):
            self.dummy_metadata = {
                'DSWX_PRODUCT_VERSION': '0.1',
                'SOFTWARE_VERSION': '0.1',
                'PROJECT': 'OPERA',
                'PRODUCT_LEVEL': '3',
                'PRODUCT_TYPE': 'DSWx-S1',
                'PRODUCT_SOURCE': 'S1',
                'PROCESSING_DATETIME': '2022-01-31T21:54:26',
                'SPACECRAFT_NAME': 'Sentinel-1A/B',
                'SENSOR': 'IW',
                'SENSING_START': '2021-09-05T14:31:56.9300799Z',
                'SENSING_END': '2021-09-05T14:32:20.8126470Z',
                'SPATIAL_COVERAGE': '99',
                'LAYOVER_SHADOW_COVERAGE': '20',
                'RTC_PRODUCT_VERSION': '1,0',
                'POLARIZATION': 'VV',
                'BURST_ID': 't047_10092_iw1',
                'ABSOLUTE_ORBIT_NUMBER': '5',
                'ORBIT_PASS_DIRECTION': 'A',
                'TRACK_NUMBER': '7',
                'SHORELINE_SOURCE': 'shoreline.shp',
                'DEM_SOURCE': 'dem.tif',
                'REFERENCE_WATER_SOURCE': 'reference_water.tif',
                'WORLDCOVER_SOURCE': 'worldcover.tif',
                'HAND_SOURCE': 'hand.tif',
                'WORKFLOW': 'DSWx-S1-open_water',
                'THRESHOLDING': 'OTSU',
                'MULTI_THRESHOLD': False,
                'TILE_SELECTION': 'combined',
                'FILTER': 'Enhanced Lee Filter',
                'INUNDATED_VEGETATION': False,
                'FUZZY_SEED': '0.1',
                'FUZZY_TOLERANCE': '0.01',
            }

        def GetMetadata(self):
            """
            Returns a subset of dummy metadata expected by the PGE.
            This function should be updated as needed for requisite metadata fields.
            """
            return deepcopy(self.dummy_metadata)

    @staticmethod
    def Open(self, filename):
        """Mock implementation for gdal.Open. Returns an instance of the mock Dataset."""
        if not exists(filename):
            # Return None since that's what GDAL does. The utility functions need
            # to be aware of this and handle a None return accordingly.
            return None

        file_name = filename.split('/')[-1].lower()

        if 'dswx_s1' in file_name:
            return MockGdal.MockDSWxS1GdalDataset()
        else:
            return MockGdal.MockDSWxHLSGdalDataset()


def mock_gdal_edit(args):
    """Mock implementation of osgeo_utils.gdal_edit that always returns success"""
    return 0  # pragma: no cover


def mock_save_as_cog(filename, scratch_dir='.', logger=None,
                     flag_compress=True, resamp_algorithm=None):
    """Mock implementation of proteus.core.save_as_cog"""
    return  # pragma: no cover


# When running a PGE within a Docker image delivered from ADT, the following imports
# below should work. When running in a dev environment, the imports will fail,
# resulting in the mock classes being substituted instead.
try:
    from osgeo import gdal
    from osgeo_utils.gdal_edit import main as gdal_edit
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    gdal = MockGdal  # pragma: no cover
    gdal_edit = mock_gdal_edit  # pragma: no cover

try:
    from proteus.core import save_as_cog
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    save_as_cog = mock_save_as_cog  # pragma: no cover


def set_geotiff_metadata(filename, scratch_dir=os.curdir, **kwargs):
    """
    Updates one or more metadata fields within an existing GeoTIFF file via
    the gdal_edit utility.

    The updated GeoTIFF is also reconverted to a Cloud-Optimized format,
    since changing any metadata will invalidate an existing COG.

    Notes
    -----
    If this call results in any metadata updates to the GeoTIFF, the LRU cache
    associated to the get_geotiff_metadata() will be cleared so any new
    updates can be read back into memory.

    Parameters
    ----------
    filename : str
        Path to the existing GeoTIFF to update metadata for.
    scratch_dir : str, optional
        Path to a scratch directory where a temporary file may be written when
        reconverting the modified GeoTIFF to a Cloud-Optimized-GeoTIFF (COG).
        Defaults to the current directory.
    kwargs : dict
        Key/value pairs of the metadata to be updated within the existing GeoTIFF
        file. If empty, this function will simply return.

    Raises
    ------
    RuntimeError
        If the call to gdal_edit fails (non-zero return code), or if the
        reconversion to a COG fails.

    """
    if len(kwargs) < 1:
        return

    # gdal_edit expects sys.argv, where first argument should be the script name
    gdal_edit_args = ['gdal_edit.py']

    for key, value in kwargs.items():
        gdal_edit_args.append('-mo')
        gdal_edit_args.append(f'{key}={value}')

    # Last arg should be the filename of the GTiff to modify
    gdal_edit_args.append(filename)

    result = gdal_edit(gdal_edit_args)

    if result != 0:
        raise RuntimeError(f'Call to gdal_edit returned non-zero ({result})')

    # Modifying metadata breaks the Cloud-Optimized-Geotiff (COG) format,
    # so use a function from PROTEUS to restore it
    try:
        save_as_cog(filename, scratch_dir=scratch_dir)
    except Exception as err:
        raise RuntimeError(f'Call to save_as_cog failed, reason: {str(err)}')

    # Lastly, we need to clear the LRU for get_geotiff_metadata so any updates
    # made here can be pulled in on the next call
    get_geotiff_metadata.cache_clear()


@lru_cache
def get_geotiff_metadata(filename):
    """
    Returns the set of metadata fields associated to the provided GeoTIFF
    file name. The metadata returned is cached for future lookups on the same
    file name.

    Parameters
    ----------
    filename : str
        Path to the GeoTIFF file to get metadata for.

    Returns
    -------
    metadata : dict
        Dictionary of metadata fields extracted from the GeoTIFF file.

    Raises
    ------
    RuntimeError
        If the provided file name does not exist, or cannot be read by GDAL.

    """
    gdal_data = gdal.Open(filename)

    if not gdal_data:
        raise RuntimeError(
            f'Failed to read GeoTIFF file "{filename}"\n'
            f'Please ensure the file exists and is a GDAL-compatible GeoTIFF file.'
        )

    return gdal_data.GetMetadata()


def get_geotiff_hls_dataset(filename):
    """Returns the HLS_DATASET value from the provided file, if it exists. None otherwise."""
    metadata = get_geotiff_metadata(filename)

    return metadata.get('HLS_DATASET')


def get_geotiff_processing_datetime(filename):
    """
    Returns the PROCESSING_DATETIME value from the provided file, if it exists,
    as a datetime object. None otherwise.
    """
    metadata = get_geotiff_metadata(filename)
    processing_datetime = metadata.get('PROCESSING_DATETIME')

    # Strip tailing "Z" from datetime to maintain backwards compatibility with
    # previous SAS versions
    if processing_datetime.endswith('Z'):
        processing_datetime = processing_datetime[:-1]

    if processing_datetime:
        processing_datetime = datetime.strptime(processing_datetime, '%Y-%m-%dT%H:%M:%S')

    return processing_datetime


def get_geotiff_hls_product_version(filename):
    """Returns the PRODUCT_VERSION value from the provided file, if it exists. None otherwise."""
    metadata = get_geotiff_metadata(filename)

    return metadata.get('PRODUCT_VERSION')


def get_geotiff_s1_product_version(filename):
    """Returns the PRODUCT_VERSION value from the provided file, if it exists. None otherwise."""
    metadata = get_geotiff_metadata(filename)

    return metadata.get('DSWX_PRODUCT_VERSION')


def get_geotiff_hls_sensor_product_id(filename):
    """Returns the SENSOR_PRODUCT_ID value from the provided file, if it exists. None otherwise."""
    metadata = get_geotiff_metadata(filename)

    return metadata.get('SENSOR_PRODUCT_ID')


def get_geotiff_spacecraft_name(filename):
    """Returns the SPACECRAFT_NAME value from the provided file, if it exists. None otherwise."""
    metadata = get_geotiff_metadata(filename)

    return metadata.get('SPACECRAFT_NAME')


def get_hls_filename_fields(file_name):
    """
    Parse the HLS filename into components, changing Julian datetime to isoformat
    (YYYYMMDDTHHMMSS).

    Parameters
    ----------
    file_name : str
        Name of the HLS file

    Returns
    -------
    fields : Ordered Dictionary
        Keys are basic descriptions of the value
        Values are the fields parsed from the HLS file_name

    """
    Fields = namedtuple('Fields',
                        ['product', 'short_name', 'tile_id', 'acquisition_time',
                         'collection_version'])
    fields = Fields._make(file_name.split('.', maxsplit=4))._asdict()

    # Convert to 'YYYYMMDDTHHMMSS' format from Julian datetime
    julian_time = fields['acquisition_time'].split('T')
    julian_time[0] = str(datetime.strptime(julian_time[0], '%Y%j').date()).replace('-', '')
    fields['acquisition_time'] = 'T'.join(julian_time)

    return fields
