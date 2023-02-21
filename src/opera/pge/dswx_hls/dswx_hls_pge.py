#!/usr/bin/env python3

"""
===============
dswx_hls_pge.py
===============

Module defining the implementation for the Dynamic Surface Water Extent (DSWx)
from Harmonized Landsat and Sentinel-1 (HLS) PGE.

"""

import glob
import os.path
import re
from collections import OrderedDict
from os.path import abspath, basename, exists, isdir, join, splitext

import opera.util.input_validation as input_validation
from opera.pge.base.base_pge import PgeExecutor
from opera.pge.base.base_pge import PostProcessorMixin
from opera.pge.base.base_pge import PreProcessorMixin
from opera.util.error_codes import ErrorCode
from opera.util.img_utils import get_geotiff_hls_dataset
from opera.util.img_utils import get_geotiff_metadata
from opera.util.img_utils import get_geotiff_processing_datetime
from opera.util.img_utils import get_geotiff_sensor_product_id
from opera.util.img_utils import get_geotiff_spacecraft_name
from opera.util.img_utils import get_hls_filename_fields
from opera.util.img_utils import set_geotiff_metadata
from opera.util.metadata_utils import get_geographic_boundaries_from_mgrs_tile
from opera.util.metadata_utils import get_sensor_from_spacecraft_name
from opera.util.render_jinja2 import render_jinja2
from opera.util.time import get_time_for_filename


class DSWxHLSPreProcessorMixin(PreProcessorMixin):
    """
    Mixin class responsible for handling all pre-processing steps for the
    DSWx-HLS PGE. The pre-processing phase is defined as all steps necessary prior
    to SAS execution.

    In addition to the base functionality inherited from PreProcessorMixin, this
    mixin adds an input validation step to ensure that the input(s) defined by
    the RunConfig exist and are valid.

    """

    _pre_mixin_name = "DSWxHLSPreProcessorMixin"

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
                list_of_input_tifs = glob.glob(join(input_file_path, '*.tif*'))

                if len(list_of_input_tifs) <= 0:
                    error_msg = f"Input directory {input_file_path} does not contain any tif files"

                    self.logger.critical(self.name, ErrorCode.INPUT_NOT_FOUND, error_msg)
            elif not input_file_path.endswith(".tif"):
                error_msg = f"Input file {input_file_path} does not have .tif extension"

                self.logger.critical(self.name, ErrorCode.INVALID_INPUT, error_msg)

    def _validate_ancillary_inputs(self):
        """
        Evaluates the list of ancillary inputs from the RunConfig to ensure they
        are exist and have an expected file extension.

        For the shoreline shapefile, this method also checks to ensure a full
        set of expected shapefiles were provided alongside the .shp file configured
        by the RunConfig.

        """
        dynamic_ancillary_file_group_dict = \
            self.runconfig.sas_config['runconfig']['groups']['dynamic_ancillary_file_group']

        for key, value in dynamic_ancillary_file_group_dict.items():
            if key in ('dem_file', 'worldcover_file'):
                input_validation.check_input(
                    value, self.logger, self.name, valid_extensions=('.tif', '.tiff', '.vrt')
                )
            elif key in ('landcover_file',):
                input_validation.check_input(
                    value, self.logger, self.name, valid_extensions=('.tif', '.tiff')
                )
            elif key in ('shoreline_shapefile',):
                input_validation.check_input(
                    value, self.logger, self.name, valid_extensions=('.shp',)
                )

                # Only the .shp file is configured in the runconfig, but we
                # need to ensure the other required files are co-located with it
                for extension in ('.dbf', '.prj', '.shx'):
                    additional_shapefile = splitext(value)[0] + extension

                    if not exists(abspath(additional_shapefile)):
                        error_msg = f"Additional shapefile {additional_shapefile} could not be located"

                        self.logger.critical(self.name, ErrorCode.INVALID_INPUT, error_msg)

            elif key in ('dem_file_description', 'landcover_file_description',
                         'worldcover_file_description', 'shoreline_shapefile_description'):
                # these fields are included in the SAS input paths, but are not
                # actually file paths, so skip them
                continue

    def _validate_expected_input_platforms(self):
        """
        Scans the input files to make sure that the data comes from expected
        platforms only. Currently, Landsat 8/9, or Sentinel 2 A/B.

        Raises an exception if an unsupported platform is detected.

        This function assumes that input files have been checked to exist.
        It also assumes that only files that contain the metadata keys
        LANDSAT_PRODUCT_ID for Landsat input, and PRODUCT_URI for Sentinel
        input, need to be checked.

        """
        self.logger.info(
            self.name, ErrorCode.UPDATING_PRODUCT_METADATA,
            'Scanning DSWx input datasets for invalid platforms.'
        )

        # Get a list of input files to check for invalid platform metadata
        list_of_input_tifs = []
        for input_file in self.runconfig.input_files:
            input_file_path = abspath(input_file)
            if isdir(input_file_path):
                list_of_input_tifs = glob.glob(join(input_file_path, '*.tif*'))
            else:
                list_of_input_tifs.append(input_file_path)

        for input_tif in list_of_input_tifs:

            if re.match(r"^HLS\.L30.*", os.path.basename(input_tif)):
                input_tif_metadata = get_geotiff_metadata(input_tif)
                if 'LANDSAT_PRODUCT_ID' in input_tif_metadata:
                    # LANDSAT_PRODUCT_ID can be a list so we don't restrict search to first element
                    if re.match(r"LC07.*", input_tif_metadata['LANDSAT_PRODUCT_ID']):
                        error_msg = (f"Input file {input_tif} appears to contain Landsat-7 data, "
                                     f"LANDSAT_PRODUCT_ID is {input_tif_metadata['LANDSAT_PRODUCT_ID']}.")
                        self.logger.critical(self.name, ErrorCode.INVALID_INPUT, error_msg)

            if re.match(r"^HLS\.S30.*", os.path.basename(input_tif)):
                input_tif_metadata = get_geotiff_metadata(input_tif)
                if 'PRODUCT_URI' in input_tif_metadata:
                    data_is_S2A = re.match(r"S2A.*", input_tif_metadata['PRODUCT_URI'])
                    data_is_S2B = re.match(r"S2B.*", input_tif_metadata['PRODUCT_URI'])
                    if not data_is_S2A and not data_is_S2B:
                        error_msg = (f"Input file {input_tif} appears to not be Sentinel 2 A/B data, "
                                     f"metadata PRODUCT_URI is {input_tif_metadata['PRODUCT_URI']}.")
                        self.logger.critical(self.name, ErrorCode.INVALID_INPUT, error_msg)

    def run_preprocessor(self, **kwargs):
        """
        Executes the pre-processing steps for DSWx-HLS PGE initialization.

        The DSWxHLSPreProcessorMixin version of this function performs all actions
        of the base PreProcessorMixin class, and adds the validation check for
        input files/directories.

        Parameters
        ----------
        **kwargs : dict
            Any keyword arguments needed by the pre-processor

        """
        super().run_preprocessor(**kwargs)

        self._validate_inputs()
        self._validate_ancillary_inputs()
        self._validate_expected_input_platforms()


class DSWxHLSPostProcessorMixin(PostProcessorMixin):
    """
    Mixin class responsible for handling all post-processing steps for the
    DSWx-HLS PGE. The post-processing phase is defined as all steps necessary
    after SAS execution has completed.

    In addition to the base functionality inherited from PostProcessorMixin, this
    mixin adds an output validation step to ensure that the output file defined by
    the RunConfig exist and are valid.

    """

    _post_mixin_name = "DSWxHLSPostProcessorMixin"
    _cached_core_filename = None

    def _validate_output(self):
        """
        Evaluates the output file(s) generated from SAS execution to ensure
        existence, and that the file(s) contains some content (size is greater than
        0).
        """
        # Get the product ID that the SAS should have used to tag all output images
        product_id = self.runconfig.sas_config['runconfig']['groups']['product_path_group']['product_id']

        output_products = list(
            filter(
                lambda filename: product_id in filename,
                self.runconfig.get_output_product_filenames()
            )
        )

        if not output_products:
            error_msg = (f"No SAS output file(s) containing product ID {product_id} "
                         f"found within {self.runconfig.output_product_path}")

            self.logger.critical(self.name, ErrorCode.OUTPUT_NOT_FOUND, error_msg)

        for output_product in output_products:
            if not os.path.getsize(output_product):
                error_msg = f"SAS output file {output_product} was created, but is empty"

                self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

    def _correct_landsat_9_products(self):
        """
        Scans the set of output DSWx products to see if the metadata identifies
        any/all of them to have originated from Landsat-9 data, and if so,
        make the necessary corrections to the product metadata to remove any
        references to Landsat-8 that may be erroneously present.

        """
        self.logger.info(
            self.name, ErrorCode.UPDATING_PRODUCT_METADATA,
            'Scanning DSWx output products for Landsat-9 metadata correction'
        )

        # Get the list of output products and filter for the images
        output_products = self.runconfig.get_output_product_filenames()

        # Filter to only images (.tif or .tiff)
        output_images = filter(lambda product: 'tif' in splitext(product)[-1], output_products)

        for output_image in output_images:
            sensor_product_id = get_geotiff_sensor_product_id(output_image)

            # Certain HLS products have been observed to have sensor product
            # ID's that identify them as originating from Landsat-9, but
            # specify the Landsat-8 as the spacecraft name. To ensure this
            # error is not propagated to DSWx products, we correct the spacecraft
            # name within the product metadata here.
            if re.match(r"L[COTEM]09.*", sensor_product_id):
                self.logger.info(
                    self.name, ErrorCode.UPDATING_PRODUCT_METADATA,
                    f'Correcting SPACECRAFT_NAME field for Landsat-9 based product '
                    f'{basename(output_image)}'
                )
                set_geotiff_metadata(
                    output_image, scratch_dir=self.runconfig.scratch_path,
                    SPACECRAFT_NAME="Landsat-9"
                )

    def _core_filename(self, inter_filename=None):
        """
        Returns the core file name component for products produced by the
        DSWx PGE.

        The core file name component of the DSWx PGE consists of:

        <PROJECT>_<LEVEL>_<PGE NAME>-<SOURCE>_<TILE ID>_<ACQ TIMETAG>_
        <PROD TIMETAG>_<SENSOR>_<SPACING>_<PRODUCT VERSION>

        Callers of this function are responsible for assignment of any other
        product-specific fields, such as the file extension.

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

        if not inter_filename:
            msg = (f"No filename provided to {self.__class__.__name__}._core_filename(), "
                   f"First call must provide a filename before result is cached.")
            self.logger.critical(self.name, ErrorCode.FILE_MOVE_FAILED, msg)

        # Find a representative geotiff file, which should be co-located with
        # whatever intermediate product name we were handed
        # they should all have same metadata
        product_dir = os.path.dirname(inter_filename)
        geotiff_files = glob.glob(join(product_dir, '*.tif*'))

        if not geotiff_files:
            msg = (f"Could not find sample output product to derive metadata from "
                   f"within {product_dir}")
            self.logger.critical(self.name, ErrorCode.FILE_MOVE_FAILED, msg)

        geotiff_file = geotiff_files[0]

        spacecraft_name = get_geotiff_spacecraft_name(geotiff_file)
        sensor = get_sensor_from_spacecraft_name(spacecraft_name)
        pixel_spacing = "30"  # fixed for HLS-based products

        dataset = get_geotiff_hls_dataset(geotiff_file)

        dataset_fields = get_hls_filename_fields(dataset)

        source = dataset_fields['product']
        tile_id = dataset_fields['tile_id']
        acquisition_time = dataset_fields['acquisition_time']

        if not acquisition_time.endswith('Z'):
            acquisition_time = f'{acquisition_time}Z'

        processing_datetime = get_geotiff_processing_datetime(geotiff_file)
        processing_time = get_time_for_filename(processing_datetime)

        if not processing_time.endswith('Z'):
            processing_time = f'{processing_time}Z'

        product_version = str(self.runconfig.product_version)

        if not product_version.startswith('v'):
            product_version = f'v{product_version}'

        # Assign the core file to the cached class attribute
        self._cached_core_filename = (
            f"{self.PROJECT}_{self.LEVEL}_{self.NAME}-{source}_{tile_id}_"
            f"{acquisition_time}_{processing_time}_{sensor}_{pixel_spacing}_"
            f"{product_version}"
        )

        return self._cached_core_filename

    def _geotiff_filename(self, inter_filename):
        """
        Returns the file name to use for GeoTIFF's produced by the DSWx-HLS PGE.

        The GeoTIFF filename for the DSWx-HLS PGE consists of:

            <Core filename>_<Band Index>_<Band Name>.tif

        Where <Core filename> is returned by DSWxHLSPostProcessorMixin._core_filename()
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
        core_filename = self._core_filename(inter_filename)

        # Specific output product band index and name should be the last parts
        # of the filename before the extension, delimited by underscores
        band_idx, band_name = splitext(inter_filename)[0].split("_")[-2:]

        return f"{core_filename}_{band_idx}_{band_name}.tif"

    def _browse_image_filename(self, inter_filename):
        """
        Returns the file name to use for PNG browse image produced by the DSWx-HLS PGE.

        The browse image filename for the DSWx-HLS PGE consists of:

            <Core filename>_BROWSE.<ext>

        Where <Core filename> is returned by DSWxHLSPostProcessorMixin._core_filename(),
        and <ext> is the file extension from inter_filename (should be either
        .tif or .png).

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the output browse image to generate
            a filename for. This parameter may be used to inspect the file
            in order to derive any necessary components of the returned filename.

        Returns
        -------
        browse_image_filename : str
            The file name to assign to browse image product(s) created by this PGE.

        """
        core_filename = self._core_filename(inter_filename)
        file_extension = splitext(inter_filename)[-1]

        return f"{core_filename}_BROWSE{file_extension}"

    def _collect_dswx_product_metadata(self):
        """
        Gathers the available metadata from a sample output DSWx-HLS product for
        use in filling out the ISO metadata template for the DSWx-HLS PGE.

        Returns
        -------
        output_product_metadata : dict
            Dictionary containing DSWx-HLS output product metadata, formatted
            for use with the ISO metadata Jinja2 template.

        """
        # Find a single representative output DSWx-HLS product, they should all
        # have identical sets of metadata
        output_products = self.runconfig.get_output_product_filenames()
        representative_product = None

        for output_product in output_products:
            if basename(output_product) in self.renamed_files.values() and basename(output_product).endswith("tif"):
                representative_product = output_product
                break
        else:
            msg = (f"Could not find sample output product to derive metadata from "
                   f"within {self.runconfig.output_product_path}")
            self.logger.critical(self.name, ErrorCode.ISO_METADATA_RENDER_FAILED, msg)

        # Extract all metadata assigned by the SAS at product creation time
        output_product_metadata = get_geotiff_metadata(representative_product)

        # Get the Military Grid Reference System (MGRS) tile code and zone identifier
        # from the name of the input HLS dataset
        hls_fields = get_hls_filename_fields(
            get_geotiff_hls_dataset(representative_product)
        )
        mgrs_tile_id = hls_fields['tile_id']

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

        # Split the sensing time into the beginning/end portions
        sensing_time = output_product_metadata.pop('SENSING_TIME')

        # Sensing time can contain multiple times delimited by semicolon,
        # just take the first one
        if ';' in sensing_time:
            sensing_time = sensing_time.split(';', maxsplit=1)[0]

        # Certain datasets have been observed with multiple sensing times
        # concatenated by a plus sign, for this case just take the first of the
        # times
        if '+' in sensing_time:
            sensing_time = sensing_time.split('+', maxsplit=1)[0]

        # Set beginning and end time to single time parsed, since ISO metadata
        # requires both
        sensing_time_begin = sensing_time_end = sensing_time

        output_product_metadata['sensingTimeBegin'] = sensing_time_begin.strip()
        output_product_metadata['sensingTimeEnd'] = sensing_time_end.strip()

        # Add some fields on the dimensions of the data. These values should
        # be the same for all DSWx-HLS products, and were derived from the
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
        RunConfig, output product, or catalog metadata).

        Returns
        -------
        custom_data : dict
            Dictionary containing the custom metadata as expected by the ISO
            metadata Jinja2 template.

        """
        custom_metadata = {
            'ISO_OPERA_FilePackageName': self._core_filename(),
            'ISO_OPERA_ProducerGranuleId': self._core_filename(),
            'MetadataProviderAction': "creation",
            'GranuleFilename': self._core_filename(),
            'ISO_OPERA_ProjectKeywords': ['OPERA', 'JPL', 'DSWx', 'Dynamic', 'Surface', 'Water', 'Extent'],
            'ISO_OPERA_PlatformKeywords': ['HLS'],
            'ISO_OPERA_InstrumentKeywords': ['Landsat8', 'Sentinel 1 A/B']
        }

        return custom_metadata

    def _create_iso_metadata(self):
        """
        Creates a rendered version of the ISO metadata template for DSWx-HLS
        output products using metadata sourced from the following locations:

            * RunConfig (in dictionary form)
            * Output products (extracted from a sample product)
            * Catalog metadata
            * "Custom" metadata (all metadata not found anywhere else)

        Returns
        -------
        rendered_template : str
            The ISO metadata template for DSWx-HLS filled in with values from
            the sourced metadata dictionaries.

        """
        runconfig_dict = self.runconfig.asdict()

        product_output_dict = self._collect_dswx_product_metadata()

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
        Executes the post-processing steps for DSWx-HLS PGE job completion.

        The DSWxHLSPostProcessorMixin version of this function performs the same
        steps as the base PostProcessorMixin, but inserts an output file
        validation check and Landsat-9 metadata correction step prior to staging
        of the output files.

        Parameters
        ----------
        **kwargs : dict
            Any keyword arguments needed by the post-processor

        """
        print(f'Running postprocessor for {self._post_mixin_name}')

        self._run_sas_qa_executable()
        self._validate_output()
        self._correct_landsat_9_products()
        self._stage_output_files()


class DSWxHLSExecutor(DSWxHLSPreProcessorMixin, DSWxHLSPostProcessorMixin, PgeExecutor):
    """
    Main class for execution of a DSWx-HLS PGE, including the SAS layer.

    This class essentially rolls up the tailored pre- and post-processors
    while inheriting all other functionality from the base PgeExecutor class.

    """

    NAME = "DSWx"
    """Short name for the DSWx-HLS PGE"""

    LEVEL = "L3"
    """Processing Level for DSWx-HLS Products"""

    PGE_VERSION = "1.0.0-rc.7.0"
    """Version of the PGE (overrides default from base_pge)"""

    SAS_VERSION = "0.5.2"  # CalVal release 3.3 https://github.com/nasa/PROTEUS/releases/tag/v0.5.2
    """Version of the SAS wrapped by this PGE, should be updated as needed with new SAS deliveries"""

    def __init__(self, pge_name, runconfig_path, **kwargs):
        super().__init__(pge_name, runconfig_path, **kwargs)

        self.rename_by_pattern_map = OrderedDict(
            {
                # Note: ordering matters here!
                'dswx_hls_*BROWSE*': self._browse_image_filename,
                'dswx_hls_*.tif*': self._geotiff_filename
            }
        )
