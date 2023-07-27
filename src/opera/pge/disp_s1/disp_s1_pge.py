#!/usr/bin/env python3

"""
==============
disp_s1_pge.py
==============
Module defining the implementation for the Land-Surface Displacement (DISP) product
from Sentinel-1 A/B (S1-A/B) data.
"""

import glob
from os import listdir
from os.path import abspath, basename, exists, getsize, join, splitext

from opera.pge.base.base_pge import PgeExecutor
from opera.pge.base.base_pge import PostProcessorMixin
from opera.pge.base.base_pge import PreProcessorMixin
from opera.util.error_codes import ErrorCode
from opera.util.input_validation import validate_algorithm_parameters_config, validate_disp_inputs


class DispS1PreProcessorMixin(PreProcessorMixin):
    """
    Mixin class responsible for handling all pre-processing steps for the DISP-S1
    PGE. The pre-processing phase is defined as all steps necessary prior
    to SAS execution.

    In addition to the base functionality inherited from PreProcessorMixin, this
    mixin adds an input validation step to ensure that input(s) defined by the
    RunConfig exist and are valid.

    """

    _pre_mixin_name = "DispS1PreProcessorMixin"

    def run_preprocessor(self, **kwargs):
        """
        Executes the pre-processing steps for DISP-S1 PGE initialization.
        The DswxS1PreProcessorMixin version of this class performs all actions
        of the base PreProcessorMixin class, and adds an input validation step for
        the inputs defined within the RunConfig (TODO).

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the pre-processor

        """
        super().run_preprocessor(**kwargs)

        validate_disp_inputs(self.runconfig, self.logger, self.name)

        self.algorithm_parameters_runconfig = self.runconfig.algorithm_parameters_file_config_path
        validate_algorithm_parameters_config(self.name,
                                             self.runconfig.algorithm_parameters_schema_path,
                                             self.runconfig.algorithm_parameters_file_config_path,
                                             self.logger)


class DispS1PostProcessorMixin(PostProcessorMixin):
    """
    Mixin class responsible for handling all post-processing steps for the DISP-S1
    PGE. The post-processing phase is defined as all steps required after SAS
    execution has completed, prior to handover of output products to PCM.

    In addition to the base functionality inherited from PostProcessorMixin, this
    mixin adds an output validation step to ensure that the output file(s) defined
    by the RunConfig exist and are valid.

    """

    _post_mixin_name = "DispS1PostProcessorMixin"
    _cached_core_filename = None

    def _validate_output(self):
        """
        Evaluates the output files generated from SAS execution to ensure:
            - That one expected .nc file exists in the output directory designated
              by the RunConfig and is non-zero in size
            - A .png file corresponding to the expected output .nc product exists
              alongside and is non-zero in size (TODO)
            - If the SAS runconfig has the product_path_group.save_compressed_slc
              flag set to True, validate that a "compressed_slcs" directory
              exists within the designated output directory, and that it is not
              empty
            - For each file within "compressed_slcs", ensure the file is non-zero
              in size
        """
        output_dir = abspath(self.runconfig.output_product_path)

        # Validate .nc product file
        nc_files = glob.glob(join(output_dir, '*.nc'))

        if len(nc_files) != 1:
            if len(nc_files) == 0:
                error_msg = "The SAS did not create an output file with the expected '.nc' extension"
            elif len(nc_files) > 1:
                error_msg = f"The SAS created too many files with the expected '.nc' extension: {nc_files}"

            self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

        nc_file = nc_files[0]
        if not getsize(nc_file):
            error_msg = f"SAS output file {basename(nc_file)} exists, but is empty"

            self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

        # Validate .png file
        nc_file_no_ext, ext = splitext(basename(nc_file))
        png_file = join(output_dir, f'{nc_file_no_ext}.png')
        if not exists(png_file):
            error_msg = f"SAS output file {basename(png_file)} does not exist"

            print(f"TODO: {error_msg}")
            # self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)
        elif not getsize(png_file):
            error_msg = f"SAS output file {basename(png_file)} exists but is empty"

            print(f"TODO: {error_msg}")
            # self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

        save_compressed_slc = self.runconfig.sas_config['product_path_group']['save_compressed_slc']
        if save_compressed_slc:
            # Validate compressed_slcs directory
            comp_dir = join(output_dir, 'compressed_slcs')
            if not exists(comp_dir):
                error_msg = f"SAS output directory '{basename(comp_dir)}' does not exist"

                self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

            comp_dir_list = listdir(comp_dir)
            if len(comp_dir_list) == 0:
                error_msg = f"SAS output directory '{basename(comp_dir)}' exists but is empty"

                self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

            # Validate each file in compressed_slcs directory
            for f in comp_dir_list:
                if not getsize(join(comp_dir, f)):
                    error_msg = f"SAS compressed_slcs file '{basename(f)}' exists but is empty"

                    self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

    def run_postprocessor(self, **kwargs):
        """
        Executes the post-processing steps for the DISP-S1 PGE.
        The DispS1PostProcessorMixin version of this method performs the same
        steps as the base PostProcessorMixin, but inserts a step to perform
        output product validation prior to staging and renaming of the output
        files (TODO).

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the post-processor

        """
        print(f'Running postprocessor for {self._post_mixin_name}')

        self._run_sas_qa_executable()
        self._validate_output()
        self._stage_output_files()


class DispS1Executor(DispS1PreProcessorMixin, DispS1PostProcessorMixin, PgeExecutor):
    """
    Main class for execution of the DISP-S1 PGE, including the SAS layer.
    This class essentially rolls up the DISP-specific pre- and post-processor
    functionality, while inheriting all other functionality for setup and execution
    of the SAS from the base PgeExecutor class.

    """

    NAME = "DISP"
    """Short name for the DISP-S1 PGE"""

    LEVEL = "L3"
    """Processing Level for DISP-S1 Products"""

    SAS_VERSION = "0.1"
    """Version of the SAS wrapped by this PGE, should be updated as needed"""

    def __init__(self, pge_name, runconfig_path, **kwargs):
        super().__init__(pge_name, runconfig_path, **kwargs)

        self.rename_by_pattern_map = {}
