#!/usr/bin/env python3
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


def get_iso_time(date_time):
    """
    Converts the provided datetime object to an ISO-format time-tag.

    Parameters
    ----------
    date_time : datetime.datetime
        Datetime object to convert to ISO format.

    Returns
    -------
    time_in_iso : str
        Provided time in ISO format: YYYY-MM-DDTHH:MM:SS.mmmmmmZ

    """
    time_in_iso = date_time.isoformat(sep='T', timespec='microseconds') + "Z"

    return time_in_iso


def get_time_for_filename(date_time):
    """
    Converts the provided datetime object to a time-tag string suitable for
    use with output filenames.

    Parameters
    ----------
    date_time : datetime.datetime
        Datetime object to convert to a filename time-tag.

    Returns
    -------
    datetime_str : str
        The provided time converted to YYYYMMDDTHHmmss format.

    """
    datetime_str = date_time.strftime('%Y%m%dT%H%M%S')

    return datetime_str


def get_catalog_metadata_datetime_str(date_time):
    """
    Converts the provided datetime object to a time-tag string suitable for use
    in catalog metadata.

    Parameters
    ----------
    date_time : datetime.datetime
        Datetime object to convert to a catalog metadata time-tag string.

    Returns
    -------
    datetime_str : str
        The provided time converted to ISO format, including nanosecond
        resolution.

    """
    # TODO: Rework to support 0.1 nanosecond resolution
    #       That probably means ditching Python's datetime class.
    datetime_str = date_time.isoformat(sep='T', timespec='microseconds') + "0000" + "Z"

    return datetime_str
