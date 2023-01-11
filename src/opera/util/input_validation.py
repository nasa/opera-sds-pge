#!/usr/bin/env python3

"""
=================
input_validation.py
=================

Common code used by some PGEs for input validation.

"""

from os.path import exists, splitext

from opera.util.error_codes import ErrorCode


def _check_input(input_object, logger, name, valid_extensions):
    """
    Called by _validate_inputs() to check individual files.
    The input object is checked for existence and that it ends with
    a valid file extension.

    Parameters
    ----------
    input_object : str
        Relative path the object to be validated
    logger: PgeLogger
        Logger passed by PGE
    name: str
        pge name
    valid_extensions : iterable
        Expected file extensions of the file being validated.

    """
    if not exists(input_object):
        error_msg = f"Could not locate specified input {input_object}."
        logger.critical(name, ErrorCode.INPUT_NOT_FOUND, error_msg)

    ext = splitext(input_object)[-1]

    if ext not in valid_extensions:
        error_msg = f"Input file {input_object} does not have an expected file extension."
        logger.critical(name, ErrorCode.INVALID_INPUT, error_msg)


def validate_slc_s1_inputs(runconfig, logger, name):
    """
    Parameters
    ----------
    runconfig: file
        Runconfig file passed by the calling PGE
    logger: PgeLogger
        Logger passed by the calling PGE
    name:  str
        pge name

    This function is shared by the RTC-S1 and CLSC-S1 PGEs:
    Evaluates the list of inputs from the RunConfig to ensure they are valid.
    There are 2 required categories defined in the 'input_file_group':

        - safe_file_path: list
            List of SAFE files (min=1)
        - orbit_file_path : list
            List of orbit (EOF) files (min=1)

    There is also an ancillary file contained in the input_dir
        - dem_file : str

    """
    # Retrieve the input_file_group from the run config file
    input_file_group_dict = runconfig.sas_config['runconfig']['groups']['input_file_group']

    # Retrieve the dynamic_ancillary_file_group from the run config file
    dynamic_ancillary_file_group_dict = runconfig.sas_config['runconfig']['groups']['dynamic_ancillary_file_group']

    if name == 'CLSC':
        # Retrieve the static_ancillary_file_group from the run config file
        static_ancillary_file_group_dict = runconfig.sas_config['runconfig']['groups']['static_ancillary_file_group']

        # Merge the dictionaries
        input_file_group_dict = {**input_file_group_dict,
                                 **dynamic_ancillary_file_group_dict,
                                 **static_ancillary_file_group_dict}
    else:
        # Merge the dictionaries
        input_file_group_dict = {**input_file_group_dict, **dynamic_ancillary_file_group_dict}

    for key, value in input_file_group_dict.items():
        if key == 'safe_file_path':
            for i in range(len(value)):
                _check_input(value[i], logger, name,  valid_extensions=('.zip',))
        elif key == 'orbit_file_path':
            for i in range(len(value)):
                _check_input(value[i], logger, name, valid_extensions=('.EOF',))
        elif key == 'dem_file':
            _check_input(value, logger, name, valid_extensions=('.tif', '.tiff', '.vrt'))
        elif key in ('burst_id', 'dem_description'):
            # these fields are included in the SAS input paths, but are not
            # actually file paths, so skip them
            continue
        elif key == 'burst_database_file':
            _check_input(value, logger, name, valid_extensions=('.sqlite3',))
        else:
            error_msg = f"Unexpected input: {key}: {value}"
            logger.critical(name, ErrorCode.INVALID_INPUT, error_msg)
