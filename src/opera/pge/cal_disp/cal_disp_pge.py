#!/usr/bin/env python3

"""
===============
cal_disp_pge.py
===============
Module defining the implementation of the Calibration for Surface Displacement from Sentinel-1 and NISAR (CAL-DISP) PGE.
"""

import re
from os import listdir
from os.path import basename, join, getsize, splitext

from opera.pge.base.base_pge import PgeExecutor, PostProcessorMixin, PreProcessorMixin
from opera.util.error_codes import ErrorCode
from opera.util.input_validation import validate_algorithm_parameters_config, validate_cal_inputs


class CalDispPreProcessorMixin(PreProcessorMixin):
    """
    Mixin class responsible for handling all pre-processing steps for the CAL-DISP
    PGE. The pre-processing phase is defined as all steps necessary prior
    to SAS execution.

    In addition to the base functionality inherited from PreProcessorMixin, this
    mixin adds an input validation step to ensure that input(s) defined by the
    RunConfig exist and are valid.
    """

    _pre_mixin_name = "CalDispPreProcessorMixin"
    _valid_input_extensions = (".nc",)

    def run_preprocessor(self, **kwargs):
        """
        Executes the pre-processing steps for CAL-DISP PGE initialization.
        The CalDispPreProcessorMixin version of this class performs all actions
        of the PreProcessorMixin class. Parameterization of the validation
        functions is handled via specialized class attributes (i.e. _valid_input_extensions)

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the pre-processor
        """
        super().run_preprocessor(**kwargs)

        validate_cal_inputs(self.runconfig, self.logger, self.name)
        validate_algorithm_parameters_config(self.name,
                                             self.runconfig.algorithm_parameters_schema_path,
                                             self.runconfig.algorithm_parameters_file_config_path,
                                             self.logger)


class CalDispPostProcessorMixin(PostProcessorMixin):
    """
    Mixin class responsible for handling all post-processing steps for the CAL-DISP
    PGE. The post-processing phase is defined as all steps required after SAS
    execution has completed, prior to handover of output products to PCM.

    This particular pre-processor is currently a stub implementation, inheriting from the base pre-processor mixin
    and adding nothing at this time. New functionalities will be added as new versions of the CAL-DISP SAS are released.
    """

    _post_mixin_name = "CalDispPostProcessorMixin"
    _product_metadata_cache = {}
    _product_filename_cache = {}

    _expected_extensions = ('.nc', '.png')

    def _validate_outputs(self):
        output_product_files = self.runconfig.get_output_product_filenames()

        # Confirm one and only one of each expected output type
        for filename_ext in self._expected_extensions:
            gen = (f for f in output_product_files if splitext(f)[1] == filename_ext)
            try:
                output_filepath = next(gen)
            except StopIteration:
                error_msg = f"Could not locate {filename_ext} file."
                self.logger.critical(self.name, ErrorCode.OUTPUT_NOT_FOUND, error_msg)

            # Check for second file, if found raise error
            try:
                next(gen)
                error_msg = f"Found incorrect number of {filename_ext} files."
                self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)
            except StopIteration:
                pass

            output_filename = basename(output_filepath)

            # Check file size
            file_size = getsize(output_filepath)
            if not file_size > 0:
                error_msg = (f"Output file {output_filename} size is {file_size}. "
                             "Size must be greater than 0.")
                self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

            # Check filename matches expected pattern
            match = self._granule_filename_re.match(output_filename)
            if not bool(match):
                error_msg = f'Invalid product filename {output_filename}'
                self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)
            else:
                # Cache the core filename for later use
                self._cached_core_filename = match.group(0)

    def run_postprocessor(self, **kwargs):
        """
        Executes the post-processing steps for the CAL-DISP PGE.
        The CalDispPostProcessorMixin version of this method currently
        validates the output product files and performs the same
        steps as the base PostProcessorMixin.

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the post-processor
        """
        self._validate_outputs()

        super().run_postprocessor(**kwargs)


class CalDispExecutor(CalDispPreProcessorMixin, CalDispPostProcessorMixin, PgeExecutor):
    """
    Main class for execution of the CAL-DISP PGE, including the SAS layer.
    This class essentially rolls up the CAL-DISP-specific pre- and post-processor
    functionality, while inheriting all other functionality for setup and execution
    of the SAS from the base PgeExecutor class.
    """

    _granule_filename_re = re.compile(r"(?P<id>(?P<project>OPERA)_(?P<level>L4)_(?P<product_type>CAL-DISP)-"
                                      r"(?P<platform>S1|NI)_(?P<mode>IW|20|40|77|05)_(?P<frame_id>F\d{5})_"
                                      r"(?P<pol>[HV]{2})_(?P<reference_ts>\d{8}T\d{6}Z)_(?P<secondary_ts>\d{8}T\d{6}Z)_"
                                      r"(?P<product_version>v\d[.]\d)_(?P<creation_ts>\d{8}T\d{6}Z)[.](?P<ext>nc|png))")

    NAME = "CAL-DISP"
    """Short name for the CAL-DISP PGE"""

    LEVEL = "L4"
    """Processing Level for CAL-DISP Products"""

    SAS_VERSION = "0.1"  # Interface release https://github.com/opera-adt/cal-disp/releases/tag/v0.1
    """Version of the SAS wrapped by this PGE, should be updated as needed"""

    def __init__(self, pge_name, runconfig_path, **kwargs):
        super().__init__(pge_name, runconfig_path, **kwargs)

        self.rename_by_pattern_map = {}
