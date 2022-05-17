#!/usr/bin/env python3

"""
===========
base_pge.py
===========

Module defining the Base PGE interfaces from which all other PGEs are derived.

"""

import os
from datetime import datetime
from functools import lru_cache
from os.path import abspath, basename, exists, join, splitext

from yamale import YamaleError

import yaml

import opera
from opera.util.error_codes import ErrorCode
from opera.util.logger import PgeLogger
from opera.util.logger import default_log_file_name
from opera.util.metfile import MetFile
from opera.util.run_utils import create_qa_command_line
from opera.util.run_utils import create_sas_command_line
from opera.util.run_utils import get_checksum
from opera.util.run_utils import get_extension
from opera.util.run_utils import time_and_execute
from opera.util.time import get_catalog_metadata_datetime_str
from opera.util.time import get_time_for_filename

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

        # Relocate the output destination for the log file now that we
        # can access output_product_path from the parsed RunConfig
        self.logger.move(join(self.runconfig.output_product_path, default_log_file_name()))

        self.logger.info(self.name, ErrorCode.LOG_FILE_INIT_COMPLETE,
                         'Log file configuration complete')

    def run_preprocessor(self, **kwargs):  # pylint: disable=unused-argument
        """
        Executes the pre-processing steps for PGE initialization.

        Inheritors of this Mixin may override this function to tailor the
        order of pre-processing steps.

        Parameters
        ----------
        **kwargs : dict
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

    def _run_sas_qa_executable(self):
        """
        Executes an optional Quality Assurance (QA) application which may be bundled
        with a SAS delivery. QA execution is controlled by settings within the
        provided RunConfig.

        If enabled, execution time for the QA application is collected and logged by
        this method.

        """
        if self.runconfig.qa_enabled:
            qa_program_path = self.runconfig.qa_program_path
            qa_program_options = self.runconfig.qa_program_options

            try:
                command_line = create_qa_command_line(qa_program_path, qa_program_options)
            except OSError as err:
                self.logger.critical(self.name, ErrorCode.QA_SAS_PROGRAM_FAILED,
                                     f'Failed to create QA command line, reason: {str(err)}')

            self.qa_logger.debug(self.name, ErrorCode.SAS_QA_COMMAND_LINE,
                                 f'QA EXE command line: {" ".join(command_line)}')

            self.qa_logger.info(self.name, ErrorCode.QA_SAS_PROGRAM_STARTING,
                                'Starting SAS QA executable')

            elapsed_time = time_and_execute(
                command_line, self.qa_logger, self.runconfig.execute_via_shell
            )

            self.qa_logger.info(self.name, ErrorCode.QA_SAS_PROGRAM_COMPLETED,
                                'SAS QA executable complete')

            self.qa_logger.log_one_metric(self.name, 'sas.qa.elapsed_seconds', elapsed_time)
        else:
            self.logger.info(self.name, ErrorCode.QA_SAS_PROGRAM_DISABLED,
                             'SAS QA is disabled, skipping')

    def _checksum_output_products(self):
        """
        Generates a dictionary mapping output product file names to the
        corresponding MD5 checksum digest of the file's contents.

        The output products to generate checksums for is determined by scanning
        the output product location specified by the RunConfig. Any files
        within the directory that have the expected file extensions for output
        products are then picked up for checksum generation.

        Returns
        -------
        checksums : dict
            Mapping of output product file names to MD5 checksums of said
            products.

        """
        output_products = self.runconfig.get_output_product_filenames()

        # Filter out any files that are not renamed by the PGE
        output_products = filter(
            lambda product: get_extension(product) in self.rename_by_extension_map,
            output_products
        )

        # Generate checksums on the filtered product list
        checksums = {
            basename(output_product): get_checksum(output_product)
            for output_product in output_products
        }

        return checksums

    @lru_cache
    def _create_catalog_metadata(self):
        """
        Returns the catalog metadata as a MetFile instance. Once generated, the
        catalog metadata is cached for the life of the PGE instance.
        """
        catalog_metadata = {
            'PGE_Name': self.runconfig.pge_name,
            'PGE_Version': opera.__version__,
            'SAS_Version': self.SAS_VERSION,
            'Input_Files': self.runconfig.get_input_filenames(),
            'Ancillary_Files': self.runconfig.get_ancillary_filenames(),
            'Production_DateTime': get_catalog_metadata_datetime_str(self.production_datetime),
            'Output_Product_Checksums': self._checksum_output_products()
        }

        return MetFile(catalog_metadata)

    def _create_iso_metadata(self):  # pylint: disable=no-self-use
        """
        Creates the ISO metadata utilized by the DAAC's for indexing output
        products submitted by OPERA. Inheritors of PostProcessorMixin must
        provide their own implementations, as ISO metadata is not applicable
        to the base PGE.

        """
        # Base PGE does not produce ISO metadata.
        return None

    def _finalize_log(self, logger):
        """
        Finalizes the provided logger such that the execution summary is logged before
        the log file is closed. This should typically be one of the last functions
        invoked by a post-processor, since the log file will be unavailable for
        writing after this function is called.

        Parameters
        ----------
        logger : PgeLogger
            The PgeLogger instance to finalize.

        """
        logger.info(self.name, ErrorCode.CLOSING_LOG_FILE,
                    f"Closing log file {logger.get_file_name()}")
        logger.close_log_stream()

    def _core_filename(self, inter_filename=None):  # pylint: disable=unused-argument
        """
        Returns the core file name component for products produced by the
        Base PGE. This function should typically be overridden by inheritors
        of PostProcessorMixin to accomplish the specific file-naming conventions
        required by the PGE.

        The core file name component of the Base PGE consists of:

            <PROJECT>_<LEVEL>_<PGE NAME>_<TIMETAG>_<PRODUCT_COUNTER>

        Callers of this function are responsible for assignment of any other
        product-specific fields, such as the file extension.

        Parameters
        ----------
        inter_filename : str, optional
            The intermediate filename of the output product to generate the
            core filename for. This parameter may be used to inspect the file
            in order to derive any necessary components of the returned filename.
            For the base PGE, this parameter is unused and may be omitted.

        Returns
        -------
        core_filename : str
            The core file name component to assign to products created by this PGE.

        """
        time_tag = get_time_for_filename(self.production_datetime)

        return f"{self.PROJECT}_{self.LEVEL}_{self.NAME}_" \
               f"{time_tag}_{str(self.runconfig.product_counter).zfill(3)}"

    def _geotiff_filename(self, inter_filename):
        """
        Returns the file name to use for GeoTIFF's produced by the Base PGE.

        The GeoTIFF filename for the Base PGE consists of:

            <Core filename>_<inter_filename>.tif

        Where <Core filename> is returned by PostProcessorMixin._core_filename()

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the output GeoTIFF to generate
            a filename for. This parameter may be used to inspect the file
            in order to derive any necessary components of the returned filename.

        Returns
        -------
        geotiff_filename : str
            The file name to assign to GeoTIFF product(s) created by this PGE.

        """
        base_filename = splitext(basename(inter_filename))[0]
        return self._core_filename() + f"_{base_filename}.tif"

    def _catalog_metadata_filename(self):
        """
        Returns the file name to use for Catalog Metadata produced by the Base PGE.

        The Catalog Metadata file name for the Base PGE consists of:

            <Core filename>.catalog.json

        Where <Core filename> is returned by PostProcessorMixin._core_filename()

        Returns
        -------
        catalog_metadata_filename : str
            The file name to assign to the Catalog Metadata product created by this PGE.

        """
        return self._core_filename() + ".catalog.json"

    def _iso_metadata_filename(self):
        """
        Returns the file name to use for ISO Metadata produced by the Base PGE.

        The ISO Metadata file name for the Base PGE consists of:

            <Core filename>.iso.xml

        Where <Core filename> is returned by PostProcessorMixin._core_filename()

        Returns
        -------
        iso_metadata_filename : str
            The file name to assign to the ISO Metadata product created by this PGE.

        """
        return self._core_filename() + ".iso.xml"

    def _log_filename(self):
        """
        Returns the file name to use for the PGE/SAS log file produced by the Base PGE.

        The log file name for the Base PGE consists of:

            <Core filename>.log

        Where <Core filename> is returned by PostProcessorMixin._core_filename()

        Returns
        -------
        log_filename : str
            The file name to assign to the PGE/SAS log created by this PGE.

        """
        return self._core_filename() + ".log"

    def _qa_log_filename(self):
        """
        Returns the file name to use for the Quality Assurance application log
        file produced by the Base PGE.

        The log file name for the Base PGE consists of:

            <Core filename>.qa.log

        Where <Core filename> is returned by PostProcessorMixin._core_filename()

        Returns
        -------
        log_filename : str
            The file name to assign to the QA log created by this PGE.

        """
        return self._core_filename() + ".qa.log"

    def _assign_filename(self, input_filepath, output_dir):
        """
        Assigns the appropriate file name which meets the file-naming conventions
        for the PGE to the provided input file on disk.

        The file name to assign is determined based on the file extension of
        the provided input file. If no file name assignment function is configured
        for a given extension, the file name assignment is skipped.

        Parameters
        ----------
        input_filepath : str
            Absolute path to the file on disk to be renamed by this function.
        output_dir : str
            The output directory destination for the renamed file.

        """
        file_extension = splitext(input_filepath)[-1]
        # Lookup the specific rename function configured for the current file extension
        try:
            rename_function = self.rename_by_extension_map[file_extension]
        except KeyError:
            msg = f'No rename function configured for file "{basename(input_filepath)}", skipping assignment'
            self.logger.warning(self.name, ErrorCode.NO_RENAME_FUNCTION_FOR_EXTENSION, msg)
            return

        # Generate the final file name to assign
        final_filename = rename_function(input_filepath)

        final_filepath = os.path.join(output_dir, final_filename)

        self.logger.info(self.name, ErrorCode.MOVING_LOG_FILE,
                         f"Renaming output file {input_filepath} to {final_filepath}")

        try:
            os.rename(input_filepath, final_filepath)
        except OSError as err:
            msg = f"Failed to rename output file {basename(input_filepath)}, reason: {str(err)}"
            self.logger.critical(self.name, ErrorCode.FILE_MOVE_FAILED, msg)

    def _stage_output_files(self):
        """
        Ensures that all output products produced by both the SAS and this PGE
        are staged to the output location defined by the RunConfig. This includes
        reassignment of file names to meet the file-naming conventions required
        by the PGE.

        In addition to staging of the output products created by the SAS, this
        function is also responsible for ensuring the catalog metadata, ISO
        metadata, and combined PGE/SAS log are also written to the expected
        output product location with the appropriate file names.

        """
        # Gather the list of output files produced by the SAS
        output_products = self.runconfig.get_output_product_filenames()

        # For each output file name, assign the final file name matching the
        # expected conventions
        for output_product in output_products:
            self._assign_filename(output_product, self.runconfig.output_product_path)

        # Write the catalog metadata to disk with the appropriate filename
        catalog_metadata = self._create_catalog_metadata()

        if not catalog_metadata.validate(catalog_metadata.get_schema_file_path()):
            msg = f"Failed to create valid catalog metadata, reason(s):\n {catalog_metadata.get_error_msg()}"
            self.logger.critical(self.name, ErrorCode.INVALID_CATALOG_METADATA, msg)

        cat_meta_filename = self._catalog_metadata_filename()
        cat_meta_filepath = join(self.runconfig.output_product_path, cat_meta_filename)

        self.logger.info(self.name, ErrorCode.CREATING_CATALOG_METADATA,
                         f"Writing Catalog Metadata to {cat_meta_filepath}")

        try:
            catalog_metadata.write(cat_meta_filepath)
        except OSError as err:
            msg = f"Failed to write catalog metadata file {cat_meta_filepath}, reason: {str(err)}"
            self.logger.critical(self.name, ErrorCode.CATALOG_METADATA_CREATION_FAILED, msg)

        # Generate the ISO metadata for use with product submission to DAAC(s)
        iso_metadata = self._create_iso_metadata()

        iso_meta_filename = self._iso_metadata_filename()
        iso_meta_filepath = join(self.runconfig.output_product_path, iso_meta_filename)

        if iso_metadata:
            self.logger.info(self.name, ErrorCode.RENDERING_ISO_METADATA,
                             f"Writing ISO Metadata to {iso_meta_filepath}")
            with open(iso_meta_filepath, 'w', encoding='utf-8') as outfile:
                outfile.write(iso_metadata)

        # Write the QA application log to disk with the appropriate filename,
        # if necessary
        if self.runconfig.qa_enabled:
            qa_log_filename = self._qa_log_filename()
            qa_log_filepath = join(self.runconfig.output_product_path, qa_log_filename)
            self.qa_logger.move(qa_log_filepath)

            try:
                self._finalize_log(self.qa_logger)
            except OSError as err:
                msg = f"Failed to write QA log file to {qa_log_filepath}, reason: {str(err)}"
                self.logger.critical(self.name, ErrorCode.LOG_FILE_CREATION_FAILED, msg)

        # Lastly, write the combined PGE/SAS log to disk with the appropriate filename
        log_filename = self._log_filename()
        log_filepath = join(self.runconfig.output_product_path, log_filename)
        self.logger.move(log_filepath)

        try:
            self._finalize_log(self.logger)
        except OSError as err:
            msg = f"Failed to write log file to {log_filepath}, reason: {str(err)}"

            # Log stream might be closed by this point so raise an Exception instead
            raise RuntimeError(msg)

    def run_postprocessor(self, **kwargs):  # pylint: disable=unused-argument
        """
        Executes the post-processing steps for PGE job completion.

        Inheritors of this Mixin may override this function to tailor the
        order of post-processing steps.

        Parameters
        ----------
        **kwargs : dict
            Any keyword arguments needed by the post-processor

        """
        print(f'Running postprocessor for {self._post_mixin_name}')

        self._run_sas_qa_executable()
        self._stage_output_files()


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

    PROJECT = "OPERA"
    """Name of the project associated to this PGE"""

    NAME = "BasePge"
    """Short name for the Base PGE"""

    LEVEL = "L0"
    """Processing Level for Base PGE Products (dummy value)"""

    SAS_VERSION = "0.1"
    """Version of the SAS wrapped by this PGE (dummy value)"""

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
            Any additional keyword arguments needed by the PGE.
            Supported kwargs include:
                - logger : An existing instance of PgeLogger for this PgeExecutor
                           to use, rather than creating its own.

        """
        self.name = self.NAME
        self.pge_name = pge_name
        self.runconfig_path = runconfig_path
        self.runconfig = None
        self.logger = kwargs.get('logger')
        self.qa_logger = PgeLogger(
            workflow="qa_logger", error_code_base=PgeLogger.QA_LOGGER_CODE_BASE
        )
        self.production_datetime = datetime.now()

        self.rename_by_extension_map = {
            '.tif': self._geotiff_filename,
            '.tiff': self._geotiff_filename
        }

    def _isolate_sas_runconfig(self):
        """
        Isolates the SAS-specific portion of the RunConfig into its own
        YAML file, so it may be fed into the SAS executable without unneeded
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

    def run_sas_executable(self, **kwargs):  # pylint: disable=unused-argument
        """
        Kicks off a SAS executable as defined by the RunConfig provided to
        the PGE.

        Execution time for the SAS is collected and logged by this method.

        Parameters
        ----------
        **kwargs : dict
            Any keyword arguments needed for SAS execution.

        """
        sas_program_path = self.runconfig.sas_program_path
        sas_program_options = self.runconfig.sas_program_options
        sas_runconfig_filepath = self._isolate_sas_runconfig()

        try:
            command_line = create_sas_command_line(
                sas_program_path, sas_runconfig_filepath, sas_program_options
            )
        except OSError as err:
            self.logger.critical(self.name, ErrorCode.SAS_PROGRAM_FAILED,
                                 f'Failed to create SAS command line, reason: {str(err)}')

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
