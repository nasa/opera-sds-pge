#!/usr/bin/env python3
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
===========
dswx_pge.py
===========

Module defining the implementation for the Dynamic Surface Water Extent (DSWx) PGE.

"""

import glob
import os.path
from os.path import abspath, exists, isdir, join

from opera.util.error_codes import ErrorCode

from .base_pge import PgeExecutor
from .base_pge import PostProcessorMixin
from .base_pge import PreProcessorMixin


class DSWxPreProcessorMixin(PreProcessorMixin):
    """
    Mixin class responsible for handling all pre-processing steps for the
    DSWx PGE. The pre-processing phase is defined as all steps necessary prior
    to SAS execution.

    In addition to the base functionality inherited from PreProcessorMixin, this
    mixin adds a input validation step to ensure that the input(s) defined by
    the RunConfig exist and are valid.

    """

    _pre_mixin_name = "DSWxPreProcessorMixin"

    def _validate_inputs(self):
        """
        Evaluates the list of inputs from the RunConfig to ensure they are valid.
        For directories, this means checking for directory existence, and that
        at least one .tif file resides within the directory. For files,
        each file is checked for existence and that it has a .tif extension.
        """
        for input_file in self.runconfig.input_files:
            input_file_path = abspath(input_file)

            if not exists(input_file_path):
                error_msg = f"Could not locate specified input file/directory {input_file_path}"

                self.logger.critical(self.name, ErrorCode.INPUT_NOT_FOUND, error_msg)
            elif isdir(input_file_path):
                list_of_input_tifs = glob.glob(join(input_file_path, '*.tif'))

                if len(list_of_input_tifs) <= 0:
                    error_msg = f"Input directory {input_file_path} does not contain any tif files"

                    self.logger.critical(self.name, ErrorCode.INPUT_NOT_FOUND, error_msg)
            elif not input_file_path.endswith(".tif"):
                error_msg = f"Input file {input_file_path} does not have .tif extension"

                self.logger.critical(self.name, ErrorCode.INVALID_INPUT, error_msg)

    def run_preprocessor(self, **kwargs):
        """
        Executes the pre-processing steps for DSWx PGE initialization.

        The DSWxPreProcessorMixin version of this function performs all actions
        of the base PreProcessorMixin class, and adds the validation check for
        input files/directories.

        Parameters
        ----------
        **kwargs : dict
            Any keyword arguments needed by the pre-processor

        """
        super().run_preprocessor(**kwargs)

        self._validate_inputs()


class DSWxPostProcessorMixin(PostProcessorMixin):
    """
    Mixin class responsible for handling all post-processing steps for the DSWx
    PGE. The post-processing phase is defined as all steps necessary after
    SAS execution has completed.

    In addition to the base functionality inherited from PostProcessorMixin, this
    mixin adds a output validation step to ensure that the output file defined by
    the RunConfig exist and are valid.

    """

    _post_mixin_name = "DSWxPostProcessorMixin"

    def _validate_output(self):
        """
        Evaluates the output file generated from SAS execution to ensure its
        existence, and that the file contains some content (size is greater than
        0).
        """
        output_path = abspath(
            join(self.runconfig.output_product_path, self.runconfig.sas_output_file)
        )

        if not exists(output_path):
            error_msg = f"Expected SAS output file {output_path} does not exist"

            self.logger.critical(self.name, ErrorCode.OUTPUT_NOT_FOUND, error_msg)

        if not os.path.getsize(output_path):
            error_msg = f"SAS output file {output_path} was created but is empty"

            self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

    def run_postprocessor(self, **kwargs):
        """
        Executes the post-processing steps for DSWx PGE job completion.

        The DSWxPostProcessorMixin version of this function performs the same
        steps as the base PostProcessorMixin, but inserts the output file
        validation check prior to staging of the output files.

        Parameters
        ----------
        **kwargs : dict
            Any keyword arguments needed by the post-processor

        """
        print(f'Running postprocessor for {self._post_mixin_name}')

        self._run_sas_qa_executable()
        self._create_catalog_metadata()
        self._create_iso_metadata()
        self._validate_output()
        self._stage_output_files()
        self._finalize_log()


class DSWxExecutor(DSWxPreProcessorMixin, DSWxPostProcessorMixin, PgeExecutor):
    """
    Main class for execution of a DSWx PGE, including the SAS layer.

    This class essentially rolls up the DSWx-tailored pre- and post-processors
    while inheriting all other functionality from the base PgeExecutor class.

    """

    NAME = "DSWx"
