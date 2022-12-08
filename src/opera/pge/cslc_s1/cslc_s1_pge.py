#!/usr/bin/env python3

"""
==============
cslc_s1_pge.py
==============

Module defining the implementation for the Co-registered Single Look Complex (CSLC)
from Sentinel-1 A/B (S1) PGE.

"""

import json
import os.path
import re
from datetime import datetime
from os.path import exists, getsize, splitext

from opera.pge.base.base_pge import PgeExecutor
from opera.pge.base.base_pge import PostProcessorMixin
from opera.pge.base.base_pge import PreProcessorMixin
from opera.util.error_codes import ErrorCode
from opera.util.input_validation import validate_slc_s1_inputs
from opera.util.render_jinja2 import render_jinja2
from opera.util.time import get_time_for_filename


class CslcS1PreProcessorMixin(PreProcessorMixin):
    """
    Mixin class responsible for handling all pre-processing steps for the CSLC-S1
    PGE. The pre-processing phase is defined as all steps necessary prior
    to SAS execution.

    In addition to the base functionality inherited from PreProcessorMixin, this
    mixin adds an input validation step to ensure that input(s) defined by the
    RunConfig exist and are valid.

    """

    _pre_mixin_name = "CslcS1PreProcessorMixin"

    def run_preprocessor(self, **kwargs):
        """
        Executes the pre-processing steps for CSLC-S1 PGE initialization.

        The CslcS1PreProcessorMixin version of this class performs all actions
        of the base PreProcessorMixin class, and adds an input validation step
        for the inputs defined within the RunConfig.

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the pre-processor

        """
        super().run_preprocessor(**kwargs)

        validate_slc_s1_inputs(self.runconfig, self.logger, self.name)


class CslcS1PostProcessorMixin(PostProcessorMixin):
    """
    Mixin class responsible for handling all post-processing steps for the CSLC-S1
    PGE. The post-processing phase is defined as all steps required after SAS
    execution has completed, prior to handover of output products to PCM.

    In addition to the base functionality inherited from PostProcessorMixin, this
    mixin adds an output validation step to ensure that the output file(s) defined
    by the RunConfig exist and are valid.

    """

    _post_mixin_name = "CslcS1PostProcessorMixin"
    _cached_core_filename = None

    def _validate_output(self):
        """
        Evaluates the output file(s) generated from SAS execution to ensure
        existence, also validate that the file(s) contains some content
        (size is greater than 0).
        """
        output_product_path = self.runconfig.output_product_path

        # Get the burst ID of the job
        burst_id = self.runconfig.sas_config['runconfig']['groups']['input_file_group']['burst_id']

        output_products = list(
            filter(
                lambda filename: burst_id in filename,
                self.runconfig.get_output_product_filenames()
            )
        )

        if not output_products:
            error_msg = (f"No SAS output file(s) containing burst ID {burst_id} "
                         f"found within {output_product_path}")
            self.logger.critical(self.name, ErrorCode.OUTPUT_NOT_FOUND, error_msg)

        for output_product in output_products:
            if not getsize(output_product):
                error_msg = f"SAS output file {output_product} was created, but is empty"

                self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

    def _core_filename(self, inter_filename=None):
        """
        Returns the core file name component for products produced by the
        CSLC-S1 PGE.

        The core file name component of the CSLC-S1 PGE consists of:

        <PROJECT>_<LEVEL>_<PGE NAME>

        Callers of this function are responsible for assignment of any other
        product-specific fields, such as the file extension.

        Notes
        -----
        On first call to this function, the returned core filename is cached
        for subsequent calls. This allows the core filename to be easily reused
        across product types without needing to provide inter_filename for each
        subsequent call.

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

        # Assign the core file name to the cached class attribute
        self._cached_core_filename = (
            f"{self.PROJECT}_{self.LEVEL}_{self.NAME}"
        )

        return self._cached_core_filename

    def _cslc_filename(self, inter_filename):
        """
        Returns the file name to use for burst-based CSLC products produced by this PGE.

        The filename for the CSLC-S1 burst products consists of:

            <Core filename>-<SENSOR>_<MODE>_<BURST ID>_<POL>_<ACQ TIMETAG>_<PRODUCT VER>_<PROD TIMETAG>

        Where <Core filename> is returned by CslcS1PostProcessorMixin._core_filename()

        Also note that this does not include a file extension, which should be
        added to the return value of this method by any callers to distinguish
        different file formats that are produced for each burst in an input SLC.

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the output GeoTIFF to generate a
            filename for. This parameter may be used to inspect the file in order
            to derive any necessary components of the returned filename.

        Returns
        -------
        geotiff_filename : str
            The file name to assign to GeoTIFF product(s) created by this PGE.

        """
        core_filename = self._core_filename(inter_filename)

        cslc_metadata = self._collect_cslc_product_metadata()

        sensor = cslc_metadata['platform_id']
        mode = 'IW'  # fixed to Interferometric Wide (IW) for all S1-based CSLC products
        burst_id = cslc_metadata['burst_id'].upper().replace('_', '-')
        pol = cslc_metadata['polarization']
        acquisition_time = get_time_for_filename(
            datetime.strptime(cslc_metadata['sensing_start'], '%Y-%m-%d %H:%M:%S.%f')
        )

        product_version = str(self.runconfig.product_version)

        if not product_version.startswith('v'):
            product_version = f'v{product_version}'

        production_time = get_time_for_filename(self.production_datetime)

        cslc_file_components = (
            f"{core_filename}-{sensor}_{mode}_{burst_id}_{pol}_"
            f"{acquisition_time}Z_{product_version}_{production_time}Z"
        )

        return cslc_file_components

    def _geotiff_filename(self, inter_filename):
        """
        Returns the file name to use for GeoTIFF's produced by the CSLC-S1 PGE.

        The GeoTIFF filename for the CSLC-S1 PGE consists of:

            <CSLC filename>.tiff

        Where <CSLC filename> is returned by CslcS1PostProcessorMixin._cslc_filename()

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the output GeoTIFF to generate a
            filename for. This parameter may be used to inspect the file in order
            to derive any necessary components of the returned filename.

        Returns
        -------
        geotiff_filename : str
            The file name to assign to GeoTIFF product(s) created by this PGE.

        """
        cslc_filename = self._cslc_filename(inter_filename)

        return f"{cslc_filename}.tiff"

    def _json_metadata_filename(self, inter_filename):
        """
        Returns the file name to use for JSON metadata files produced by the
        CSLC-S1 PGE.

        The JSON metadata filename for the CSLC-S1 PGE consists of:

            <CSLC filename>.json

        Where <CSLC filename> is returned by CslcS1PostProcessorMixin._cslc_filename()

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the output JSON metadata to generate a
            filename for. This parameter may be used to inspect the file in order
            to derive any necessary components of the returned filename.

        Returns
        -------
        json_metadata_filename : str
            The file name to assign to JSON metadata product(s) created by this PGE.

        """
        cslc_filename = self._cslc_filename(inter_filename)

        return f"{cslc_filename}.json"

    def _ancillary_filename(self):
        """
        Helper method to derive the core component of the file names for the
        ancillary products associated to a PGE job (catalog metadata, log file,
        etc...).

        The core file name component for CSLC-S1 ancillary products consists of:

        <PROJECT>_<LEVEL>_<PGE NAME>-<SENSOR>_<MODE>_<POL>_<PRODUCT VER>_<PROD TIMETAG>

        Since these files are not specific to any particular burst processed for
        a CSLC job, fields such as burst ID and acquisition time are omitted from
        this file pattern.

        Also note that this does not include a file extension, which should be
        added to the return value of this method by any callers to distinguish
        the different formats of ancillary outputs produced by this PGE.

        Returns
        -------
        ancillary_filename : str
            The file name component to assign to ancillary products created by this PGE.

        """
        cslc_metadata = self._collect_cslc_product_metadata()

        sensor = cslc_metadata['platform_id']
        mode = 'IW'  # fixed for all S1-based CSLC products
        pol = cslc_metadata['polarization']

        product_version = str(self.runconfig.product_version)

        if not product_version.startswith('v'):
            product_version = f'v{product_version}'

        production_time = get_time_for_filename(self.production_datetime)

        ancillary_filename = (
            f"{self.PROJECT}_{self.LEVEL}_{self.NAME}-{sensor}_{mode}_{pol}_"
            f"{product_version}_{production_time}Z"
        )

        return ancillary_filename

    def _catalog_metadata_filename(self):
        """
        Returns the file name to use for Catalog Metadata produced by the CSLC-S1 PGE.

        The Catalog Metadata file name for the CSLC-S1 PGE consists of:

            <Ancillary filename>.catalog.json

        Where <Ancillary filename> is returned by CslcPostProcessorMixin._ancillary_filename()

        Returns
        -------
        catalog_metadata_filename : str
            The file name to assign to the Catalog Metadata product created by this PGE.

        """
        return self._ancillary_filename() + ".catalog.json"

    def _iso_metadata_filename(self):
        """
        Returns the file name to use for ISO Metadata produced by the CSLC-S1 PGE.

        The ISO Metadata file name for the CSLC-S1 PGE consists of:

            <Ancillary filename>.iso.xml

        Where <Ancillary filename> is returned by CslcS1PostProcessorMixin._ancillary_filename()

        Returns
        -------
        iso_metadata_filename : str
            The file name to assign to the ISO Metadata product created by this PGE.

        """
        return self._ancillary_filename() + ".iso.xml"

    def _log_filename(self):
        """
        Returns the file name to use for the PGE/SAS log file produced by the CSLC-S1 PGE.

        The log file name for the CSLC-S1 PGE consists of:

            <Ancillary filename>.log

        Where <Ancillary filename> is returned by CslcS1PostProcessorMixin._ancillary_filename()

        Returns
        -------
        log_filename : str
            The file name to assign to the PGE/SAS log created by this PGE.

        """
        return self._ancillary_filename() + ".log"

    def _qa_log_filename(self):
        """
        Returns the file name to use for the Quality Assurance application log
        file produced by the CSLC-S1 PGE.

        The log file name for the CSLC-S1 PGE consists of:

            <Ancillary filename>.qa.log

        Where <Ancillary filename> is returned by CslcS1PostProcessorMixin._ancillary_filename()

        Returns
        -------
        log_filename : str
            The file name to assign to the QA log created by this PGE.

        """
        return self._ancillary_filename() + ".qa.log"

    def _collect_cslc_product_metadata(self):
        """
        Gathers the available metadata from the JSON metadata product created by
        the CSLC-S1 SAS. This metadata is then formatted for use with filling in
        the ISO metadata template for the CSLC-S1 PGE.

        Returns
        -------
        output_product_metadata : dict
            Dictionary containing CSLC-S1 output product metadata, formatted for
            use with the ISO metadata Jinja2 template.

        """
        # Gather the output products produced by the SAS to locate the JSON file
        # containing the product metadata
        output_products = self.runconfig.get_output_product_filenames()
        json_metadata_product = None

        for output_product in output_products:
            if output_product.endswith('.json') and not output_product.endswith('.catalog.json'):
                json_metadata_product = output_product
                break
        else:
            msg = (f"Could not find the JSON metadata output product within "
                   f"{self.runconfig.output_product_path}")
            self.logger.critical(self.name, ErrorCode.ISO_METADATA_RENDER_FAILED, msg)

        # Read the output product metadata
        with open(json_metadata_product, 'r') as infile:
            output_product_metadata = json.load(infile)

        # Parse the burst center coordinate to conform with gml schema
        # sample: "POINT (441737.4292702299 3877557.760490343)"
        burst_center_str = output_product_metadata['center']
        burst_center_pattern = r"POINT\s*\(\s*(.+)\s*\)"
        result = re.match(burst_center_pattern, burst_center_str)

        if not result:
            msg = f'Failed to parse burst center from string "{burst_center_str}"'
            self.logger.critical(self.name, ErrorCode.ISO_METADATA_RENDER_FAILED, msg)

        output_product_metadata['burst_center'] = result.groups()[0]

        # Parse the burst polygon coordinates to conform with gml
        # sample: "POLYGON ((399015 3859970, 398975 3860000, ..., 399015 3859970))"
        burst_polygon_str = output_product_metadata['border']
        burst_polygon_pattern = r"POLYGON\s*\(\((.+)\)\)"
        result = re.match(burst_polygon_pattern, burst_polygon_str)

        if not result:
            msg = f'Failed to parse burst polygon from string "{burst_polygon_str}"'
            self.logger.critical(self.name, ErrorCode.ISO_METADATA_RENDER_FAILED, msg)

        output_product_metadata['burst_polygon'] = "".join(result.groups()[0].split(','))

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
            'ISO_OPERA_FilePackageName': self._core_filename(),
            'ISO_OPERA_ProducerGranuleId': self._core_filename(),
            'MetadataProviderAction': "creation",
            'GranuleFilename': self._core_filename(),
            'ISO_OPERA_ProjectKeywords': ['OPERA', 'JPL', 'CSLC', 'Co-registered', 'Single', 'Look', 'Complex'],
            'ISO_OPERA_PlatformKeywords': ['S1'],
            'ISO_OPERA_InstrumentKeywords': ['Sentinel 1 A/B']
        }

        return custom_metadata

    def _create_iso_metadata(self):
        """
        Creates a rendered version of the ISO metadata template for CSLC-S1
        output products using metadata from the following locations:

            * RunConfig (in dictionary form)
            * Output products (particularly the json metadata file)
            * Catalog metadata
            * "Custom" metadata (all metadata not found anywhere else)

        Returns
        -------
        rendered_template : str
            The ISO metadata template for CSLC-S1 filled in with values from
            the sourced metadata dictionaries.

        """
        runconfig_dict = self.runconfig.asdict()

        product_output_dict = self._collect_cslc_product_metadata()

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
        Executes the post-processing steps for the CSLC-S1 PGE.

        The CslcS1PostProcessorMixin version of this method performs the same
        steps as the base PostProcessorMixin, but inserts a step to perform
        output product validation prior to staging and renaming of the output
        files.

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the post-processor

        """
        print(f'Running postprocessor for {self._post_mixin_name}')

        self._run_sas_qa_executable()
        self._validate_output()
        self._stage_output_files()


class CslcS1Executor(CslcS1PreProcessorMixin, CslcS1PostProcessorMixin, PgeExecutor):
    """
    Main class for execution of the CSLC-S1 PGE, including the SAS layer.

    This class essentially rolls up the CSLC-specific pre- and post-processor
    functionality, while inheriting all other functionality for setup and execution
    of the SAS from the base PgeExecutor class.

    """

    NAME = "CSLC"
    """Short name for the CSLC-S1 PGE"""

    LEVEL = "L2"
    """Processing Level for CSLC-S1 Products"""

    SAS_VERSION = "0.1.2"  # https://github.com/opera-adt/COMPASS/releases/tag/v0.1.2
    """Version of the SAS wrapped by this PGE, should be updated as needed"""

    def __init__(self, pge_name, runconfig_path, **kwargs):
        super().__init__(pge_name, runconfig_path, **kwargs)

        self.rename_by_pattern_map = {
            '*.slc': self._geotiff_filename,
            '*.tif*': self._geotiff_filename,
            '*.json': self._json_metadata_filename
        }
