#!/usr/bin/env python3

"""
===================
input_validation.py
===================

Common code used by some PGEs for input validation.

"""
import glob
import re
from os.path import abspath, exists, getsize, isdir, isfile, join, splitext

import yamale

from opera.util.error_codes import ErrorCode


def check_input(input_object, logger, name, valid_extensions=None,
                check_zero_size=False):
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
    # The input object path must be explicitly tested for 'None' before
    # os.path.exists() executes.
    if input_object is None:
        error_msg = f"TypeError: {input_object} is NoneType."
        logger.critical(name, ErrorCode.INPUT_NOT_FOUND, error_msg)

    if not exists(input_object):
        error_msg = f"Could not locate specified input {input_object}."
        logger.critical(name, ErrorCode.INPUT_NOT_FOUND, error_msg)

    if valid_extensions:
        ext = splitext(input_object)[-1]

        if ext not in valid_extensions:
            error_msg = (f"Input file {input_object} does not have an expected "
                         f"file extension.")
            logger.critical(name, ErrorCode.INVALID_INPUT, error_msg)

    if check_zero_size is True:
        file_size = getsize(input_object)
        if not file_size > 0:
            error_msg = (f"Input file {input_object} size is {file_size}. "
                         "Size must be greater than 0.")
            logger.critical(name, ErrorCode.INVALID_INPUT, error_msg)


def check_input_list(list_of_input_objects, logger, name, valid_extensions=None,
                     check_zero_size=False):
    """Call check_input for a list of input objects."""
    for input_object in list_of_input_objects:
        check_input(input_object, logger, name,
                    valid_extensions=valid_extensions,
                    check_zero_size=check_zero_size)


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
            for index in range(len(value)):
                check_input(value[index], logger, name, valid_extensions=('.zip',))
        elif key == 'orbit_file_path':
            for index in range(len(value)):
                check_input(value[index], logger, name, valid_extensions=('.EOF',))
        elif key == 'dem_file':
            check_input(value, logger, name, valid_extensions=('.tif', '.tiff', '.vrt'))
        elif key == 'tec_file':
            check_input(value, logger, name)
        elif key == 'weather_model_file':
            # This key could show up since it is in the schema, but it should
            # never be present in R2 production, so just ignore
            continue
        elif key in ('burst_id', 'dem_description', 'dem_file_description',
                     'source_data_access'):
            # these fields are included in the SAS input paths, but are not
            # actually file paths, so skip them
            continue
        elif key == 'burst_database_file':
            check_input(value, logger, name, valid_extensions=('.sqlite', '.sqlite3',))
        else:
            error_msg = f"Unexpected input: {key}: {value}"
            logger.critical(name, ErrorCode.INVALID_INPUT, error_msg)


def get_burst_id_set(input_file_group: list, logger, name) -> set:
    """
    Compiles a set of burst_ids from a list of files defined in the runconfig file.
    Each file in the list should have a burst_id in the file name.

    Parameters
    ----------
    input_file_group : list
        List of files containing a burst_id
    logger : PgeLogger
        Logger passed by the calling PGE
    name : str
        PGE name

    Returns
    -------
    burst_ids : set
        The unique set of burst IDs parsed from the list of input file names.

    Raises
    ------
    RuntimeError
        If a burst_id is improperly formatted.

    """
    burst_ids = set()
    for index in input_file_group:
        reg_ex = r'[t|T]\w{3}[-|_]\d{6}[-|_][I|i][W|w][1|2|3]'
        match = re.search(reg_ex, index)
        if match:
            burst_id = re.findall(reg_ex, index)[0]

            # canonicalize the burst ID before adding to set
            burst_id = burst_id.replace("_", "-").upper()

            burst_ids.add(burst_id)
        else:
            msg = f'Input file present without properly formatted burst_id: {index}'
            logger.critical(name, ErrorCode.INVALID_INPUT, msg)

    return burst_ids


def check_disp_s1_ancillary_burst_ids(cslc_input_burst_ids: set,
                                      ancillary_file_list: list, logger, name):
    # pylint: disable=C0103
    """
    Verify burst_ids from the ancillary input files:
        'amplitude_dispersion_files',
        'amplitude_mean_files',
        'geometry_files'

    Verify that each file has a unique burst id in the file name, and that the
    burst idea is in the set of DISP_S1 cslc input burst ids.

    Parameters
    ----------
    cslc_input_burst_ids : set
        DISP_S1 input file burst_ids
    ancillary_file_list : list
        List from the runconfig file of the desired set of ancillary files to check
    logger : PgeLogger
        Logger passed by the calling PGE
    name : str
        PGE name

    Raises
    ------
    RuntimeError
        If there are ancillary files of the same type with the same burst_id.
        If the set of ancillary file burst_ids do not match the set of cslc
        input file burst_ids.

    """
    nl, tab, dtab = '\n', '\t', '\t\t'   # used to format log output in fstrings.
    ancillary_burst_ids: set = get_burst_id_set(ancillary_file_list, logger, name)

    # Test none of the ancillary inputs have the same burst ID
    if len(ancillary_burst_ids) != len(ancillary_file_list):
        msg = (f"Duplicate burst ID's in ancillary file list. "
               f"Length of file list {ancillary_file_list}, "
               f"Length of file set {ancillary_burst_ids}")
        logger.critical(name, ErrorCode.INVALID_INPUT, msg)

    # Verify that the sets of ancillary input burst ID's match the set of CSLC
    # input burst ID's
    if ancillary_burst_ids != cslc_input_burst_ids:
        msg = (f"{nl}{tab}Set of input CSLC burst IDs do not match the set of "
               f"ancillary burst IDs: {nl}"
               f"{dtab}In cslc set, but not in ancillary set: "
               f"{cslc_input_burst_ids.difference(ancillary_burst_ids)}{nl}"
               f"{dtab}In ancillary set, but not in cslc set: "
               f"{ancillary_burst_ids.difference(cslc_input_burst_ids)}")
        logger.critical(name, ErrorCode.INVALID_INPUT, msg)


def get_cslc_input_burst_id_set(cslc_input_file_list, logger, name):
    # pylint: disable=C0103,R1710
    """
    Compile the set of burst ids from the cslc input files
    There may be uncompressed files only, or a mixture of uncompressed
    and compressed files.  If mixed the uncompressed set of burst ids
    must match the set of compressed burst ids.

    Parameters
    ----------
    cslc_input_file_list : list
        List of all cslc input files pulled from the runconfig file
    logger : PgeLogger
        Logger passed by the calling PGE
    name : str
        PGE name

    Returns
    -------
    burst id set : set
        Will be either 'single_file_burst_id_set' or 'compressed_file_burst_id_set'
        depending upon the list of burst ids passed to the function.

    Raises
    ------
    RuntimeError
        If the compressed burst_ids set does not match the uncompressed burst_id set.

    """
    nl, tab, dtab = '\n', '\t', '\t\t'  # used to format log output in fstrings.
    # Filter and separate into 2 list: files with 'compressed' in the name, and
    # files without 'compressed' in the name.
    compressed_input_file_list = list(filter((lambda filename: 'compressed' in filename),
                                             cslc_input_file_list))
    single_input_file_list = list(set(cslc_input_file_list) - set(compressed_input_file_list))

    compressed_file_burst_id_set: set = get_burst_id_set(compressed_input_file_list, logger, name)
    single_file_burst_id_set: set = get_burst_id_set(single_input_file_list, logger, name)

    # Case 1:  uncompressed files only in cslc inputs
    if len(compressed_file_burst_id_set) == 0:
        return single_file_burst_id_set

    # Case 2: uncompressed files and compressed files in cslc inputs with non-matching burst ids
    if single_file_burst_id_set != compressed_file_burst_id_set:
        msg = (f"{nl}{tab}Set of input CSLC 'compressed' burst IDs do not match"
               f" the set of 'uncompressed' burst IDs: {nl}"
               f"{dtab}In 'compressed' set, but not in 'uncompressed' set: "
               f"{compressed_file_burst_id_set.difference(single_file_burst_id_set)} {nl}"
               f"{dtab}In 'uncompressed' set, but not in 'compressed' set:"
               f" {single_file_burst_id_set.difference(compressed_file_burst_id_set)}")
        logger.critical(name, ErrorCode.INVALID_INPUT, msg)
    # Case 3: uncompressed file and compressed files with matching burst id sets
    else:
        return compressed_file_burst_id_set


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
    input_file_group = runconfig.sas_config['input_file_group']
    dyn_anc_file_group = runconfig.sas_config['dynamic_ancillary_file_group']
    static_anc_file_group = runconfig.sas_config['static_ancillary_file_group']

    check_input_list(input_file_group['cslc_file_list'], logger, name,
                     valid_extensions=('.h5',), check_zero_size=True)

    cslc_burst_id_set = get_cslc_input_burst_id_set(
        runconfig.sas_config['input_file_group']['cslc_file_list'],
        logger, name
    )

    if ('static_layers_files' in dyn_anc_file_group and
            len(dyn_anc_file_group['static_layers_files']) > 0):
        check_input_list(dyn_anc_file_group['static_layers_files'], logger, name,
                         valid_extensions=('.h5',), check_zero_size=True)
        check_disp_s1_ancillary_burst_ids(cslc_burst_id_set,
                                          dyn_anc_file_group['static_layers_files'],
                                          logger,
                                          name)

    if 'mask_file' in dyn_anc_file_group and dyn_anc_file_group['mask_file']:
        check_input(dyn_anc_file_group['mask_file'], logger, name,
                    valid_extensions=('.tif', '.tiff', '.vrt', '.flg'), check_zero_size=True)

    if 'dem_file' in dyn_anc_file_group and dyn_anc_file_group['dem_file']:
        check_input(dyn_anc_file_group['dem_file'], logger, name,
                    valid_extensions=('.tif', '.tiff', '.vrt'), check_zero_size=True)

    if ('ionosphere_files' in dyn_anc_file_group
            and len(dyn_anc_file_group['ionosphere_files']) > 0):
        check_input_list(dyn_anc_file_group['ionosphere_files'], logger, name,
                         check_zero_size=True)

    if ('troposphere_files' in dyn_anc_file_group and
            len(dyn_anc_file_group['troposphere_files']) > 0):
        check_input_list(dyn_anc_file_group['troposphere_files'], logger, name,
                         valid_extensions=('.nc', '.h5', '.grb'), check_zero_size=True)

    if ('frame_to_burst_json' in static_anc_file_group and
            static_anc_file_group['frame_to_burst_json'] is not None):
        check_input(static_anc_file_group['frame_to_burst_json'], logger, name,
                    valid_extensions=('.json',), check_zero_size=True)

    if ('reference_date_database_json' in static_anc_file_group and
            static_anc_file_group['reference_date_database_json'] is not None):
        check_input(static_anc_file_group['reference_date_database_json'], logger,
                    name, valid_extensions=('.json',), check_zero_size=True)


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
        elif valid_extensions and splitext(input_file_path)[-1] not in valid_extensions:
            error_msg = (f"{name} Input file {input_file_path} does not have an expected "
                         f"extension ({valid_extensions}).")

            logger.critical(name, ErrorCode.INVALID_INPUT, error_msg)


def validate_algorithm_parameters_config(name, algorithm_parameters_schema_file_path,
                                         algorithm_parameters_runconfig, logger):
    """
    The DSWx-S1 and DISP-S1 interface SAS uses two runconfig files; one for the
    main SAS, and another for algorithm parameters.  This allows for independent
    modification of algorithm parameters within its own runconfig file.

    This method performs validation of the 'algorithm parameters' runconfig file
    against its associated schema file. The SAS section of the main runconfig
    defines the location within the container of the 'algorithm parameters'
    runconfig file, under ['dynamic_ancillary_file_group']['algorithm_parameters'].

    The schema file for the 'algorithm parameters' runconfig file is referenced
    under ['PrimaryExecutable']['AlgorithmParametersSchemaPath'] in the PGE
    section of the runconfig file.

    For compatibility with the other PGE 'AlgorithmParametersSchemaPath' is optional.

    """
    #  If it was decided not to provide a path to the schema file, validation is impossible.
    if algorithm_parameters_schema_file_path is None:
        error_msg = "No algorithm_parameters_schema_path provided in runconfig file."
        logger.info(name, ErrorCode.NO_ALGO_PARAM_SCHEMA_PATH, error_msg)
        return

    if isfile(algorithm_parameters_schema_file_path):
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
