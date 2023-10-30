#!/usr/bin/env python3

"""
=============
tiff_utils.py
=============

Utilities related to setting/getting metadata to/from geotiff files.

"""
import contextlib
import io
import os
from datetime import datetime
from functools import lru_cache

from opera.util.mock_utils import MockGdal, mock_gdal_edit, mock_save_as_cog

# When running a PGE within a Docker image delivered from ADT, the following imports
# below should work. When running in a dev environment, the imports will fail,
# resulting in the mock classes being substituted instead.
# pylint: disable=import-error,invalid-name
try:
    from osgeo import gdal
    from osgeo_utils.gdal_edit import main as gdal_edit

    gdal.UseExceptions()
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    gdal = MockGdal  # pragma: no cover
    gdal_edit = mock_gdal_edit  # pragma: no cover


# Search for an available implementation of save_as_cog from the underlying
# SAS library. Fallback to the mock implementation if we cannot find any.
# pylint: enable=invalid-name
try:
    from proteus.core import save_as_cog        # noinspection PyUnresolvedReferences,
except (ImportError, ModuleNotFoundError):      # pragma: no cover
    try:
        from rtc.core import save_as_cog        # noinspection PyUnresolvedReferences
    except (ImportError, ModuleNotFoundError):  # pragma: no cover
        save_as_cog = mock_save_as_cog  # pragma: no cover
# pylint: enable=import-error


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
    # so use a function from the SAS to restore it
    stdout = io.StringIO()
    stderr = io.StringIO()

    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            save_as_cog(filename, scratch_dir=scratch_dir)
        except Exception as err:
            raise RuntimeError(
                f'Call to save_as_cog failed, reason: {str(err)}, stderr: {stderr.getvalue()}'
            )

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
