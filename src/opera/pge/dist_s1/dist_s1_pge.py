#!/usr/bin/env python3

"""
==============
dist_s1_pge.py
==============
Module defining the implementation for the Surface Disturbance (DIST) from Sentinel-1 A/C (S1) PGE.

"""

import os
import re
import shutil
from datetime import datetime
from itertools import chain
from os.path import join, isdir, isfile, abspath, basename, splitext

from opera.pge.base.base_pge import PreProcessorMixin, PgeExecutor, PostProcessorMixin
from opera.util.dataset_utils import get_sensor_from_spacecraft_name
from opera.util.error_codes import ErrorCode
from opera.util.geo_utils import get_geographic_boundaries_from_mgrs_tile
from opera.util.input_validation import check_input_list
from opera.util.render_jinja2 import augment_measured_parameters, render_jinja2
from opera.util.run_utils import get_checksum
from opera.util.tiff_utils import get_geotiff_metadata
from opera.util.time import get_time_for_filename, get_iso_time


class DistS1PreProcessorMixin(PreProcessorMixin):
    """
    Mixin class responsible for handling all pre-processing steps for the DIST-S1
    PGE. The pre-processing phase is defined as all steps necessary prior
    to SAS execution.

    This particular pre-processor is currently a stub implementation, inheriting from the base pre-processor mixin
    and adding nothing at this time. New functionalities will be added as new versions of the DIST-S1 SAS are released.
    """

    _pre_mixin_name = "DistS1PreProcessorMixin"
    _valid_input_extensions = (".tif",)

    _rtc_pattern = re.compile(r'(?P<id>(?P<project>OPERA)_(?P<level>L2)_(?P<product_type>RTC)-(?P<source>S1)_'
                              r'(?P<burst_id>\w{4}-\w{6}-\w{3})_(?P<acquisition_ts>\d{8}T\d{6}Z)'
                              r'_(?P<creation_ts>\d{8}T\d{6}Z)_(?P<sensor>S1A|S1B|S1C)_(?P<spacing>30)_'
                              r'(?P<product_version>v\d+[.]\d+))(_(?P<pol>VV|VH|HH|HV|VV\+VH|HH\+HV))?'
                              r'[.](?P<ext>tif|tiff)$')

    def __validate_rtc_list_lengths(self, all_rtcs):
        """
        Validate that the pre_rtc_copol & pre_rtc_crosspol / post_rtc_copol &
        post_rtc_crosspol are the same lengths

        Parameters
        ----------
        all_rtcs : tuple(list(str), list(str), list(str), list(str))
            4-tuple of lists of input RTC filenames in the order: pre_rtc_copol, pre_rtc_crosspol, post_rtc_copol,
            post_rtc_crosspol
        """

        pre_rtc_copol, pre_rtc_crosspol, post_rtc_copol, post_rtc_crosspol = all_rtcs

        if len(pre_rtc_copol) != len(pre_rtc_crosspol) or len(post_rtc_copol) != len(post_rtc_crosspol):
            msg = (f'Lengths of input pre/post co/cross pol input RTC lists differ: pre {len(pre_rtc_copol)} '
                   f'{len(pre_rtc_crosspol)} post {len(post_rtc_copol)} {len(post_rtc_crosspol)}')
            self.logger.critical(
                self.name,
                ErrorCode.INVALID_INPUT,
                msg
            )

    def __validate_rtc_lists_are_pge_subset(self, all_rtcs):
        """
        Ensures all RTCs in the SAS group are also in the PGE group

        Parameters
        ----------
        all_rtcs : tuple(list(str), list(str), list(str), list(str))
            4-tuple of lists of input RTC filenames in the order: pre_rtc_copol, pre_rtc_crosspol, post_rtc_copol,
            post_rtc_crosspol
        """

        all_rtcs = chain.from_iterable(all_rtcs)

        if not set([basename(rtc) for rtc in all_rtcs]).issubset([basename(rtc) for rtc in self.runconfig.input_files]):
            msg = 'RunConfig SAS group RTC file lists do not make a subset of PGE group Input File list'
            self.logger.critical(
                self.name,
                ErrorCode.INVALID_INPUT,
                msg
            )

    def __validate_rtc_filenames(self, all_rtcs):
        """
        Validates that all input RTCs have the standard filename defined in the RTC product specification.

        See: https://www.jpl.nasa.gov/go/opera/products/rtc-product/

        Parameters
        ----------
        all_rtcs : tuple(list(str), list(str), list(str), list(str))
            4-tuple of lists of input RTC filenames in the order: pre_rtc_copol, pre_rtc_crosspol, post_rtc_copol,
            post_rtc_crosspol

        Returns
        -------
        rtc_matches: List of re.Match objects
            List of RTC filenames matched by a regular expression. Used in later validation. Only returns
            if this validation is passing.
        """

        rtc_matches = [self._rtc_pattern.match(basename(rtc)) for rtc in chain.from_iterable(all_rtcs)]
        mismatches = [rtc for match, rtc in zip(rtc_matches, chain.from_iterable(all_rtcs)) if match is None]

        if len(mismatches) > 0:
            msg = f'Invalid RTC filenames in RunConfig: {mismatches}'
            self.logger.critical(
                self.name,
                ErrorCode.INVALID_INPUT,
                msg
            )

        return rtc_matches

    def __validate_rtc_homogeneity(self, rtc_matches):
        """
        Validates all RTCs are from either Sentinel-1A or Sentinel-1C.

        Parameters
        ----------
        rtc_matches: List of re.Match objects
            List of RTC filenames matched by a regular expression.
        """
        if len(set([match.groupdict()['sensor'] for match in rtc_matches])) > 1:
            msg = 'RunConfig contains RTCs from more than one S1 Sensor. Inputs should be all from S1A or S1C'
            self.logger.critical(
                self.name,
                ErrorCode.INVALID_INPUT,
                msg
            )

    def __validate_rtc_ordering(self, all_rtcs):
        """
        Verifies the pre and post co- and cross-pol RTC lists are well-ordered.

        First, the lists are sorted by burst ID, then acquisition time. They are then
        checked so that each RTC in the copol lists have the same burst ID and acquisition
        time as the RTC in the same position in the corresponding crosspol list.

        Parameters
        ----------
        all_rtcs : tuple(list(str), list(str), list(str), list(str))
            4-tuple of lists of input RTC filenames in the order: pre_rtc_copol, pre_rtc_crosspol, post_rtc_copol,
            post_rtc_crosspol
        """
        def is_sorted(iterable, key=lambda x: x) -> bool:
            for i, e in enumerate(iterable[1:]):
                if key(e) < key(iterable[i]):
                    return False
            return True

        def sort_fn(path):
            match = self._rtc_pattern.match(os.path.basename(path))
            match_dict = match.groupdict()

            return match_dict['burst_id'], match_dict['acquisition_ts']

        def compare_rtc_dates_and_bursts(copol, crosspol):
            for copol_rtc, crosspol_rtc in zip(copol, crosspol):
                copol_rtc = self._rtc_pattern.match(os.path.basename(copol_rtc))
                crosspol_rtc = self._rtc_pattern.match(os.path.basename(crosspol_rtc))

                if copol_rtc.groupdict()['acquisition_ts'] != crosspol_rtc.groupdict()['acquisition_ts']:
                    return False
                if copol_rtc.groupdict()['burst_id'] != crosspol_rtc.groupdict()['burst_id']:
                    return False
            return True

        pre_rtc_copol, pre_rtc_crosspol, post_rtc_copol, post_rtc_crosspol = all_rtcs

        if not all([is_sorted(rtc_list, key=sort_fn) for rtc_list in (pre_rtc_copol, pre_rtc_crosspol,
                                                                      post_rtc_copol, post_rtc_crosspol)]):
            msg = 'One or more of the RunConfig SAS group RTC lists is badly ordered. Attempting to sort them'
            self.logger.warning(
                self.name,
                ErrorCode.LOGGED_WARNING_LINE,
                msg
            )

            pre_rtc_copol.sort(key=sort_fn)
            pre_rtc_crosspol.sort(key=sort_fn)
            post_rtc_copol.sort(key=sort_fn)
            post_rtc_crosspol.sort(key=sort_fn)

        if not compare_rtc_dates_and_bursts(pre_rtc_copol, pre_rtc_crosspol):
            msg = 'Date or burst ID mismatch in pre_rtc copol and crosspol lists'
            self.logger.critical(
                self.name,
                ErrorCode.INVALID_INPUT,
                msg
            )

        if not compare_rtc_dates_and_bursts(post_rtc_copol, post_rtc_crosspol):
            msg = 'Date or burst ID mismatch in post_rtc copol and crosspol lists'
            self.logger.critical(
                self.name,
                ErrorCode.INVALID_INPUT,
                msg
            )

    def __validate_co_and_cross_polarizations(self, all_rtcs):
        """
        Ensures the RTCs in the copol lists are co-polarized (VV or HH). Likewise,
        ensures the RTCs in the crosspol lists are cross-polarized (VH or HV).

        Parameters
        ----------
        all_rtcs : tuple(list(str), list(str), list(str), list(str))
            4-tuple of lists of input RTC filenames in the order: pre_rtc_copol, pre_rtc_crosspol, post_rtc_copol,
            post_rtc_crosspol
        """

        pre_rtc_copol, pre_rtc_crosspol, post_rtc_copol, post_rtc_crosspol = all_rtcs

        for rtc in pre_rtc_copol + post_rtc_copol:
            if self._rtc_pattern.match(os.path.basename(rtc)).groupdict()['pol'] not in ['VV', 'HH']:
                msg = f'Found non-copol RTC in copol input list: {os.path.basename(rtc)}'
                self.logger.critical(
                    self.name,
                    ErrorCode.INVALID_INPUT,
                    msg
                )

        for rtc in pre_rtc_crosspol + post_rtc_crosspol:
            if self._rtc_pattern.match(os.path.basename(rtc)).groupdict()['pol'] not in ['VH', 'HV']:
                msg = f'Found non-crosspol RTC in crosspol input list: {os.path.basename(rtc)}'
                self.logger.critical(
                    self.name,
                    ErrorCode.INVALID_INPUT,
                    msg
                )

    def _validate_rtcs(self):
        """
        Performs the following validations on the input RTCs:

        1. Verifies the co- and cross-pol RTC input lists are the same length
        2. Verifies the combined SAS RTC input lists are a subset of the PGE input list
        3. Verifies the input RTCs have standard filenames (important for later checks)
        4. Ensures input RTCs are not from a mixture of Sentinel-1A and Sentinel-1C
        5. Validates that the co- and cross-pol RTCs are in the same order (burst-ID &
           acquisition time)
        6. Validates no cross-pol RTCs are in copol input lists and vice-versa
        """

        sas_config = self.runconfig.sas_config

        pre_rtc_copol = sas_config["run_config"]["pre_rtc_copol"]
        pre_rtc_crosspol = sas_config["run_config"]["pre_rtc_crosspol"]
        post_rtc_copol = sas_config["run_config"]["post_rtc_copol"]
        post_rtc_crosspol = sas_config["run_config"]["post_rtc_crosspol"]

        all_rtcs = (pre_rtc_copol, pre_rtc_crosspol, post_rtc_copol, post_rtc_crosspol)

        self.__validate_rtc_list_lengths(all_rtcs)
        self.__validate_rtc_lists_are_pge_subset(all_rtcs)
        matches = self.__validate_rtc_filenames(all_rtcs)
        self.__validate_rtc_homogeneity(matches)
        self.__validate_rtc_ordering(all_rtcs)
        self.__validate_co_and_cross_polarizations(all_rtcs)

    def run_preprocessor(self, **kwargs):
        """
        Executes the pre-processing steps for DIST-S1 PGE initialization.
        The DistS1PreProcessorMixin version of this class performs all actions
        of the PreProcessorMixin class. Parameterization of the validation
        functions is handled via specialized class attributes (i.e. _valid_input_extensions)

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the pre-processor
        """
        super().run_preprocessor(**kwargs)

        check_input_list(
            self.runconfig.input_files,
            self.logger,
            self.name,
            valid_extensions=self._valid_input_extensions,
            check_zero_size=True
        )
        self._validate_rtcs()


class DistS1PostProcessorMixin(PostProcessorMixin):
    """
    Mixin class responsible for handling all post-processing steps for the DIST-S1
    PGE. The post-processing phase is defined as all steps required after SAS
    execution has completed, prior to handover of output products to PCM.

    This particular pre-processor is currently a stub implementation, inheriting from the base pre-processor mixin
    and adding nothing at this time. New functionalities will be added as new versions of the DIST-S1 SAS are released.
    """

    _post_mixin_name = "DistS1PostProcessorMixin"
    _cached_core_filename = None

    # May not need these since PGE produces 1 tile / execution
    _tile_metadata_cache = {}
    _tile_filename_cache = {}

    # These layers are always produced and therefore must be present
    _main_output_layer_names = ['DIST-GEN-STATUS-ACQ', 'DIST-GEN-STATUS', 'GEN-METRIC', 'BROWSE']

    # The production of these layers depends on the confirmation DB and may be absent
    _confirmation_db_output_layer_names = ['DATE-FIRST', 'DATE-LATEST', 'N-DIST', 'N-OBS']

    _valid_layer_names = _main_output_layer_names + _confirmation_db_output_layer_names

    _product_id_pattern = (r'(?P<id>(?P<project>OPERA)_(?P<level>L3)_(?P<product_type>DIST(-ALERT)?)-(?P<source>S1)_'
                           r'(?P<tile_id>T[^\W_]{5})_(?P<acquisition_ts>\d{8}T\d{6}Z)_(?P<creation_ts>\d{8}T\d{6}Z)_'
                           r'(?P<sensor>S1[AC]?)_(?P<spacing>30)_(?P<product_version>v\d+[.]\d+))')

    _granule_filename_pattern = (_product_id_pattern + rf'((_(?P<layer_name>{"|".join(_valid_layer_names)}))|'
                                                       r'_BROWSE)?[.](?P<ext>tif|tiff|png)$')

    _product_id_re = re.compile(_product_id_pattern + r'$')
    _granule_filename_re = re.compile(_granule_filename_pattern)

    def _validate_outputs(self):
        output_product_path = abspath(self.runconfig.output_product_path)
        output_products = []

        for file in os.listdir(output_product_path):
            dir_path = join(output_product_path, file)
            if isdir(dir_path) and self._product_id_re.match(file):
                bands = []
                generated_band_names = []

                for granule in os.listdir(dir_path):
                    granule_path = join(dir_path, granule)
                    if isfile(granule_path):
                        match_result = self._granule_filename_re.match(granule)

                        if match_result is None:  # or match_result.groupdict()['ext'] != 'tif':
                            error_msg = f'Invalid product filename {granule}'
                            self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

                        match_dict = match_result.groupdict()

                        if match_dict['layer_name'] is None and match_dict['ext'] == 'png':
                            match_dict['layer_name'] = 'BROWSE'

                        if os.stat(granule_path).st_size == 0:
                            error_msg = f'Output file {granule_path} is empty.'
                            self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)
                        elif match_dict['layer_name'] not in self._valid_layer_names:
                            error_msg = f'Invalid layer name "{match_dict["layer_name"]}" in output.'
                            self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

                        bands.append(granule_path)
                        generated_band_names.append(match_dict['layer_name'])

                        tile_id = match_dict['tile_id']
                        file_id = match_dict['id']

                        if tile_id not in self._tile_metadata_cache:
                            dist_metadata = self._collect_dist_s1_product_metadata(granule_path)
                            self._tile_metadata_cache[tile_id] = dist_metadata

                        if file_id not in self._tile_filename_cache:
                            self._tile_filename_cache[tile_id] = file_id

                # Not sure how I should do this validation... The bands in self._confirmation_db_output_layer_names
                # are only created if the confirmation db is available (& might still be missing on initial runs
                # with it available?)
                missing_main_output_bands = set(self._main_output_layer_names).difference(set(generated_band_names))

                if len(missing_main_output_bands) > 0:
                    error_msg = f'Some required output bands are missing: {list(missing_main_output_bands)}'
                    self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

                output_products.append(dir_path)

        if len(output_products) != 1:
            error_msg = f'Incorrect number of output granules generated: {len(output_products)}'
            self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

    def _ancillary_filename(self):
        """
        Helper method to derive the core component of the file names for the
        ancillary products associated to a PGE job (catalog metadata, log file,
        etc...).

        The core file name component for DIST-S1 ancillary products consists of:

        <PROJECT>_<LEVEL>_<PGE NAME>_<PROD TIMETAG>_<SENSOR>_<SPACING>_<PRODUCT VERSION>

        Since these files are not specific to any particular tile processed for
        a DIST-S1 job, fields such as tile ID and acquisition time are omitted from
        this file pattern.

        Also note that this does not include a file extension, which should be
        added to the return value of this method by any callers to distinguish
        the different formats of ancillary outputs produced by this PGE.

        Returns
        -------
        ancillary_filename : str
            The file name component to assign to ancillary products created by this PGE.
        """

        # TODO: Get this from metadata
        spacecraft_name = "SENTINEL-1A"
        sensor = get_sensor_from_spacecraft_name(spacecraft_name)
        pixel_spacing = "30"

        # TODO - for now, use the PGE production time, but ideally this should
        #        eventually match the production time assigned by the SAS, which
        #        should be present in the product metadata
        processing_time = get_time_for_filename(
            self.production_datetime
        )

        if not processing_time.endswith('Z'):
            processing_time = f'{processing_time}Z'

        product_version = str(self.runconfig.product_version)

        if not product_version.startswith('v'):
            product_version = f'v{product_version}'

        ancillary_filename = (f"{self.PROJECT}_{self.LEVEL}_{self.NAME}_{processing_time}_"
                              f"{sensor}_{pixel_spacing}_{product_version}")

        return ancillary_filename

    def _catalog_metadata_filename(self):
        """
        Returns the file name to use for Catalog Metadata produced by the DIST-S1 PGE.

        The Catalog Metadata file name for the DIST-S1 PGE consists of:

            <Ancillary filename>.catalog.json

        Where <Ancillary filename> is returned by DistS1PostProcessorMixin._ancillary_filename()

        Returns
        -------
        <catalog metadata filename> : str
            The file name to assign to the Catalog Metadata product created by this PGE.

        """
        return self._ancillary_filename() + ".catalog.json"

    def _log_filename(self):
        """
        Returns the file name to use for the PGE/SAS log file produced by the DIST-S1 PGE.

        The log file name for the DIST-S1 PGE consists of:

            <Ancillary filename>.log

        Where <Ancillary filename> is returned by DistS1PostProcessorMixin._ancillary_filename()

        Returns
        -------
        log_filename : str
            The file name to assign to the PGE/SAS log created by this PGE.

        """
        return self._ancillary_filename() + ".log"

    def _qa_log_filename(self):
        """
        Returns the file name to use for the Quality Assurance application log
        file produced by the DIST-S1 PGE.

        The log file name for the DIST-S1 PGE consists of:

            <Ancillary filename>.qa.log

        Where <Ancillary filename> is returned by DistS1PostProcessorMixin._ancillary_filename()

        Returns
        -------
        log_filename : str
            The file name to assign to the QA log created by this PGE.

        """
        return self._ancillary_filename() + ".qa.log"

    def _iso_metadata_filename(self):
        """
        Returns the file name to use for ISO Metadata produced by the DIST-S1 PGE.

        The ISO Metadata file name for the DIST-S1 PGE consists of:

            <DIST-S1 filename>.iso.xml

        Where <DIST-S1 filename> is:

        <PROJECT>_<LEVEL>_<PGE NAME>_<TILE ID>_<ACQ TIMESTAMP>_<PROD TIMETAG>_<SENSOR>_<SPACING>_<PRODUCT VERSION>

        Returns
        -------
        <iso metadata filename> : str
            The file name to assign to the ISO Metadata product created by this PGE.

        """
        # Since we only produce 1 tile each execution, we only have one tile ID in here
        tile_id = list(self._tile_filename_cache.keys())[0]

        iso_metadata_filename = self._tile_filename_cache[tile_id]

        return iso_metadata_filename + ".iso.xml"

    def _collect_dist_s1_product_metadata(self, geotiff_product):
        """
        Gathers the available metadata from an output DIST-S1 product for
        use in filling out the ISO metadata template for the DIST-S1 PGE.

        Parameters
        ----------
        geotiff_product : str
            Path the GeoTIFF product to collect metadata from.

        Returns
        -------
        output_product_metadata : dict
            Dictionary containing DIST-S1 output product metadata, formatted
            for use with the ISO metadata Jinja2 template.
        """
        output_product_metadata = dict()

        try:
            measured_parameters = get_geotiff_metadata(geotiff_product)
            output_product_metadata['MeasuredParameters'] = augment_measured_parameters(
                measured_parameters,
                self.runconfig.iso_measured_parameter_descriptions,
                self.logger
            )
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
        # be the same for all DIST-S1 products, and were derived from the
        # ADT product spec
        output_product_metadata['xCoordinates'] = {
            'size': 3600,  # pixels
            'spacing': 30  # meters/pixel
        }
        output_product_metadata['yCoordinates'] = {
            'size': 3600,  # pixels
            'spacing': 30  # meters/pixel
        }

        # TODO: Replace these with metadata values sourced from the granule when available
        #  (Or remove entirely if possible to refer to them straight through the MP dict)

        match_result = self._granule_filename_re.match(basename(geotiff_product))

        if match_result is None:
            # This really should not happen due to passing the _validate_outputs function but check anyway
            msg = f'Failed to parse DIST-S1 filename {basename(geotiff_product)}'
            self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, msg)

        match_result = match_result.groupdict()
        acq_time = match_result['acquisition_ts']
        acq_time = datetime.strptime(acq_time, '%Y%m%dT%H%M%SZ')

        output_product_metadata['acquisition_start_time'] = get_iso_time(acq_time)
        output_product_metadata['acquisition_end_time'] = get_iso_time(acq_time)

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
            'ISO_OPERA_ProjectKeywords': ['OPERA', 'JPL', 'DIST', 'Surface', 'Disturbance'],
            'ISO_OPERA_PlatformKeywords': ['S1'],
            'ISO_OPERA_InstrumentKeywords': ['Sentinel 1 A/C']
        }

        return custom_metadata

    def _create_iso_metadata(self):
        """
        Creates a rendered version of the ISO metadata template for DIST-S1
        output products using metadata from the following locations:

            * RunConfig (in dictionary form)
            * Output product (dictionary extracted from HDF5 product, per-tile)
            * Catalog metadata
            * "Custom" metadata (all metadata not found anywhere else)

        Returns
        -------
        rendered_template : str
            The ISO metadata template for DSWX-S1 filled in with values from
            the sourced metadata dictionaries.

        """
        # Use the base PGE implemenation to validate existence of the template
        super()._create_iso_metadata()

        # Since we only produce 1 tile each execution, we only have one tile ID in here
        tile_id = list(self._tile_metadata_cache.keys())[0]

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

        rendered_template = render_jinja2(iso_template_path, iso_metadata, self.logger)

        return rendered_template

    def _flatten_output_dir(self):
        """
        Flattens the output directory since PCM expects all output files
        to be in the output root.
        """
        output_product_path = abspath(self.runconfig.output_product_path)
        scratch_path = abspath(self.runconfig.scratch_path)

        for dirpath, dirnames, filenames in os.walk(output_product_path):
            for filename in filenames:
                src = os.path.join(dirpath, filename)
                dst = os.path.join(output_product_path, basename(filename))

                if scratch_path not in src and src != dst:
                    # TODO: Change this to shutil.move() with the next SAS delivery. We need the output directory
                    #  structure intact for the comparison script since it works on the whole directory
                    shutil.copy(str(src), dst)

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

    def run_postprocessor(self, **kwargs):
        """
        Executes the post-processing steps for the DIST-S1 PGE.
        The DistS1PostProcessorMixin version of this method currently
        validates the output product files and performs other base
        postprocessing steps (writing log file, etc).

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the post-processor
        """

        print(f'Running postprocessor for {self._post_mixin_name}')

        self._validate_outputs()
        self._flatten_output_dir()
        self._run_sas_qa_executable()
        self._stage_output_files()


class DistS1Executor(DistS1PreProcessorMixin, DistS1PostProcessorMixin, PgeExecutor):
    """
    Main class for execution of the DIST-S1 PGE, including the SAS layer.
    This class essentially rolls up the DIST-specific pre- and post-processor
    functionality, while inheriting all other functionality for setup and execution
    of the SAS from the base PgeExecutor class.
    """

    NAME = "DIST-S1"
    """Short name for the DIST-S1 PGE"""

    LEVEL = "L3"
    """Processing Level for DIST-S1 Products"""

    SAS_VERSION = "0.0.6"  # Beta release https://github.com/opera-adt/dist-s1/releases/tag/v0.0.3
    """Version of the SAS wrapped by this PGE, should be updated as needed"""

    def __init__(self, pge_name, runconfig_path, **kwargs):
        super().__init__(pge_name, runconfig_path, **kwargs)

        self.rename_by_pattern_map = {}
