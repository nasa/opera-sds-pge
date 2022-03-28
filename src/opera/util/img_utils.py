#!/usr/bin/env python3
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
============
img_utils.py
============

Image file utilities for use with OPERA PGEs.

"""

from collections import namedtuple
from datetime import datetime
from functools import cache
from os.path import exists


class MockGdal:  # pragma: no cover
    """
    Mock class for the osgeo.gdal module.

    This class is defined so the opera-sds-pge project does not require the
    Geospatial Data Abstraction Library (GDAL) as an explicit dependency for
    developers. When PGE code is eventually run from within a Docker container,
    osgeo.gdal should always be installed and importable.

    """

    class MockGdalDataset:
        """Mock class for gdal.Dataset objects, as returned from an Open call."""

        def GetMetadata(self):
            """
            Returns a subset of dummy metadata expected by the PGE.
            This function should be updated as needed for requisite metadata fields.
            """
            return {
                'BUILT_UP_COVER_FRACTION_FILE': '(not provided)',
                'CLOUD_COVERAGE': '43', 'DEM_FILE': '(not provided)',
                'HLS_DATASET': 'HLS.L30.T22VEQ.2021248T143156.v2.0',
                'LANDCOVER_FILE': '(not provided)', 'LEVEL': '3',
                'MEAN_SUN_AZIMUTH_ANGLE': '145.002203258435',
                'MEAN_SUN_ZENITH_ANGLE': '30.7162834439185',
                'MEAN_VIEW_AZIMUTH_ANGLE': '100.089770731169',
                'MEAN_VIEW_ZENITH_ANGLE': '4.6016561116873',
                'NBAR_SOLAR_ZENITH': '31.7503071022442',
                'PROCESSING_DATETIME': '2022-01-31T21:54:26',
                'PRODUCT_ID': 'dswx_hls', 'PRODUCT_SOURCE': 'HLS',
                'PRODUCT_TYPE': 'DSWx', 'PRODUCT_VERSION': '0.1',
                'PROJECT': 'OPERA', 'SENSING_TIME': '2021-09-07T16:54:47.751044Z',
                'SENSOR': 'MSI', 'SPACECRAFT_NAME': 'SENTINEL-2A',
                'SPATIAL_COVERAGE': '99'
            }

    @staticmethod
    def Open(filename):
        """Mock implementation for gdal.Open. Returns an instance of the mock Dataset."""
        if not exists(filename):
            # Return None since that's what GDAL does. The utility functions need
            # to be aware of this and handle a None return accordingly.
            return None

        return MockGdal.MockGdalDataset()


# When running a PGE within a Docker image delivered from ADT, the gdal import
# below should work. When running in a dev environment, the import will fail
# resulting in the MockGdal class being substituted instead.
try:
    from osgeo import gdal
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    gdal = MockGdal                         # pragma: no cover


@cache
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
    """Returns the PROCESSING_DATETIME value from the provided file, if it exists. None otherwise."""
    metadata = get_geotiff_metadata(filename)

    return metadata.get('PROCESSING_DATETIME')


def get_geotiff_product_version(filename):
    """Returns the PRODUCT_VERSION value from the provided file, if it exists. None otherwise."""
    metadata = get_geotiff_metadata(filename)

    return metadata.get('PRODUCT_VERSION')


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
