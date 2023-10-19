#!/usr/bin/env python3

"""
=================
dataset_utils.py
=================

Utilities used to to input datasets and generate and filenames.

"""

import re
from collections import namedtuple
from datetime import datetime


def get_hls_filename_fields(file_name):
    """
    Parse the HLS filename into components, changing Julian datetime to iso-format
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


def get_burst_id_from_file_name(file_name):
    """
    Extracts and returns the burst ID from the provided file name.

    Parameters
    ----------
    file_name : str
        File name to extract the burst ID from.

    Returns
    -------
    burst_id : str
        The extracted burst ID.

    """
    burst_id_regex = r'[T|t]\w{3}[-|_]\d{6}[-|_][I|i][W|w][1|2|3]'

    result = re.search(burst_id_regex, file_name)

    if result:
        burst_id = result.group(0)
    else:
        raise ValueError(f'Could not parse Burst ID from HDF5 product {file_name}')

    return burst_id


def get_sensor_from_spacecraft_name(spacecraft_name):
    """
    Returns the sensor short name from the full spacecraft name.
    The short name is used with output file naming conventions for PGE
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
            'SENTINEL-1A': 'S1A',
            'SENTINEL-1B': 'S1B',
            'SENTINEL-2A': 'S2A',
            'SENTINEL-2B': 'S2B'
        }[spacecraft_name.upper()]
    except KeyError:
        raise RuntimeError(f"Unknown spacecraft name '{spacecraft_name}'")
