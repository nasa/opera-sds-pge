#!/usr/bin/env python3

"""
=================
input_validation.py
=================

Common code used by some PGEs for input validation.

"""
import glob
from os.path import abspath, exists, getsize, isdir, isfile, join, splitext

import yamale

from opera.util.error_codes import ErrorCode


def check_input(input_object, logger, name, valid_extensions=None, check_zero_size=False):
    """
    Validation checks for individual files.
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
    valid_extensions : iterable, optional
        Expected file extensions of the file being validated. If not provided,
        no extension checking will take place.
    check_zero_size : boolean, optional
        If true, raise an exception for zero-size input objects

    """
    # The input object path must be explicitly tested for 'None' before os.path.exists() executes.
    if input_object is None:
        error_msg = f"TypeError: {input_object} is NoneType."
        logger.critical(name, ErrorCode.INPUT_NOT_FOUND, error_msg)

    if not exists(input_object):
        error_msg = f"Could not locate specified input {input_object}."
        logger.critical(name, ErrorCode.INPUT_NOT_FOUND, error_msg)

    if valid_extensions:
        ext = splitext(input_object)[-1]

        if ext not in valid_extensions:
            error_msg = f"Input file {input_object} does not have an expected file extension."
            logger.critical(name, ErrorCode.INVALID_INPUT, error_msg)

    if check_zero_size is True:
        file_size = getsize(input_object)
        if not file_size > 0:
            error_msg = f"Input file {input_object} size is {file_size}. Size must be greater than 0."
            logger.critical(name, ErrorCode.INVALID_INPUT, error_msg)


def check_input_list(list_of_input_objects, logger, name, valid_extensions=None, check_zero_size=False):
    """Call check_input for a list of input objects."""
    for input_object in list_of_input_objects:
        check_input(input_object, logger, name, valid_extensions=valid_extensions, check_zero_size=check_zero_size)


def validate_slc_s1_inputs(runconfig, logger, name):
    """
    This function is shared by the RTC-S1 and CSLC-S1 PGEs:
    Evaluates the list of inputs from the RunConfig to ensure they are valid.
    There are 2 required categories defined in the 'input_file_group':

        - safe_file_path: list
            List of SAFE files (min=1)
        - orbit_file_path : list
            List of orbit (EOF) files (min=1)

    There is also an ancillary file contained in the input_dir
        - dem_file : str

    Parameters
    ----------
    runconfig: file
        Runconfig file passed by the calling PGE
    logger: PgeLogger
        Logger passed by the calling PGE
    name:  str
        pge name

    """
    # Retrieve the input_file_group from the run config file
    input_file_group_dict = runconfig.sas_config['runconfig']['groups']['input_file_group']

    # Retrieve the dynamic_ancillary_file_group from the run config file
    dynamic_ancillary_file_group_dict = runconfig.sas_config['runconfig']['groups']['dynamic_ancillary_file_group']

    # Retrieve the static_ancillary_file_group from the run config file
    static_ancillary_file_group_dict = runconfig.sas_config['runconfig']['groups']['static_ancillary_file_group']

    # Merge the dictionaries
    input_file_group_dict = {**input_file_group_dict,
                             **dynamic_ancillary_file_group_dict,
                             **static_ancillary_file_group_dict}

    for key, value in input_file_group_dict.items():
        if key == 'safe_file_path':
            for i in range(len(value)):
                check_input(value[i], logger, name, valid_extensions=('.zip',))
        elif key == 'orbit_file_path':
            for i in range(len(value)):
                check_input(value[i], logger, name, valid_extensions=('.EOF',))
        elif key == 'dem_file':
            check_input(value, logger, name, valid_extensions=('.tif', '.tiff', '.vrt'))
        elif key == 'tec_file':
            check_input(value, logger, name)
        elif key == 'weather_model_file':
            # TODO: this might be utilized as an ancillary with later deliveries,
            #       but no example available currently
            continue
        elif key in ('burst_id', 'dem_description', 'dem_file_description'):
            # these fields are included in the SAS input paths, but are not
            # actually file paths, so skip them
            continue
        elif key == 'burst_database_file':
            check_input(value, logger, name, valid_extensions=('.sqlite3',))
        else:
            error_msg = f"Unexpected input: {key}: {value}"
            logger.critical(name, ErrorCode.INVALID_INPUT, error_msg)


def validate_disp_inputs(runconfig, logger, name):
    """
    Evaluates the list of inputs from the RunConfig to ensure they are valid.

    The input products for DISP-S1 can be classified into two groups:
        1) the main input products (the CSLC burst products) and
        2) the ancillary input products (DEM, geometry, amplitude mean/distortion,
           water mask, tec files, and weather model).

    Parameters
    ----------
    runconfig: file
        Runconfig file passed by the calling PGE
    logger: PgeLogger
        Logger passed by the calling PGE
    name:  str
        pge name
    """
    input_file_group = runconfig.sas_config['runconfig']['groups']['input_file_group']
    dyn_anc_file_group = runconfig.sas_config['runconfig']['groups']['dynamic_ancillary_file_group']

    check_input_list(input_file_group['cslc_file_list'], logger, name,
                     valid_extensions=('.h5',), check_zero_size=True)

    if 'amplitude_dispersion_files' in dyn_anc_file_group:
        check_input_list(dyn_anc_file_group['amplitude_dispersion_files'], logger, name,
                         valid_extensions=('.tif', '.tiff'), check_zero_size=True)

    if 'amplitude_mean_files' in dyn_anc_file_group:
        check_input_list(dyn_anc_file_group['amplitude_mean_files'], logger, name,
                         valid_extensions=('.tif', '.tiff'), check_zero_size=True)

    if 'geometry_files' in dyn_anc_file_group:
        check_input_list(dyn_anc_file_group['geometry_files'], logger, name,
                         valid_extensions=('.h5',), check_zero_size=True)

    if 'mask_file' in dyn_anc_file_group:
        check_input_list(dyn_anc_file_group['mask_file'], logger, name,
                         valid_extensions=('.tif', '.tiff'), check_zero_size=True)

    if 'dem_file' in dyn_anc_file_group:
        check_input(dyn_anc_file_group['dem_file'], logger, name,
                    valid_extensions=('.tif', '.tiff'), check_zero_size=True)

    if 'tec_files' in dyn_anc_file_group:
        check_input_list(dyn_anc_file_group['tec_files'], logger, name,
                         check_zero_size=True)

    if 'weather_model_files' in dyn_anc_file_group:
        check_input_list(dyn_anc_file_group['weather_model_files'], logger, name,
                         valid_extensions=('.nc', '.h5',), check_zero_size=True)


def validate_dswx_inputs(runconfig, logger, name, valid_extensions=None):
    """
    This function is shared by the DSWX-HLS and DSWX-S1 PGEs:
    Evaluates the list of main inputs from the RunConfig to ensure they are valid.
    DSWX-S1 ancillary input validation is performed by the DSWX-S1 pge.

    For directories, this means checking for directory existence, and that
    at least one file of each required type resides within the directory. For files,
    each file is checked for existence and that it has an appropriate extension.

    Expected file extensions in the input_dir
        - dswx-hls : .tif (min=1)
        - dswx-s1 : .tif (min=1), .h5 (min-1)

    Parameters
    ----------
    runconfig: file
        Runconfig file passed by the calling PGE
    logger: PgeLogger
        Logger passed by the calling PGE
    name:  str
        PGE name
    valid_extensions : list, optional
        The list of expected extensions for input files to have. If not provided,
        no extension checking is performed

    """
    for input_file in runconfig.input_files:
        input_file_path = abspath(input_file)

        if not exists(input_file_path):
            error_msg = f"Could not locate specified input file/directory {input_file_path}"

            logger.critical(name, ErrorCode.INPUT_NOT_FOUND, error_msg)
        elif isdir(input_file_path):
            for extension in valid_extensions:
                list_of_inputs = glob.glob(join(input_file_path, f'*{extension}*'))

                if len(list_of_inputs) <= 0:
                    error_msg = f"Input directory {input_file_path} does not contain any {extension} files"

                    logger.critical(name, ErrorCode.INPUT_NOT_FOUND, error_msg)
        else:
            if valid_extensions and splitext(input_file_path)[-1] not in valid_extensions:
                error_msg = (f"{name} Input file {input_file_path} does not have an expected "
                             f"extension ({valid_extensions}).")

                logger.critical(name, ErrorCode.INVALID_INPUT, error_msg)


def validate_algorithm_parameters_config(name, algorithm_parameters_schema_file_path,
                                         algorithm_parameters_runconfig, logger):
    """
    The DSWx-S1 and DISP-S1 interface SAS uses two runconfig files; one for the main SAS,
    and another for algorithm parameters.  This allows for independent modification
    of algorithm parameters within its own runconfig file.

    This method performs validation of the 'algorithm parameters' runconfig file
    against its associated schema file. The SAS section of the main runconfig
    defines the location within the container of the 'algorithm parameters' runconfig
    file, under ['dynamic_ancillary_file_group']['algorithm_parameters'].

    The schema file for the 'algorithm parameters' runconfig file is referenced under
    ['PrimaryExecutable']['AlgorithmParametersSchemaPath'] in the PGE section of the runconfig file.
    For compatibility with the other PGE 'AlgorithmParametersSchemaPath' is optional.

    """
    #  If it was decided not to provide a path to the schema file, validation is impossible.
    if algorithm_parameters_schema_file_path is None:
        error_msg = "No algorithm_parameters_schema_path provided in runconfig file."
        logger.info(name, ErrorCode.NO_ALGO_PARAM_SCHEMA_PATH, error_msg)
        return
    elif isfile(algorithm_parameters_schema_file_path):
        # Load the 'algorithm parameters' schema
        algorithm_parameters_schema = yamale.make_schema(algorithm_parameters_schema_file_path)
    else:
        raise RuntimeError(
            f'Schema error: Could not validate algorithm_parameters schema file.  '
            f'File: ({algorithm_parameters_schema_file_path}) not found.'
        )

    if isfile(algorithm_parameters_runconfig):
        # Load the 'algorithm parameters' runconfig file
        algorithm_parameters_config_data = yamale.make_data(algorithm_parameters_runconfig)
    else:
        raise RuntimeError(
            f'Can not validate algorithm_parameters config file.  '
            f'File: {algorithm_parameters_runconfig} not found.'
        )

    # Validate the algorithm parameter Runconfig against its schema file
    yamale.validate(algorithm_parameters_schema, algorithm_parameters_config_data, strict=True)
