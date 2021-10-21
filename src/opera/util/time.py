#
# Copyright 2021, by the California Institute of Technology.
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
=======
time.py
=======

Time-tag generation utilities for use with OPERA PGEs.

This module is adapted for OPERA from the NISAR PGE R2.0.0 util/time.py
Original Author: Alice Stanboli
Adapted By: Scott Collins

"""

from datetime import datetime


def get_current_iso_time():
    """
    Returns current time in ISO format, including trailing "Z" to indicate
    Zulu (GMT) time.

    Returns
    -------
    time_in_iso : str
        Current time in ISO format: YYYY-MM-DDTHH:MM:SS.mmmmmmZ

    """
    time_in_iso = datetime.now().isoformat(sep='T', timespec='microseconds') + "Z"

    return time_in_iso


def get_iso_time(dt):
    """
    Converts the provided datetime object to an ISO-format time-tag.

    Parameters
    ----------
    dt : datetime.datetime
        Datetime object to convert to ISO format.

    Returns
    -------
    time_in_iso : str
        Provided time in ISO format: YYYY-MM-DDTHH:MM:SS.mmmmmmZ

    """
    time_in_iso = dt.isoformat(sep='T', timespec='microseconds') + "Z"

    return time_in_iso


def get_time_for_filename(dt):
    """
    Converts the provided datetime object to a time-tag string suitable for
    use with output filenames.

    Parameters
    ----------
    dt : datetime.datetime
        Datetime object to convert to a filename time-tag.

    Returns
    -------
    datetime_str : str
        The provided time converted to YYYYMMDDTHHmmss format.

    """
    datetime_str = dt.strftime('%Y%m%dT%H%M%S')

    return datetime_str


def get_catalog_metadata_datetime_str(dt):
    """
    Converts the provided datetime object to a time-tag string suitable for use
    in catalog metadata.

    Parameters
    ----------
    dt : datetime.datetime
        Datetime object to convert to a catalog metadata time-tag string.

    Returns
    -------
    datetime_str : str
        The provided time converted to ISO format, including nanosecond
        resolution.

    """
    # TODO: Rework to support 0.1 nanosecond resolution
    # That probably means ditching Python's datetime class.
    datetime_str = dt.isoformat(sep='T', timespec='microseconds') + "0000" + "Z"

    return datetime_str
