#!/usr/bin/env python3

"""
==============
dswx_s1_pge.py
==============
Module defining the implementation for the Dynamic Surface Water Extent (DSWx)
from Sentinel-1 A/B (S1) PGE.
"""

from os.path import abspath, exists, isfile, splitext

import yamale

import opera.util.input_validation as input_validation
from opera.pge.base.base_pge import PgeExecutor
from opera.pge.base.base_pge import PostProcessorMixin
from opera.pge.base.base_pge import PreProcessorMixin
from opera.util.error_codes import ErrorCode


class DSWxS1PreProcessorMixin(PreProcessorMixin):
    """
    Mixin class responsible for handling all pre-processing steps for the DSWx-S1
    PGE. The pre-processing phase is defined as all steps necessary prior
    to SAS execution.

    In addition to the base functionality inherited from PreProcessorMixin, this
    mixin adds an input validation step to ensure that input(s) defined by the
    RunConfig exist and are valid.

    """

    _pre_mixin_name = "DSWxS1PreProcessorMixin"

    def _validate_algorithm_parameters_config(self):
        """
        The DSWx-S1 interface SAS uses two runconfig files; one for the main SAS,
        and another for algorithm parameters.  This allows for independent modification
        of algorithm parameters within it's own runconfig file. This method performs validation
        of the 'algorithm parameters' runconfig file against its associated schema file. The SAS
        section of the main runconfig defines the location within the container of the 'algorithm
        parameters' runconfig file, under ['dynamic_ancillary_file_group']['algorithm_parameters'].
        The schema file for the 'algorithm parameters' runconfig file is referenced under
        ['PrimaryExecutable']['AlgorithmParametersSchemaPath'] in the PGE section of the runconfig file.
        For compatibility with the other PGE 'AlgorithmParametersSchemaPath' is optional.

        """
        # Get the path to the optional 'algorithm_parameters_s1.schema.yaml' file
        algorithm_parameters_schema_file_path = self.runconfig.algorithm_parameters_schema_path
        #  If it was decided not to provide a path to the schema file, validation is impossible.
        if algorithm_parameters_schema_file_path is None:
            error_msg = "No algorithm_parameters_schema_path provided in runconfig file."
            self.logger.info(self.name, ErrorCode.NO_ALGO_PARAM_SCHEMA_PATH, error_msg)
            return
        elif isfile(algorithm_parameters_schema_file_path):
            # Load the 'algorithm parameters' schema
            algorithm_parameters_schema = yamale.make_schema(algorithm_parameters_schema_file_path)
        else:
            raise RuntimeError(
                f'Schema error: Could not validate algorithm_parameters schema file.  '
                f'File: ({algorithm_parameters_schema_file_path}) not found.'
            )

        # Get the 'algorithm parameters' runconfig file
        self.algorithm_parameters_runconfig = self.runconfig.algorithm_parameters_config_path
        if isfile(self.algorithm_parameters_runconfig):
            # Load the 'algorithm parameters' runconfig file
            algorithm_parameters_config_data = yamale.make_data(self.algorithm_parameters_runconfig)
        else:
            raise RuntimeError(
                f'Can not validate algorithm_parameters config file.  '
                f'File: {self.algorithm_parameters_runconfig} not found.'
            )

        # Validate the algorithm parameter Runconfig against its schema file
        yamale.validate(algorithm_parameters_schema, algorithm_parameters_config_data, strict=True)

    def _validate_ancillary_inputs(self):
        """
        Evaluates the list of ancillary inputs from the RunConfig to ensure they
        exist and have an expected file extension.

        """
        dynamic_ancillary_file_group_dict = \
            self.runconfig.sas_config['runconfig']['groups']['dynamic_ancillary_file_group']

        for key, value in dynamic_ancillary_file_group_dict.items():
            if key in ('dem_file', ):
                input_validation.check_input(
                    value, self.logger, self.name, valid_extensions=('.tif', '.tiff', '.vrt')
                )
            elif key in ('reference_water_file', 'world_file', 'hand_file'):
                input_validation.check_input(
                    value, self.logger, self.name, valid_extensions=('.tif', '.tiff')
                )
            elif key in ('shoreline_shapefile',):
                input_validation.check_input(
                    value, self.logger, self.name, valid_extensions=('.shp',)
                )

                # Only the .shp file is configured in the runconfig, but we
                # need to ensure the other required files are co-located with it
                for extension in ('.dbf', '.prj', '.shx'):
                    additional_shapefile = splitext(value)[0] + extension

                    if not exists(abspath(additional_shapefile)):
                        error_msg = f"Additional shapefile {additional_shapefile} could not be located"

                        self.logger.critical(self.name, ErrorCode.INVALID_INPUT, error_msg)

            elif key in ('dem_file_description', 'worldcover_file_description',
                         'reference_water_file_description', 'hand_file_description',
                         'shoreline_shapefile_description'):
                # these fields are included in the SAS input paths, but are not
                # actually file paths, so skip them
                continue
            elif key in ('algorithm_parameters',):
                input_validation.check_input(
                    value, self.logger, self.name, valid_extensions=('.yaml', )
                )

    def run_preprocessor(self, **kwargs):
        """
        Executes the pre-processing steps for DSWx-S1 PGE initialization.
        The DswxS1PreProcessorMixin version of this class performs all actions
        of the base PreProcessorMixin class, and adds an input validation step for
        the inputs defined within the RunConfig (TODO).

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the pre-processor

        """
        super().run_preprocessor(**kwargs)

        input_validation.validate_dswx_inputs(self.runconfig, self.logger, self.runconfig.pge_name)
        self._validate_algorithm_parameters_config()
        self._validate_ancillary_inputs()


class DSWxS1PostProcessorMixin(PostProcessorMixin):
    """
    Mixin class responsible for handling all post-processing steps for the DSWx-S1
    PGE. The post-processing phase is defined as all steps required after SAS
    execution has completed, prior to handover of output products to PCM.

    In addition to the base functionality inherited from PostProcessorMixin, this
    mixin adds an output validation step to ensure that the output file(s) defined
    by the RunConfig exist and are valid (TODO).

    """

    _post_mixin_name = "DSWxS1PostProcessorMixin"
    _cached_core_filename = None

    def run_postprocessor(self, **kwargs):
        """
        Executes the post-processing steps for the DSWx-S1 PGE.
        The DSWxS1PostProcessorMixin version of this method performs the same
        steps as the base PostProcessorMixin, but inserts a step to perform
        output product validation prior to staging and renaming of the output
        files (TODO).

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the post-processor

        """
        super().run_postprocessor(**kwargs)


class DSWxS1Executor(DSWxS1PreProcessorMixin, DSWxS1PostProcessorMixin, PgeExecutor):
    """
    Main class for execution of the DSWx-S1 PGE, including the SAS layer.
    This class essentially rolls up the DSWx-specific pre- and post-processor
    functionality, while inheriting all other functionality for setup and execution
    of the SAS from the base PgeExecutor class.

    """

    NAME = "DSWx"
    """Short name for the DSWx-S1 PGE"""

    LEVEL = "L3"
    """Processing Level for DSWx-S1 Products"""

    SAS_VERSION = "0.1"
    """Version of the SAS wrapped by this PGE, should be updated as needed"""

    def __init__(self, pge_name, runconfig_path, **kwargs):
        super().__init__(pge_name, runconfig_path, **kwargs)

        self.rename_by_pattern_map = {}
