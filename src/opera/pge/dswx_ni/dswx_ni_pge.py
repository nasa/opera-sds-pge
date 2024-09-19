#!/usr/bin/env python3

"""
==============
dswx_ni_pge.py
==============
Module defining the implementation for the Dynamic Surface Water Extent (DSWX)
from NISAR (NI) PGE.

"""

import re
from os.path import basename, join

from opera.pge.base.base_pge import PgeExecutor
from opera.pge.dswx_s1.dswx_s1_pge import DSWxS1PostProcessorMixin, DSWxS1PreProcessorMixin
from opera.util.error_codes import ErrorCode
from opera.util.geo_utils import get_geographic_boundaries_from_mgrs_tile
from opera.util.mock_utils import MockGdal
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
    _tile_metadata_cache = {}
    _tile_filename_cache = {}

    def _validate_output_product_filenames(self):
        """
        This method validates output product file names assigned by the SAS
        via a regular expression. The output product file names should follow
        this convention:

            <PROJECT>_<LEVEL>_<PRODUCT TYPE>_<SOURCE>_<TILE ID>_<ACQUISITION TIMESTAMP>_
            <CREATION TIMESTAMP>_<SENSOR>_<SPACING>_<PRODUCT VERSION>_<BAND INDEX>_
            <BAND NAME>.<FILE EXTENSION>

        If the pattern does not match a critical error will cause a RuntimeError.
        If the pattern does match, this function will also read the product metadata
        from the GeoTIFF product, and cache it for later use.

        """
        pattern = re.compile(
            r'(?P<file_id>(?P<project>OPERA)_(?P<level>L3)_(?P<product_type>DSWx)-(?P<source>NI)_'
            r'(?P<tile_id>T[^\W_]{5})_(?P<acquisition_ts>\d{8}T\d{6}Z)_(?P<creation_ts>\d{8}T\d{6}Z)_'
            r'(?P<sensor>LSAR)_(?P<spacing>30)_(?P<product_version>v\d+[.]\d+))(_(?P<band_index>B\d{2})_'
            r'(?P<band_name>WTR|BWTR|CONF|DIAG)|_BROWSE)?[.](?P<ext>tif|tiff|png)$'
        )

        for output_file in self.runconfig.get_output_product_filenames():
            match_result = pattern.match(basename(output_file))
            if not match_result:
                error_msg = (f"Output file {output_file} does not match the output "
                             f"naming convention.")
                self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)
            else:
                tile_id = match_result.groupdict()['tile_id']
                file_id = match_result.groupdict()['file_id']

                if tile_id not in self._tile_metadata_cache:
                    # Cache the metadata for this product for use when generating the ISO XML
                    self._tile_metadata_cache[tile_id] = self._collect_dswx_ni_product_metadata(output_file)

                if tile_id not in self._tile_filename_cache:
                    # Cache the core filename for use when naming the ISO XML file
                    self._tile_filename_cache[tile_id] = file_id

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

    def _collect_dswx_ni_product_metadata(self, geotiff_product):
        """
        Gathers the available metadata from an output DSWx-NI product for
        use in filling out the ISO metadata template for the DSWx-NI PGE.

        Parameters
        ----------
        geotiff_product : str
            Path the GeoTIFF product to collect metadata from.

        Returns
        -------
        output_product_metadata : dict
            Dictionary containing DSWx-S1 output product metadata, formatted
            for use with the ISO metadata Jinja2 template.

        """
        # Extract all metadata assigned by the SAS at product creation time
        # TODO: current DSWx-NI GeoTIFF products do not contain any metadata
        #       so just use the mock set for the time being
        try:
            output_product_metadata = MockGdal.MockDSWxNIGdalDataset().GetMetadata()
        except Exception as err:
            msg = f'Failed to extract metadata from {geotiff_product}, reason: {err}'
            self.logger.critical(self.name, ErrorCode.ISO_METADATA_COULD_NOT_EXTRACT_METADATA, msg)

        # Get the Military Grid Reference System (MGRS) tile code and zone
        # identifier from the intermediate file name
        mgrs_tile_id = basename(geotiff_product).split('_')[3]

        output_product_metadata['tileCode'] = mgrs_tile_id
        output_product_metadata['zoneIdentifier'] = mgrs_tile_id[:2]

        # Translate the MGRS tile ID to a lat/lon bounding box
        (lat_min,
         lat_max,
         lon_min,
         lon_max) = get_geographic_boundaries_from_mgrs_tile(mgrs_tile_id)

        output_product_metadata['geospatial_lon_min'] = lon_min
        output_product_metadata['geospatial_lon_max'] = lon_max
        output_product_metadata['geospatial_lat_min'] = lat_min
        output_product_metadata['geospatial_lat_max'] = lat_max

        # Add some fields on the dimensions of the data. These values should
        # be the same for all DSWx-NI products, and were derived from the
        # ADT product spec
        output_product_metadata['xCoordinates'] = {
            'size': 3660,  # pixels
            'spacing': 30  # meters/pixel
        }
        output_product_metadata['yCoordinates'] = {
            'size': 3660,  # pixels
            'spacing': 30  # meters/pixel
        }

        return output_product_metadata

    def _create_custom_metadata(self, tile_filename):
        """
        Creates the "custom data" dictionary used with the ISO metadata rendering.

        Custom data contains all metadata information needed for the ISO template
        that is not found within any of the other metadata sources (such as the
        RunConfig, output product(s), or catalog metadata).

        Parameters
        ----------
        tile_filename : str
            Tile filename to be used as the granule identifier within the
            custom metadata.

        Returns
        -------
        custom_metadata : dict
            Dictionary containing the custom metadata as expected by the ISO
            metadata Jinja2 template.

        """
        custom_metadata = {
            'ISO_OPERA_FilePackageName': tile_filename,
            'ISO_OPERA_ProducerGranuleId': tile_filename,
            'MetadataProviderAction': "creation",
            'GranuleFilename': tile_filename,
            'ISO_OPERA_ProjectKeywords': ['OPERA', 'JPL', 'DSWx', 'Dynamic', 'Surface', 'Water', 'Extent'],
            'ISO_OPERA_PlatformKeywords': ['NI'],
            'ISO_OPERA_InstrumentKeywords': ['NISAR']
        }

        return custom_metadata

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
        # For DSWX-S1, each tile-set is assigned an ISO xml file
        for tile_id in self._tile_metadata_cache.keys():
            iso_metadata = self._create_iso_metadata(tile_id)

            iso_meta_filename = self._iso_metadata_filename(tile_id)
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

        self._validate_output()
        self._validate_output_product_filenames()
        self._run_sas_qa_executable()
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

    SAS_VERSION = "0.2"  # Beta release https://github.com/opera-adt/DSWX-SAR/releases/tag/DSWx-NI-v0.2
    """Version of the SAS wrapped by this PGE, should be updated as needed"""

    def __init__(self, pge_name, runconfig_path, **kwargs):
        super().__init__(pge_name, runconfig_path, **kwargs)

        self.rename_by_pattern_map = {}
