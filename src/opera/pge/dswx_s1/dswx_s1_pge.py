#!/usr/bin/env python3

"""
==============
dswx_s1_pge.py
==============
Module defining the implementation for the Dynamic Surface Water Extent (DSWx)
from Sentinel-1 A/B (S1) PGE.

"""

import glob
from datetime import datetime
from os.path import abspath, basename, dirname, exists, getsize, join, splitext

import opera.util.input_validation as input_validation
from opera.pge.base.base_pge import PgeExecutor
from opera.pge.base.base_pge import PostProcessorMixin
from opera.pge.base.base_pge import PreProcessorMixin
from opera.util.dataset_utils import get_sensor_from_spacecraft_name
from opera.util.error_codes import ErrorCode
from opera.util.geo_utils import get_geographic_boundaries_from_mgrs_tile
from opera.util.input_validation import validate_algorithm_parameters_config
from opera.util.input_validation import validate_dswx_inputs
from opera.util.render_jinja2 import render_jinja2
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

    def _validate_dynamic_ancillary_inputs(self):
        """
        Evaluates the list of dynamic ancillary inputs from the RunConfig to
        ensure they exist and have an expected file extension.

        """
        dynamic_ancillary_file_group_dict = \
            self.runconfig.sas_config['runconfig']['groups']['dynamic_ancillary_file_group']

        for key, value in dynamic_ancillary_file_group_dict.items():
            if key in ('dem_file', 'reference_water_file', 'worldcover_file', 'hand_file'):
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
                         'shoreline_shapefile_description'):
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
            self.runconfig, self.logger, self.runconfig.pge_name, valid_extensions=(".tif", ".h5")
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

    def _validate_output(self):
        """
        Evaluates the output file(s) generated from SAS execution to ensure:
            - That the file(s) contains some content (size is greater than 0).
            - That the .tif output files (band data) end with 'B01_WTR',
              'B02_BWTR', 'B03_CONF' or 'B04_DIAG'
            - That the there are the same number of each type of file, implying
              3 output bands per tile

        """
        EXPECTED_NUM_BANDS: int = 4
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

    def _core_filename(self, inter_filename=None):
        """
        Returns the core file name component for products produced by the
        DSWx-S1 PGE.

        The core file name component of the DSWx-S1 PGE consists of:

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

    def _tile_filename(self, inter_filename=None):
        """
        Returns the file name to use for MGRS tile-based DSWx products produced
        by this PGE.

        The filename for the DSWx-S1 tile products consists of:

        <Core filename>_<TILE ID>_<ACQ TIMETAG>_<PROD TIMETAG>_<SENSOR>_<SPACING>_<PRODUCT VERSION>

        Where <Core filename> is returned by DSWxS1PostProcessorMixin._core_filename()

        Callers of this function are responsible for assignment of any other
        product-specific fields, such as the file extension.

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
        tile_filename : str
            The filename component to assign to tile-based products created by
            this PGE.

        """
        core_filename = self._core_filename(inter_filename)

        # The tile ID should be included within the intermediate filename,
        # extract it and prepare it for use within the final filename
        tile_id = basename(inter_filename).split('_')[3]

        if tile_id in self._tile_metadata_cache:
            dswx_metadata = self._tile_metadata_cache[tile_id]
        else:
            # Collect the metadata from the GeoTIFF output product
            dswx_metadata = self._collect_dswx_s1_product_metadata(inter_filename)

            # TODO: kludge since SAS hardcodes SPACECRAFT_NAME to "Sentinel-1A/B"
            dswx_metadata['SPACECRAFT_NAME'] = "Sentinel-1A" if "S1A" in inter_filename else "Sentinel-1B"

            self._tile_metadata_cache[tile_id] = dswx_metadata

        spacecraft_name = dswx_metadata['SPACECRAFT_NAME']
        sensor = get_sensor_from_spacecraft_name(spacecraft_name)
        pixel_spacing = "30"  # fixed for tile-based products

        acquisition_time = get_time_for_filename(
            datetime.strptime(dswx_metadata['RTC_SENSING_START_TIME'], '%Y-%m-%dT%H:%M:%SZ')
        )

        if not acquisition_time.endswith('Z'):
            acquisition_time = f'{acquisition_time}Z'

        processing_time = get_time_for_filename(
            datetime.strptime(dswx_metadata['PROCESSING_DATETIME'], '%Y-%m-%dT%H:%M:%SZ')
        )

        if not processing_time.endswith('Z'):
            processing_time = f'{processing_time}Z'

        product_version = str(self.runconfig.product_version)

        if not product_version.startswith('v'):
            product_version = f'v{product_version}'

        tile_filename = (
            f"{core_filename}_{tile_id}_{acquisition_time}_{processing_time}_"
            f"{sensor}_{pixel_spacing}_{product_version}"
        )

        # Cache the file name for this tile ID, so it can be used with the
        # ISO metadata later.
        self._tile_filename_cache[tile_id] = tile_filename

        return tile_filename

    def _geotiff_filename(self, inter_filename):
        """
        Returns the file name to use for GeoTIFF's produced by the DSWx-S1 PGE.

        The GeoTIFF filename for the DSWx-S1 PGE consists of:

            <Tile filename>_<Band Index>_<Band Name>.tif

        Where <Tile filename> is returned by DSWxS1PostProcessorMixin._tile_filename()
        and <Band Index> and <Band Name> are determined from the name of the
        intermediate geotiff file to be renamed.

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
        tile_filename = self._tile_filename(inter_filename)

        # Specific output product band index and name should be the last parts
        # of the filename before the extension, delimited by underscores
        band_idx, band_name = splitext(inter_filename)[0].split("_")[-2:]

        return f"{tile_filename}_{band_idx}_{band_name}.tif"

    def _browse_filename(self, inter_filename):
        """
        Returns the file name to use for the PNG browse image produced by
        the DSWx-S1 PGE.

        The browse image filename for the DSWx-S1 PGE consists of:

            <Tile filename>_BROWSE.png

        Where <Tile filename> is returned by DSWxS1PostProcessorMixin._tile_filename().

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the output browse image from which to
            generate a filename. This parameter may be used to inspect the
            file in order to derive any necessary components of the returned filename.

        Returns
        -------
        browse_image_filename : str
            The file name to assign to browse image created by this PGE.

        """
        # Find one of the tif files corresponding to the provided browse image
        # based on the tile ID
        tile_id = basename(inter_filename).split('_')[3]

        tif_pattern = f"*{tile_id}*.tif*"

        tif_files = list(glob.glob(join(dirname(inter_filename), tif_pattern)))

        if not len(tif_files):
            error_msg = f"Could not find any .tif files corresponding to browse image {inter_filename}"
            self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

        # Now we derive the core (tile) filename using the tif file(s) we located,
        # since we need to extract product metadata to form the correct filename.
        # We can use the first tif file in the list, since they should all have
        # the same metadata.
        tile_filename = self._tile_filename(tif_files[0])

        # Add the portion specific to browse images
        return f"{tile_filename}_BROWSE.png"

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
        dswx_metadata = list(self._tile_metadata_cache.values())[0]

        spacecraft_name = dswx_metadata['SPACECRAFT_NAME']
        sensor = get_sensor_from_spacecraft_name(spacecraft_name)
        pixel_spacing = "30"  # fixed for tile-based products

        processing_time = get_time_for_filename(
            datetime.strptime(dswx_metadata['PROCESSING_DATETIME'], '%Y-%m-%dT%H:%M:%SZ')
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
        # Extract all metadata assigned by the SAS at product creation time
        output_product_metadata = get_geotiff_metadata(geotiff_product)

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
            'ISO_OPERA_ProjectKeywords': ['OPERA', 'JPL', 'DSWx', 'Dynamic', 'Surface', 'Water', 'Extent'],
            'ISO_OPERA_PlatformKeywords': ['S1'],
            'ISO_OPERA_InstrumentKeywords': ['Sentinel 1 A/B']
        }

        return custom_metadata

    def _create_iso_metadata(self, tile_metadata):
        """
        Creates a rendered version of the ISO metadata template for DSWX-S1
        output products using metadata from the following locations:

            * RunConfig (in dictionary form)
            * Output product (dictionary extracted from HDF5 product, per-tile)
            * Catalog metadata
            * "Custom" metadata (all metadata not found anywhere else)

        Parameters
        ----------
        tile_metadata : dict
            The product metadata corresponding to a specific tile product to
            be included as the "product_output" metadata in the rendered ISO xml.

        Returns
        -------
        rendered_template : str
            The ISO metadata template for DSWX-S1 filled in with values from
            the sourced metadata dictionaries.

        """
        runconfig_dict = self.runconfig.asdict()

        product_output_dict = tile_metadata

        catalog_metadata_dict = self._create_catalog_metadata().asdict()

        custom_data_dict = self._create_custom_metadata()

        iso_metadata = {
            'run_config': runconfig_dict,
            'product_output': product_output_dict,
            'catalog_metadata': catalog_metadata_dict,
            'custom_data': custom_data_dict
        }

        iso_template_path = abspath(self.runconfig.iso_template_path)

        if not exists(iso_template_path):
            msg = f"Could not load ISO template {iso_template_path}, file does not exist"
            self.logger.critical(self.name, ErrorCode.ISO_METADATA_TEMPLATE_NOT_FOUND, msg)

        rendered_template = render_jinja2(iso_template_path, iso_metadata, self.logger)

        return rendered_template

    def _stage_output_files(self):
        """
        Ensures that all output products produced by both the SAS and this PGE
        are staged to the output location defined by the RunConfig. This includes
        reassignment of file names to meet the file-naming conventions required
        by the PGE.

        This version of the method performs the same steps as the base PGE
        implementation, except that an ISO xml metadata file is rendered for
        each tile product covered by the input region.

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
        # For DSWX-S1, each tile-set is assigned an ISO xml file
        for tile_id, tile_metadata in self._tile_metadata_cache.items():
            iso_metadata = self._create_iso_metadata(tile_metadata)

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
        self._run_sas_qa_executable()
        self._validate_output()
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

    SAS_VERSION = "0.4"  # Gamma release https://github.com/opera-adt/DSWX-SAR/releases/tag/v0.4
    """Version of the SAS wrapped by this PGE, should be updated as needed"""

    def __init__(self, pge_name, runconfig_path, **kwargs):
        super().__init__(pge_name, runconfig_path, **kwargs)

        # Used in base_pge.py to rename and keep track of files
        # renamed by the PGE
        self.rename_by_pattern_map = {
            '*.tif*': self._geotiff_filename,
            '*.png': self._browse_filename
        }
