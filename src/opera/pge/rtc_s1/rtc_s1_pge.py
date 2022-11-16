#!/usr/bin/env python3

"""
=============
rtc_s1_pge.py
=============

Module defining the implementation for the Radiometric Terrain Corrected (RTC)
from Sentinel-1 A/B (S1) PGE.

"""

import os.path
from os import walk
from os.path import basename, getsize
from pathlib import Path

from opera.pge.base.base_pge import PgeExecutor
from opera.pge.base.base_pge import PostProcessorMixin
from opera.pge.base.base_pge import PreProcessorMixin
from opera.util.error_codes import ErrorCode
from opera.util.input_validation import validate_slc_s1_inputs
from opera.util.metadata_utils import get_rtc_s1_product_metadata
from opera.util.render_jinja2 import render_jinja2
from opera.util.time import get_time_for_filename


class RtcS1PreProcessorMixin(PreProcessorMixin):
    """
    Mixin class responsible for handling all pre-processing steps for the RTC-S1
    PGE. The pre-processing phase is defined as all steps necessary prior to
    SAS execution.

    In addition to the base functionality inherited from PreProcessorMixin, this
    mixin adds an input validation step to ensure that input(s) defined by the
    RunConfig exist and are valid.

    """

    _pre_mixin_name = "RtcS1PreProcessorMixin"

    def run_preprocessor(self, **kwargs):
        """
        Executes the pre-processing steps for RTC-S1 PGE initialization.

        The RtcS1PreProcessorMixin version of this class performs all actions of
        the base PreProcessorMixin class, and adds an input validation step for
        the inputs defined within the RunConfig.

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the pre-processor

        """
        super().run_preprocessor(**kwargs)

        validate_slc_s1_inputs(self.runconfig, self.logger, self.name)


class RtcS1PostProcessorMixin(PostProcessorMixin):
    """
    Mixin class responsible for handling all post-processing steps for the RTC-S1
    PGE. The post-processing phase is defined as all steps required after SAS
    execution has completed, prior to handover of output products to PCM.

    In addition to the base functionality inherited from PostProcessorMixin, this
    mixin adds an output validation step to ensure that the output file(s) defined
    by the RunConfig exist and are valid.

    """

    _post_mixin_name = "RtcS1PostProcessorMixin"
    _cached_core_filename = None

    def _validate_output(self):
        """
        Evaluates the output file(s) generated from SAS execution to ensure
        the existence of a directory for each burst containing a single output
        file.  Verify each output file exists, is named with the proper extension,
        and is non-zero in size.

        """
        out_dir_walk_dict = {}

        output_dir = self.runconfig.output_product_path

        # from 'output_dir' make a dictionary of {sub_dir_name: [file1, file2,...]}
        for path, dirs, files in walk(output_dir):
            if not dirs:  # Ignore files in 'output_dir'
                out_dir_walk_dict[basename(path)] = files

        output_format = self.runconfig.sas_config['runconfig']['groups']['product_path_group']['output_format']
        if output_format == 'NETCDF':
            expected_ext = ['nc']
        elif output_format == 'GTiff' or output_format == 'COG':
            expected_ext = ['tiff', 'tif']

        # Verify: files in subdirectories, file length, and proper extension.
        for dir_name_key, file_names in out_dir_walk_dict.items():
            if len(file_names) == 0:
                error_msg = f"Empty SAS output directory: {'/'.join((output_dir, dir_name_key))}"

                self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

            for file_name in file_names:
                if not getsize('/'.join((output_dir, dir_name_key, file_name))):
                    error_msg = f"SAS output file {file_name} exists, but is empty"

                    self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

                if file_name.split('.')[-1] not in expected_ext:
                    error_msg = f"SAS output file {file_name} extension error:  expected {[i for i in expected_ext]}"

                    self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

    def _core_filename(self, inter_filename=None):
        """
        Returns the core file name component for products produced by the
        RTC-S1 PGE.

        The core file name component for RTC-S1 products consists of:

        <PROJECT>_<LEVEL>_<PGE NAME>_<SOURCE>_{burst_id}_{acquisition_time}_
        {production_time}_<SENSOR>_<SPACING>_<PRODUCT VERSION>

        Where {burst_id}, {acquisition_time} and {production_time} are literal
        format-string placeholders and are NOT filled in by this method.
        Callers are responsible for assignment of these fields product-specific
        fields via a format() call.

        Notes
        -----
        On first call to this function, the returned core filename is cached
        for subsequent calls. This allows the core filename to be easily reused
        across product types without needing to provide inter_filename for
        each subsequent call.

        Parameters
        ----------
        inter_filename : str, optional
            The intermediate filename of the output product to generate the
            core filename for. This parameter may be used to inspect the file
            in order to derive any necessary components of the returned filename.
            Once the core filename is cached upon first call to this function,
            this parameter may be omitted.

        Returns
        -------
        core_filename : str
            The core file name component to assign to products created by this PGE.

        """
        # Check if the core filename has already been generated and cached,
        # and return it if so
        if self._cached_core_filename is not None:
            return self._cached_core_filename

        product_version = str(self.runconfig.product_version)

        if not product_version.startswith('v'):
            product_version = f'v{product_version}'

        # Assign the core file to the cached class attribute
        self._cached_core_filename = (
            f"{self.PROJECT}_{self.LEVEL}_{self.NAME}-{self.SOURCE}_"
            "{burst_id}_{acquisition_time}Z_{production_time}Z_"  # To be filled in per-product
            f"{self.SENSOR}_{self.SPACING}_{product_version}"
        )

        return self._cached_core_filename

    def _rtc_filename(self, inter_filename):
        """
        Returns the file name to use for RTC products produced by this PGE.

        The filename for the RTC PGE consists of:

            <Core filename>.<ext>

        Where <Core filename> is returned by RtcS1PostProcessorMixin._core_filename()
        and <ext> is the file extension carried over from inter_filename

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the output product to generate
            a filename for. This parameter may be used to inspect the file
            in order to derive any necessary components of the returned filename.

        Returns
        -------
        rtc_filename : str
            The file name to assign to RTC product(s) created by this PGE.

        """
        core_filename = self._core_filename(inter_filename)

        # Each RTC product is stored in a directory named for the corresponding burst ID
        burst_id = Path(os.path.dirname(inter_filename)).parts[-1]

        ext = os.path.splitext(inter_filename)[-1]

        # TODO: this will come from product metadata eventually
        production_time = get_time_for_filename(self.production_datetime)

        # TODO: this needs to be parsed from input SAFE file
        acquisition_time = production_time

        rtc_filename = core_filename.format(
            burst_id=burst_id,
            acquisition_time=acquisition_time,
            production_time=production_time
        ) + ext

        return rtc_filename

    def _ancillary_filename(self):
        """
        Helper method to derive the core component of the file names for
        the ancillary products associated to a PGE job (catalog metadata, log
        file, etc...).

        The core file name component for RTC-S1 ancillary products consists of:

        <PROJECT>_<LEVEL>_<PGE NAME>_<SOURCE>_<PRODUCTION TIME>_<SENSOR>_<SPACING>_<PRODUCT VERSION>

        Since these files are not specific to any particular burst processed
        for an RTC job, fields such as burst ID and acquisition time are omitted
        from this file pattern.

        Returns
        -------
        ancillary_filename : str
            The file name component to assign to ancillary products created by this PGE.

        """
        production_time = get_time_for_filename(self.production_datetime)
        product_version = str(self.runconfig.product_version)

        if not product_version.startswith('v'):
            product_version = f'v{product_version}'

        ancillary_filename = (
            f"{self.PROJECT}_{self.LEVEL}_{self.NAME}_{self.SOURCE}_"
            f"{production_time}Z_{self.SENSOR}_{self.SPACING}_{product_version}"
        )

        return ancillary_filename

    def _catalog_metadata_filename(self):
        """
        Returns the file name to use for Catalog Metadata produced by the RTC-S1 PGE.

        The Catalog Metadata file name for the RTC-S1 PGE consists of:

            <Ancillary filename>.catalog.json

        Where <Ancillary filename> is returned by RtcS1PostProcessorMixin._ancillary_filename()

        Returns
        -------
        catalog_metadata_filename : str
            The file name to assign to the Catalog Metadata product created by this PGE.

        """
        return self._ancillary_filename() + ".catalog.json"

    def _iso_metadata_filename(self):
        """
        Returns the file name to use for ISO Metadata produced by the RTC-S1 PGE.

        The ISO Metadata file name for the RTC-S1 PGE consists of:

            <Ancillary filename>.iso.xml

        Where <Ancillary filename> is returned by RtcS1PostProcessorMixin._ancillary_filename()

        Returns
        -------
        iso_metadata_filename : str
            The file name to assign to the ISO Metadata product created by this PGE.

        """
        return self._ancillary_filename() + ".iso.xml"

    def _log_filename(self):
        """
        Returns the file name to use for the PGE/SAS log file produced by the RTC-S1 PGE.

        The log file name for the RTC-S1 PGE consists of:

            <Ancillary filename>.log

        Where <Ancillary filename> is returned by RtcS1PostProcessorMixin._ancillary_filename()

        Returns
        -------
        log_filename : str
            The file name to assign to the PGE/SAS log created by this PGE.

        """
        return self._ancillary_filename() + ".log"

    def _qa_log_filename(self):
        """
        Returns the file name to use for the Quality Assurance application log
        file produced by the RTC-S1 PGE.

        The log file name for the RTC-S1 PGE consists of:

            <Ancillary filename>.qa.log

        Where <Ancillary filename> is returned by RtcS1PostProcessorMixin._ancillary_filename()

        Returns
        -------
        log_filename : str
            The file name to assign to the QA log created by this PGE.

        """
        return self._ancillary_filename() + ".qa.log"

    def _collect_rtc_product_metadata(self):
        """
        Gathers the available metadata from a representative RTC product created by
        the RTC-S1 SAS. This metadata is then formatted for use with filling in
        the ISO metadata template for the RTC-S1 PGE.

        Returns
        -------
        output_product_metadata : dict
            Dictionary containing RTC-S1 output product metadata, formatted for
            use with the ISO metadata Jinja2 template.

        """
        output_products = self.runconfig.get_output_product_filenames()

        # TODO: will need to support GeoTIFF/COG for later versions of SAS
        nc_product = None

        for output_product in output_products:
            if output_product.endswith('.nc'):
                nc_product = output_product
                break
        else:
            msg = (f"Could not find a NetCDF format RTC product to extract "
                   f"metadata from within {self.runconfig.output_product_path}")
            self.logger.critical(self.name, ErrorCode.ISO_METADATA_RENDER_FAILED, msg)

        output_product_metadata = get_rtc_s1_product_metadata(nc_product)

        # Fill in some additional fields expected within the ISO
        output_product_metadata['frequencyA']['frequencyAWidth'] = len(output_product_metadata['frequencyA']['xCoordinates'])
        output_product_metadata['frequencyA']['frequencyALength'] = len(output_product_metadata['frequencyA']['yCoordinates'])

        # TODO: the following fields seems to be missing in the interface delivery products,
        #       but are documented, remove these kludges once they are actually available
        if 'burst_polygon' not in output_product_metadata:
            output_product_metadata['burst_polygon'] = "POLYGON ((399015 3859970, 398975 3860000, ..., 399015 3859970))"

        if 'azimuthBandwidth' not in output_product_metadata['frequencyA']:
            output_product_metadata['frequencyA']['azimuthBandwidth'] = 12345678.9

        if 'noiseCorrectionFlag' not in output_product_metadata['frequencyA']:
            output_product_metadata['frequencyA']['noiseCorrectionFlag'] = False

        if 'productVersion' not in output_product_metadata['identification']:
            output_product_metadata['identification']['productVersion'] = '1.0'

        if 'plannedDatatakeId' not in output_product_metadata['identification']:
            output_product_metadata['identification']['plannedDatatakeId'] = ['datatake1', 'datatake2']

        if 'plannedObservationId' not in output_product_metadata['identification']:
            output_product_metadata['identification']['plannedObservationId'] = ['obs1', 'obs2']
        # TODO: end kludges

        return output_product_metadata

    def _create_custom_metadata(self):
        """
        Creates the "custom data" dictionary used with the ISO metadata rendering.

        Custom data contains all metadata information needed for the ISO template
        that is not found within any of the other metadata sources (such as the
        RunConfig, output product(s), or catalog metadata).

        Returns
        -------
        custom_metadata : dict
            Dictionary containing the custom metadata as expected by the ISO
            metadata Jinja2 template.

        """
        custom_metadata = {
            'ISO_OPERA_FilePackageName': self._ancillary_filename(),
            'ISO_OPERA_ProducerGranuleId': self._ancillary_filename(),
            'MetadataProviderAction': "creation",
            'GranuleFilename': self._ancillary_filename(),
            'ISO_OPERA_ProjectKeywords': ['OPERA', 'JPL', 'RTC', 'Radiometric', 'Terrain', 'Corrected'],
            'ISO_OPERA_PlatformKeywords': ['S1'],
            'ISO_OPERA_InstrumentKeywords': ['Sentinel 1 A/B']
        }

        return custom_metadata

    def _create_iso_metadata(self):
        """
        Creates a rendered version of the ISO metadata template for RTC-S1
        output products using metadata from the following locations:

            * RunConfig (in dictionary form)
            * Output products (dictionaries extracted from NetCDF format)
            * Catalog metadata
            * "Custom" metadata (all metadata not found anywhere else)

        Returns
        -------
        rendered_template : str
            The ISO metadata template for RTC-S1 filled in with values from the
            sourced metadata dictionaries.

        """
        runconfig_dict = self.runconfig.asdict()

        product_output_dict = self._collect_rtc_product_metadata()

        catalog_metadata_dict = self._create_catalog_metadata().asdict()

        custom_data_dict = self._create_custom_metadata()

        iso_metadata = {
            'run_config': runconfig_dict,
            'product_output': product_output_dict,
            'catalog_metadata': catalog_metadata_dict,
            'custom_data': custom_data_dict
        }

        iso_template_path = os.path.abspath(self.runconfig.iso_template_path)

        if not os.path.exists(iso_template_path):
            msg = f"Could not load ISO template {iso_template_path}, file does not exist"
            self.logger.critical(self.name, ErrorCode.ISO_METADATA_TEMPLATE_NOT_FOUND, msg)

        rendered_template = render_jinja2(iso_template_path, iso_metadata, self.logger)

        return rendered_template

    def run_postprocessor(self, **kwargs):
        """
        Executes the post-processing steps for the RTC-S1 PGE.

        The RtcS1PostProcessorMixin version of this method performs the same
        steps as the base PostProcessorMixin, but inserts a step to perform
        output product validation prior to staging and renaming of the output
        files.

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the post-processo

        """
        print(f'Running postprocessor for {self._post_mixin_name}')

        self._run_sas_qa_executable()
        self._validate_output()
        self._stage_output_files()


class RtcS1Executor(RtcS1PreProcessorMixin, RtcS1PostProcessorMixin, PgeExecutor):
    """
    Main class for execution of the RTC-S1 PGE, including the SAS layer.

    This class essentially rolls up the RTC-specific pre- and post-processor
    functionality, while inheriting all other functionality for setup and execution
    of the SAS from the base PgeExecutor class.

    """

    NAME = "RTC"
    """Short name for the RTC-S1 PGE"""

    LEVEL = "L2"
    """Processing Level for RTC-S1 Products"""

    SAS_VERSION = "0.1"  # Interface release https://github.com/opera-adt/RTC/releases/tag/v0.1
    """Version of the SAS wrapped by this PGE, should be updated as needed"""

    # TODO: these are hardcoded for now, need to determine if they will come
    #       from product metadata
    SOURCE = "S1"
    SENSOR = "S1A"
    SPACING = "30"

    def __init__(self, pge_name, runconfig_path, **kwargs):
        super().__init__(pge_name, runconfig_path, **kwargs)

        self.rename_by_pattern_map = {
            "*.nc": self._rtc_filename
        }
