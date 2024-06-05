#!/usr/bin/env python3

"""
==============
dswx_ni_pge.py
==============
Module defining the implementation for the Dynamic Surface Water Extent (DSWX)
from NISAR (NI) PGE.

"""

import re
from os.path import join

from opera.pge.base.base_pge import PgeExecutor
from opera.pge.dswx_s1.dswx_s1_pge import DSWxS1PostProcessorMixin, DSWxS1PreProcessorMixin
from opera.util.error_codes import ErrorCode
from opera.util.time import get_time_for_filename


class DSWxNIPreProcessorMixin(DSWxS1PreProcessorMixin):
    """
    Mixin class responsible for handling all pre-processing steps for the DSWX-NI
    PGE. The pre-processing phase is defined as all steps necessary prior
    to SAS execution.

    This particular pre-processor inherits its functionality from the DSWx-S1
    pre-processor class, as both PGE's share a similar interface.

    """

    _pre_mixin_name = "DSWxNIPreProcessorMixin"
    _valid_input_extensions = (".h5",)

    def run_preprocessor(self, **kwargs):
        """
        Executes the pre-processing steps for DSWx-NI PGE initialization.
        The DSWxNIPreProcessorMixin version of this class performs all actions
        of the DSWxS1PreProcessorMixin class. Parameterization of the validation
        functions is handled via specialized class attributes (i.e. _valid_input_extensions)

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the pre-processor
        """
        super().run_preprocessor(**kwargs)


class DSWxNIPostProcessorMixin(DSWxS1PostProcessorMixin):
    """
    Mixin class responsible for handling all post-processing steps for the DSWx-NI
    PGE. The post-processing phase is defined as all steps required after SAS
    execution has completed, prior to handover of output products to PCM.
    In addition to the base functionality inherited from PostProcessorMixin, this
    mixin adds an output validation step inherited from DSWxS1PostProcessorMixin
    to ensure that the output file(s) defined by the RunConfig exist and are
    valid.
    """

    _post_mixin_name = "DSWxNIPostProcessorMixin"
    _cached_core_filename = None

    def _validate_output_product_filenames(self):
        """
        Test method to verify the regular expression used to
        validate the output product file names assigned by the SAS
        This method will validate that the filename has the acceptable name
        through a regular expression.  If the pattern does not match
        """
        validated_product_filenames = []
        pattern = re.compile(
            r'(?P<project>OPERA)_(?P<level>L3)_(?P<product_type>DSWx)-(?P<source>NI)_(?P<tile_id>T[^\W_]{5})_'
            r'(?P<acquisition_ts>\d{8}T\d{6}Z)_(?P<creation_ts>\d{8}T\d{6}Z)_(?P<sensor>LSAR)_(?P<spacing>30)_'
            r'(?P<product_version>v\d+[.]\d+)(_(?P<band_index>B\d{2})_'
            r'(?P<band_name>WTR|BWTR|CONF|DIAG)|_BROWSE)?[.](?P<ext>tif|tiff|png)$')

        for output_file in self.runconfig.get_output_product_filenames():
            if pattern.match(output_file.split('/')[-1]):
                validated_product_filenames.append(output_file)
            else:
                error_msg = (f"Output file {output_file} does not match the output predict "
                             f"naming convention.")
                self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

    def _ancillary_filename(self):
        """
        Helper method to derive the core component of the file names for the
        ancillary products associated to a PGE job (catalog metadata, log file,
        etc...).

        The core file name component for DSWx-NI ancillary products consists of:

        <PROJECT>_<LEVEL>_<PGE NAME>_<PROD TIMETAG>_<SENSOR>_<SPACING>_<PRODUCT VERSION>

        Since these files are not specific to any particular tile processed for
        a DSWx-NI job, fields such as tile ID and acquisition time are omitted from
        this file pattern.

        Also note that this does not include a file extension, which should be
        added to the return value of this method by any callers to distinguish
        the different formats of ancillary outputs produced by this PGE.

        Returns
        -------
        ancillary_filename : str
            The file name component to assign to ancillary products created by this PGE.

        """
        # Metadata fields we need for ancillary file name should be equivalent
        # across all tiles, so just take the first set of cached metadata as
        # a representative
        sensor = 'LSAR'  # fixed for NISAR-based products
        pixel_spacing = "30"  # fixed for tile-based products

        # TODO - for now, use the PGE production time, but ideally this should
        #        eventually match the production time assigned by the SAS, which
        #        should be present in the product metadata
        production_time = get_time_for_filename(self.production_datetime)

        if not production_time.endswith('Z'):
            production_time = f'{production_time}Z'

        product_version = str(self.runconfig.product_version)

        if not product_version.startswith('v'):
            product_version = f'v{product_version}'

        ancillary_filename = (
            f"{self.PROJECT}_{self.LEVEL}_{self.NAME}_{production_time}_"
            f"{sensor}_{pixel_spacing}_{product_version}"
        )

        return ancillary_filename

    def _log_filename(self):
        """
        Returns the file name to use for the PGE/SAS log file produced by the DSWx-NI PGE.

        The log file name for the DSWx-NI PGE consists of:

            <Ancillary filename>.log

        Where <Ancillary filename> is returned by DSWxNIPostProcessorMixin._ancillary_filename()

        Returns
        -------
        log_filename : str
            The file name to assign to the PGE/SAS log created by this PGE.

        """
        return self._ancillary_filename() + ".log"

    def _stage_output_files(self):
        """
        This is not a complete module. It has been reduced so that the .log file
        will be saved to disk.

        Ensures that all output products produced by both the SAS and this PGE
        are staged to the output location defined by the RunConfig. This includes
        reassignment of file names to meet the file-naming conventions required
        by the PGE.

        In addition to staging of the output products created by the SAS, this
        function is also responsible for ensuring the catalog metadata, ISO
        metadata, and combined PGE/SAS log are also written to the expected
        output product location with the appropriate file names.

        """
        # Write the catalog metadata to disk with the appropriate filename
        catalog_metadata = self._create_catalog_metadata()

        if not catalog_metadata.validate(catalog_metadata.get_schema_file_path()):
            msg = f"Failed to create valid catalog metadata, reason(s):\n {catalog_metadata.get_error_msg()}"
            self.logger.critical(self.name, ErrorCode.INVALID_CATALOG_METADATA, msg)

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

    def run_postprocessor(self, **kwargs):
        """
        Executes the post-processing steps for the DSWx-NI PGE.
        The DSWxNIPostProcessorMixin version of this method performs the same
        steps as the base PostProcessorMixin, but inserts a step to perform
        output product validation (inherited from DSWxS1PostProcessorMixin) prior
        to staging and renaming of the output files (partially developed).

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the post-processor
        """
        print(f'Running postprocessor for {self._post_mixin_name}')

        self._run_sas_qa_executable()

        self._validate_output()
        # TODO - stage_output_files()  is only partially implemented
        self._stage_output_files()


class DSWxNIExecutor(DSWxNIPreProcessorMixin, DSWxNIPostProcessorMixin, PgeExecutor):
    """
    Main class for execution of the DSWx-NI PGE, including the SAS layer.
    This class essentially rolls up the DSWx-specific pre- and post-processor
    functionality, while inheriting all other functionality for setup and execution
    of the SAS from the base PgeExecutor class.
    """

    NAME = "DSWx-NI"
    """Short name for the DSWx-NI PGE"""

    LEVEL = "L3"
    """Processing Level for DSWx-NI Products"""

    PGE_VERSION = "4.0.0-er.1.0"
    """Version of the PGE (overrides default from base_pge)"""

    SAS_VERSION = "0.1"
    """Version of the SAS wrapped by this PGE, should be updated as needed"""

    def __init__(self, pge_name, runconfig_path, **kwargs):
        super().__init__(pge_name, runconfig_path, **kwargs)

        self.rename_by_pattern_map = {}
