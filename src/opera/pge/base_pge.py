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
base_pge.py
===========

Module defining the Base PGE interfaces from which all other PGEs are derived.

"""

import os
from os.path import abspath, basename, exists, join, splitext

from yamale import YamaleError

import yaml

from opera.util.error_codes import ErrorCode
from opera.util.logger import PgeLogger
from opera.util.run_utils import create_sas_command_line
from opera.util.run_utils import time_and_execute

from .runconfig import RunConfig


class PreProcessorMixin:
    """
    Mixin class which is responsible for handling all pre-processing steps for
    the PGE. The pre-processing phase is defined as all steps necessary prior
    to SAS execution.

    This class is intended for use as a Mixin for use with the PgeExecutor
    class and its inheritors, and as such, this class assumes access to the
    instance attributes defined by PgeExecutor.

    Inheritors of PreProcessorMixin may provide overloaded implementations
    for any of the exiting pre-processing steps, and even provide additional
    steps as necessary.

    """

    _pre_mixin_name = "PreProcessorMixin"

    def __init__(self):
        self.logger = None
        self.name = None
        self.runconfig_path = None

    def _initialize_logger(self):
        """
        Creates the logger object used by the PGE.

        The logger is created using a default name, as the proper filename
        cannot be determined until the RunConfig is parsed and validated.

        """
        if not self.logger:
            self.logger = PgeLogger()
            self.logger.info(self.name, ErrorCode.LOG_FILE_CREATED,
                             f'New Log file initialized to {self.logger.get_file_name()}')
        else:
            self.logger.info(self.name, ErrorCode.LOG_FILE_CREATED,
                             f'Log file passed from pge_main: {self.logger.get_file_name()}')

    def _load_runconfig(self):
        """
        Loads the RunConfig file provided to the PGE into an in-memory
        representation.
        """
        self.logger.info(self.name, ErrorCode.LOADING_RUN_CONFIG_FILE,
                         f'Loading RunConfig file {self.runconfig_path}')

        self.runconfig = RunConfig(self.runconfig_path)

    def _validate_runconfig(self):
        """
        Validates the parsed RunConfig against the appropriate schema(s).

        Raises
        ------
        RuntimeError
            If the RunConfig fails validation.

        """
        self.logger.info(self.name, ErrorCode.VALIDATING_RUN_CONFIG_FILE,
                         f'Validating RunConfig file {self.runconfig.filename}')

        try:
            self.runconfig.validate()
        except YamaleError as error:
            error_msg = (f'Validation of RunConfig file {self.runconfig.filename} '
                         f'failed, reason(s): \n{str(error)}')

            self.logger.critical(
                self.name, ErrorCode.RUN_CONFIG_VALIDATION_FAILED, error_msg
            )

    def _setup_directories(self):
        """
        Creates the output/scratch directory locations referenced by the
        RunConfig if they don't exist already.
        """
        output_product_path = abspath(self.runconfig.output_product_path)
        scratch_path = abspath(self.runconfig.scratch_path)

        try:
            if not exists(output_product_path):
                self.logger.info(self.name, ErrorCode.CREATING_WORKING_DIRECTORY,
                                 f'Creating output product directory {output_product_path}')
                os.makedirs(output_product_path, exist_ok=True)

            # TODO: add a cleanup function on the post-processor to remove scratch dir?
            if not exists(scratch_path):
                self.logger.info(self.name, ErrorCode.CREATING_WORKING_DIRECTORY,
                                 f'Creating scratch directory {scratch_path}')
                os.makedirs(scratch_path, exist_ok=True)

            self.logger.info(self.name, ErrorCode.DIRECTORY_SETUP_COMPLETE,
                             'Directory setup complete')
        except OSError as error:
            error_msg = (f'Could not create one or more working directories. '
                         f'reason: \n{str(error)}')

            self.logger.critical(
                self.name, ErrorCode.DIRECTORY_CREATION_FAILED, error_msg
            )

    def _configure_logger(self):
        """
        Configures the logger used by the PGE using information from the
        parsed and validated RunConfig.
        """
        self.logger.error_code_base = self.runconfig.error_code_base

        self.logger.workflow = f'{self.runconfig.pge_name}::{basename(__file__)}'

        # TODO: perform the log rename step here (if possible) once file-name convention is defined
        output_product_path = abspath(self.runconfig.output_product_path)
        log_file_destination = join(output_product_path, self.logger.get_file_name())

        self.logger.info(self.name, ErrorCode.MOVING_LOG_FILE,
                         f'Moving log file to {log_file_destination}')
        self.logger.move(log_file_destination)

        self.logger.info(self.name, ErrorCode.LOG_FILE_INIT_COMPLETE,
                         'Log file configuration complete')

    def run_preprocessor(self, **kwargs):
        """
        Executes the pre-processing steps for PGE initialization.

        Inheritors of this Mixin may override this function to tailor the
        order of pre-processing steps.

        Parameters
        ----------
        kwargs : dict
            Any keyword arguments needed by the pre-processor

        """
        # TODO: better way to handle trace statements before logger has been created?
        print(f'Running preprocessor for {self._pre_mixin_name}')

        self._initialize_logger()
        self._load_runconfig()
        self._validate_runconfig()
        self._setup_directories()
        self._configure_logger()


class PostProcessorMixin:
    """
    Mixin class which is responsible for handling all post-processing steps for
    the PGE. The post-processing phase is defined as all steps necessary after
    SAS execution has completed.

    This class is intended for use as a Mixin for use with the PgeExecutor
    class and its inheritors, and as such, this class assumes access to the
    instance attributes defined by PgeExecutor.

    Inheritors of PostProcessorMixin may provide overloaded implementations
    for any of the exiting pre-processing steps, and even provide additional
    steps as necessary.

    """

    _post_mixin_name = "PostProcessorMixin"

    def __init__(self):
        self.name = None
        self.logger = None

    def _run_sas_qa_executable(self):
        # TODO
        pass

    def _create_catalog_metadata(self):
        # TODO
        pass

    def _create_iso_metadata(self):
        # TODO
        pass

    def _stage_output_files(self):
        # TODO
        pass

    def _finalize_log(self):
        """
        Finalizes the logger such that the execution summary is logged before
        the log file is closed. This should typically be one of the last functions
        invoked by a post-processor, since the log file will be unavailable for
        writing after this function is called.

        """
        self.logger.info(self.name, ErrorCode.CLOSING_LOG_FILE,
                         f"Closing log file {self.logger.get_file_name()}")
        self.logger.close_log_stream()

    def run_postprocessor(self, **kwargs):
        """
        Executes the post-processing steps for PGE job completion.

        Inheritors of this Mixin may override this function to tailor the
        order of post-processing steps.

        Parameters
        ----------
        kwargs : dict
            Any keyword arguments needed by the post-processor

        """
        print(f'Running postprocessor for {self._post_mixin_name}')

        self._run_sas_qa_executable()
        self._create_catalog_metadata()
        self._create_iso_metadata()
        self._stage_output_files()
        self._finalize_log()


class PgeExecutor(PreProcessorMixin, PostProcessorMixin):
    """
    Main class for execution of a PGE, including the SAS layer.

    The PgeExecutor class is primarily responsible for defining the interface
    for PGE execution and managing the actual execution of the SAS executable
    within a subprocess. PGE's also define pre- and post-processing stages,
    which are invoked by PgeExecutor, but whose implementations are defined
    by use of Mixin classes.

    The use of Mixin classes allows for flexibility of PGE design, where
    inheritors of PgeExecutor can compose a custom PGE by providing overloaded
    implementations of the Mixin classes to tailor the behavior of the pre-
    and post-processing phases, where necessary, while still inheriting any
    common functionality from this class.

    """

    NAME = "PgeExecutor"

    def __init__(self, pge_name, runconfig_path, **kwargs):
        """
        Creates a new instance of PgeExecutor

        Parameters
        ----------
        pge_name : str
            Name to associate with this PGE.
        runconfig_path : str
            Path to the RunConfig to be used with this PGE.
        kwargs : dict
            Any additional keyword arguments needed by the PGE. Currently
            supported kwargs include:
                - logger : An existing instance of PgeLogger for this PgeExecutor
                           to use, rather than creating its own.

        """
        self.name = self.NAME
        self.pge_name = pge_name
        self.runconfig_path = runconfig_path
        self.runconfig = None
        self.logger = kwargs.get('logger')

    def _isolate_sas_runconfig(self):
        """
        Isolates the SAS-specific portion of the RunConfig into its own
        YAML file so it may be fed into the SAS executable without unneeded
        PGE configuration settings.

        """
        sas_config = self.runconfig.sas_config

        pge_runconfig_filename = basename(self.runconfig.filename)
        pge_runconfig_fileparts = splitext(pge_runconfig_filename)

        sas_runconfig_filename = f'{pge_runconfig_fileparts[0]}_sas{pge_runconfig_fileparts[1]}'
        sas_runconfig_filepath = join(self.runconfig.scratch_path, sas_runconfig_filename)

        try:
            with open(sas_runconfig_filepath, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(sas_config, outfile, sort_keys=False)
        except OSError as err:
            self.logger.critical(self.name, ErrorCode.SAS_CONFIG_CREATION_FAILED,
                                 f'Failed to create SAS config file {sas_runconfig_filepath}, '
                                 f'reason: {str(err)}')

        self.logger.info(self.name, ErrorCode.CREATED_SAS_CONFIG,
                         f'SAS RunConfig created at {sas_runconfig_filepath}')

        return sas_runconfig_filepath

    def run_sas_executable(self, **kwargs):
        """
        Kicks off a SAS executable as defined by the RunConfig provided to
        the PGE.

        Execution time for the SAS is collected and logged by this method.

        Parameters
        ----------
        kwargs : dict
            Any keyword arguments needed for SAS execution.

        """
        sas_program_path = self.runconfig.sas_program_path
        sas_program_options = self.runconfig.sas_program_options
        sas_runconfig_filepath = self._isolate_sas_runconfig()

        command_line = create_sas_command_line(
            sas_program_path, sas_runconfig_filepath, sas_program_options
        )

        self.logger.debug(self.name, ErrorCode.SAS_EXE_COMMAND_LINE,
                          f'SAS EXE command line: {" ".join(command_line)}')

        self.logger.info(self.name, ErrorCode.SAS_PROGRAM_STARTING,
                         'Starting SAS executable')

        elapsed_time = time_and_execute(
            command_line, self.logger, self.runconfig.execute_via_shell
        )

        self.logger.info(self.name, ErrorCode.SAS_PROGRAM_COMPLETED,
                         'SAS executable complete')

        self.logger.log_one_metric(self.name, 'sas.elapsed_seconds', elapsed_time)

    def run(self, **kwargs):
        """
        Main entry point for PGE execution.

        The pre-processor stage is run to initialize the PGE, followed by
        SAS execution, then completed with the post-processing steps to complete
        the job.

        """
        self.run_preprocessor(**kwargs)

        print(f'Starting SAS execution for {self.__class__.__name__}')
        self.run_sas_executable(**kwargs)

        self.run_postprocessor(**kwargs)
