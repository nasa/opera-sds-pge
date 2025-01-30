#!/usr/bin/env python3

"""
==============
dswx_s1_pge.py
==============
Module defining the implementation for the Dynamic Surface Water Extent (DSWx)
from Sentinel-1 A/B (S1) PGE.

"""

import re
from datetime import datetime
from os.path import abspath, basename, exists, getsize, join, splitext

import opera.util.input_validation as input_validation
from opera.pge.base.base_pge import PgeExecutor
from opera.pge.base.base_pge import PostProcessorMixin
from opera.pge.base.base_pge import PreProcessorMixin
from opera.util.dataset_utils import get_sensor_from_spacecraft_name
from opera.util.error_codes import ErrorCode
from opera.util.geo_utils import get_geographic_boundaries_from_mgrs_tile
from opera.util.input_validation import validate_algorithm_parameters_config
from opera.util.input_validation import validate_dswx_inputs
from opera.util.render_jinja2 import render_jinja2, XML_VALIDATOR
from opera.util.run_utils import get_checksum
from opera.util.tiff_utils import get_geotiff_metadata
from opera.util.time import get_time_for_filename


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
    _valid_input_extensions = (".tif", ".h5")

    def _validate_dynamic_ancillary_inputs(self):
        """
        Evaluates the list of dynamic ancillary inputs from the RunConfig to
        ensure they exist and have an expected file extension.

        """
        dynamic_ancillary_file_group_dict = \
            self.runconfig.sas_config['runconfig']['groups']['dynamic_ancillary_file_group']

        for key, value in dynamic_ancillary_file_group_dict.items():
            if key in ('dem_file', 'glad_classification_file', 'reference_water_file', 'worldcover_file', 'hand_file'):
                input_validation.check_input(
                    value, self.logger, self.name, valid_extensions=('.tif', '.tiff', '.vrt')
                )
            elif key in ('shoreline_shapefile',):
                if value is not None:
                    input_validation.check_input(
                        value, self.logger, self.name, valid_extensions=('.shp',))
                    # Only the .shp file is configured in the runconfig, but we
                    # need to ensure the other required files are co-located with it
                    for extension in ('.dbf', '.prj', '.shx'):
                        additional_shapefile = splitext(value)[0] + extension

                        if not exists(abspath(additional_shapefile)):
                            error_msg = f"Additional shapefile {additional_shapefile} could not be located"

                            self.logger.critical(self.name, ErrorCode.INVALID_INPUT, error_msg)
                else:
                    msg = "No shoreline_shapefile specified in runconfig file."
                    self.logger.info(self.name, ErrorCode.INPUT_NOT_FOUND, msg)

            elif key in ('dem_file_description', 'worldcover_file_description',
                         'reference_water_file_description', 'hand_file_description',
                         'glad_classification_file_description', 'shoreline_shapefile_description'):
                # these fields are included in the SAS input paths, but are not
                # actually file paths, so skip them
                continue
            elif key in ('algorithm_parameters',):
                input_validation.check_input(
                    value, self.logger, self.name, valid_extensions=('.yaml', )
                )

    def _validate_static_ancillary_inputs(self):
        """
        Evaluates the list of static ancillary inputs from the RunConfig to
        ensure they exist and have an expected file extension.

        """
        static_ancillary_file_group_dict = \
            self.runconfig.sas_config['runconfig']['groups']['static_ancillary_file_group']

        for key, value in static_ancillary_file_group_dict.items():
            if key in ('mgrs_database_file', 'mgrs_collection_database_file'):
                input_validation.check_input(
                    value, self.logger, self.name, valid_extensions=('.sqlite', '.sqlite3')
                )
            elif key in ('static_ancillary_inputs_flag', ):
                # these fields are included in the SAS input paths, but are not
                # actually file paths, so skip them
                continue

    def run_preprocessor(self, **kwargs):
        """
        Executes the pre-processing steps for DSWx-S1 PGE initialization.
        The DswxS1PreProcessorMixin version of this class performs all actions
        of the base PreProcessorMixin class, and adds an input validation step for
        the inputs defined within the RunConfig.

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the pre-processor

        """
        super().run_preprocessor(**kwargs)

        validate_dswx_inputs(
            self.runconfig, self.logger, self.runconfig.pge_name,
            valid_extensions=self._valid_input_extensions
        )
        validate_algorithm_parameters_config(self.name,
                                             self.runconfig.algorithm_parameters_schema_path,
                                             self.runconfig.algorithm_parameters_file_config_path,
                                             self.logger)
        self._validate_dynamic_ancillary_inputs()
        self._validate_static_ancillary_inputs()


class DSWxS1PostProcessorMixin(PostProcessorMixin):
    """
    Mixin class responsible for handling all post-processing steps for the DSWx-S1
    PGE. The post-processing phase is defined as all steps required after SAS
    execution has completed, prior to handover of output products to PCM.

    In addition to the base functionality inherited from PostProcessorMixin, this
    mixin adds an output validation step to ensure that the output file(s) defined
    by the RunConfig exist and are valid.

    """

    _post_mixin_name = "DSWxS1PostProcessorMixin"
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
            r'(?P<file_id>(?P<project>OPERA)_(?P<level>L3)_(?P<product_type>DSWx)-(?P<source>S1)_'
            r'(?P<tile_id>T[^\W_]{5})_(?P<acquisition_ts>\d{8}T\d{6}Z)_(?P<creation_ts>\d{8}T\d{6}Z)_'
            r'(?P<sensor>S1A|S1B)_(?P<spacing>30)_(?P<product_version>v\d+[.]\d+))(_(?P<band_index>B\d{2})_'
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
                    dswx_metadata = self._collect_dswx_s1_product_metadata(output_file)

                    # TODO: kludge since SAS hardcodes SPACECRAFT_NAME to "Sentinel-1A/B"
                    dswx_metadata['MeasuredParameters']['SPACECRAFT_NAME']['value'] = \
                        "Sentinel-1A" if match_result.groupdict()['sensor'] == "S1A" else "Sentinel-1B"

                    # Cache the metadata for this product for use when generating the ISO XML
                    self._tile_metadata_cache[tile_id] = dswx_metadata

                if tile_id not in self._tile_filename_cache:
                    # Cache the core filename for use when naming the ISO XML file
                    self._tile_filename_cache[tile_id] = file_id

    def _validate_output(self):
        """
        Evaluates the output file(s) generated from SAS execution to ensure:
            - That the file(s) contains some content (size is greater than 0).
            - That the .tif output files (band data) end with 'B01_WTR',
              'B02_BWTR', 'B03_CONF', 'B04_DIAG' or 'BROWSE'
            - That the there are the same number of each type of file, implying
              3 output bands per tile

        """
        EXPECTED_NUM_BANDS: int = 5
        band_dict = {}
        num_bands = []
        output_extension = '.tif'

        # get all .tiff files
        output_products = list(
            filter(
                lambda filename: output_extension in filename,
                self.runconfig.get_output_product_filenames()
            )
        )

        if not output_products:
            error_msg = (f"No SAS output file(s) with '{output_extension}' extension "
                         f"found within '{self.runconfig.output_product_path}'")

            self.logger.critical(self.name, ErrorCode.OUTPUT_NOT_FOUND, error_msg)

        for out_product in output_products:
            if not getsize(out_product):
                error_msg = f"SAS output file {out_product} was created, but is empty"

                self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

            #  Gather the output files into a dictionary
            #     key = band type (e.g. B01_WTR.tif)
            #     value = list of filenames of this type (e.g. ['OPERA_L3_DSWx-S1_..._v0.1_B01_WTR.tif', ...]
            key = '_'.join(out_product.split('_')[-2:])
            if key not in band_dict:
                band_dict[key] = []
            band_dict[key].append(out_product)

        if len(band_dict.keys()) != EXPECTED_NUM_BANDS:
            error_msg = (f"Invalid SAS output file, wrong number of bands, "
                         f"expected {EXPECTED_NUM_BANDS}, found {band_dict.keys()}")

            self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

        # Make a list of the numbers of bands per band type
        for band in band_dict.keys():
            num_bands.append(len(band_dict[band]))

        if not all(band_type == num_bands[0] for band_type in num_bands):
            error_msg = f"Missing or extra band files: number of band files per " \
                        f"band: {num_bands}"

            self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

    def _checksum_output_products(self):
        """
        Generates a dictionary mapping output product file names to the
        corresponding MD5 checksum digest of the file's contents.

        The products to generate checksums for are determined by scanning
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

        # Filter out any files that do not end with the expected extensions
        expected_extensions = ('.tif', '.png')
        filtered_output_products = filter(
            lambda product: splitext(product)[-1] in expected_extensions,
            output_products
        )

        # Generate checksums on the filtered product list
        checksums = {
            basename(output_product): get_checksum(output_product)
            for output_product in filtered_output_products
        }

        return checksums

    def _ancillary_filename(self):
        """
        Helper method to derive the core component of the file names for the
        ancillary products associated to a PGE job (catalog metadata, log file,
        etc...).

        The core file name component for DSWx-S1 ancillary products consists of:

        <PROJECT>_<LEVEL>_<PGE NAME>_<PROD TIMETAG>_<SENSOR>_<SPACING>_<PRODUCT VERSION>

        Since these files are not specific to any particular tile processed for
        a DSWx-S1 job, fields such as tile ID and acquisition time are omitted from
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
        dswx_metadata = list(self._tile_metadata_cache.values())[0]['MeasuredParameters']

        spacecraft_name = dswx_metadata['SPACECRAFT_NAME']['value']
        sensor = get_sensor_from_spacecraft_name(spacecraft_name)
        pixel_spacing = "30"  # fixed for tile-based products

        processing_time = get_time_for_filename(
            datetime.strptime(dswx_metadata['PROCESSING_DATETIME']['value'], '%Y-%m-%dT%H:%M:%SZ')
        )

        if not processing_time.endswith('Z'):
            processing_time = f'{processing_time}Z'

        product_version = str(self.runconfig.product_version)

        if not product_version.startswith('v'):
            product_version = f'v{product_version}'

        ancillary_filename = (
            f"{self.PROJECT}_{self.LEVEL}_{self.NAME}_{processing_time}_"
            f"{sensor}_{pixel_spacing}_{product_version}"
        )

        return ancillary_filename

    def _catalog_metadata_filename(self):
        """
        Returns the file name to use for Catalog Metadata produced by the DSWx-S1 PGE.

        The Catalog Metadata file name for the DSWx-S1 PGE consists of:

            <Ancillary filename>.catalog.json

        Where <Ancillary filename> is returned by DSWxS1PostProcessorMixin._ancillary_filename()

        Returns
        -------
        <catalog metadata filename> : str
            The file name to assign to the Catalog Metadata product created by this PGE.

        """
        return self._ancillary_filename() + ".catalog.json"

    def _iso_metadata_filename(self, tile_id):
        """
        Returns the file name to use for ISO Metadata produced by the DSWX-S1 PGE.

        The ISO Metadata file name for the DSWX-S1 PGE consists of:

            <DSWX-S1 filename>.iso.xml

        Where <DSWX-S1 filename> is returned by DSWxS1PostProcessorMixin._tile_filename()

        Parameters
        ----------
        tile_id : str
            The MGRS tile identifier used to look up the corresponding cached
            DSWx-S1 file name.

        Returns
        -------
        <iso metadata filename> : str
            The file name to assign to the ISO Metadata product created by this PGE.

        """
        if tile_id not in self._tile_filename_cache:
            raise RuntimeError(f"No file name cached for tile ID {tile_id}")

        iso_metadata_filename = self._tile_filename_cache[tile_id]

        return iso_metadata_filename + ".iso.xml"

    def _log_filename(self):
        """
        Returns the file name to use for the PGE/SAS log file produced by the DSWx-S1 PGE.

        The log file name for the DSWx-S1 PGE consists of:

            <Ancillary filename>.log

        Where <Ancillary filename> is returned by DSWxS1PostProcessorMixin._ancillary_filename()

        Returns
        -------
        log_filename : str
            The file name to assign to the PGE/SAS log created by this PGE.

        """
        return self._ancillary_filename() + ".log"

    def _qa_log_filename(self):
        """
        Returns the file name to use for the Quality Assurance application log
        file produced by the DSWx-S1 PGE.

        The log file name for the DSWx-S1 PGE consists of:

            <Ancillary filename>.qa.log

        Where <Ancillary filename> is returned by DSWxS1PostProcessorMixin._ancillary_filename()

        Returns
        -------
        log_filename : str
            The file name to assign to the QA log created by this PGE.

        """
        return self._ancillary_filename() + ".qa.log"

    def _collect_dswx_s1_product_metadata(self, geotiff_product):
        """
        Gathers the available metadata from an output DSWx-S1 product for
        use in filling out the ISO metadata template for the DSWx-S1 PGE.

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
        output_product_metadata = dict()

        # Extract all metadata assigned by the SAS at product creation time
        try:
            measured_parameters = get_geotiff_metadata(geotiff_product)
            output_product_metadata['MeasuredParameters'] = self.augment_measured_parameters(measured_parameters)
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
        # be the same for all DSWx-S1 products, and were derived from the
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
            'ISO_OPERA_PlatformKeywords': ['S1'],
            'ISO_OPERA_InstrumentKeywords': ['Sentinel 1 A/B']
        }

        return custom_metadata

    def _create_iso_metadata(self, tile_id):
        """
        Creates a rendered version of the ISO metadata template for DSWX-S1
        output products using metadata from the following locations:

            * RunConfig (in dictionary form)
            * Output product (dictionary extracted from HDF5 product, per-tile)
            * Catalog metadata
            * "Custom" metadata (all metadata not found anywhere else)

        Parameters
        ----------
        tile_id : str
            MGRS tile identifier used to look up the metadata used to instantiate
            the ISO template.

        Returns
        -------
        rendered_template : str
            The ISO metadata template for DSWX-S1 filled in with values from
            the sourced metadata dictionaries.

        """
        # Use the base PGE implemenation to validate existence of the template
        super()._create_iso_metadata()

        if tile_id not in self._tile_metadata_cache or tile_id not in self._tile_filename_cache:
            raise RuntimeError(f"No file name or metadata cached for tile ID {tile_id}")

        tile_metadata = self._tile_metadata_cache[tile_id]
        tile_filename = self._tile_filename_cache[tile_id]

        runconfig_dict = self.runconfig.asdict()

        product_output_dict = tile_metadata

        catalog_metadata_dict = self._create_catalog_metadata().asdict()

        custom_data_dict = self._create_custom_metadata(tile_filename)

        iso_metadata = {
            'run_config': runconfig_dict,
            'product_output': product_output_dict,
            'catalog_metadata': catalog_metadata_dict,
            'custom_data': custom_data_dict
        }

        iso_template_path = abspath(self.runconfig.iso_template_path)

        rendered_template = render_jinja2(iso_template_path, iso_metadata, self.logger, validator=XML_VALIDATOR)

        return rendered_template

    def _stage_output_files(self):
        """
        Ensures that all output products produced by both the SAS and this PGE
        are staged to the output location defined by the RunConfig.

        For DSWx-S1, this only includes the ancillary outputs created by the PGE
        (catalog metadata, ISO XML, etc.), since the DSWx-S1 performs its own
        file name application and staging to the output directory.

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
        Executes the post-processing steps for the DSWx-S1 PGE.
        The DSWxS1PostProcessorMixin version of this method performs the same
        steps as the base PostProcessorMixin, but inserts a step to perform
        output product validation prior to staging and renaming of the output
        files.

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the post-processor

        """
        self._validate_output()
        self._validate_output_product_filenames()
        self._run_sas_qa_executable()
        self._stage_output_files()


class DSWxS1Executor(DSWxS1PreProcessorMixin, DSWxS1PostProcessorMixin, PgeExecutor):
    """
    Main class for execution of the DSWx-S1 PGE, including the SAS layer.
    This class essentially rolls up the DSWx-specific pre- and post-processor
    functionality, while inheriting all other functionality for setup and execution
    of the SAS from the base PgeExecutor class.

    """

    NAME = "DSWx-S1"
    """Short name for the L3_DSWx_S1 PGE"""

    LEVEL = "L3"
    """Processing Level for DSWx-S1 Products"""

    PGE_VERSION = "3.0.2"
    """Version of the PGE (overrides default from base_pge)"""

    SAS_VERSION = "1.1"  # Final release https://github.com/opera-adt/DSWX-SAR/releases/tag/v1.1
    """Version of the SAS wrapped by this PGE, should be updated as needed"""

    def __init__(self, pge_name, runconfig_path, **kwargs):
        super().__init__(pge_name, runconfig_path, **kwargs)

        # Used in base_pge.py to rename and keep track of files
        # renamed by the PGE
        self.rename_by_pattern_map = {}
