#!/usr/bin/env python3

"""
===============
cal_disp_pge.py
===============
Module defining the implementation of the Calibration for Surface Displacement from Sentinel-1 and NISAR (CAL-DISP) PGE.
"""

import re
from os.path import abspath, basename, getsize, splitext

from opera.pge.base.base_pge import PgeExecutor, PostProcessorMixin, PreProcessorMixin
from opera.util.dataset_utils import parse_bounding_polygon_from_wkt
from opera.util.error_codes import ErrorCode
from opera.util.h5_utils import get_cal_disp_product_metadata
from opera.util.input_validation import validate_algorithm_parameters_config, validate_cal_inputs
from opera.util.render_jinja2 import augment_hdf5_measured_parameters, render_jinja2
from opera.util.run_utils import get_checksum
from opera.util.time import get_catalog_metadata_datetime_str


class CalDispPreProcessorMixin(PreProcessorMixin):
    """
    Mixin class responsible for handling all pre-processing steps for the CAL-DISP
    PGE. The pre-processing phase is defined as all steps necessary prior
    to SAS execution.

    In addition to the base functionality inherited from PreProcessorMixin, this
    mixin adds an input validation step to ensure that input(s) defined by the
    RunConfig exist and are valid.
    """

    _pre_mixin_name = "CalDispPreProcessorMixin"
    _valid_input_extensions = (".nc",)

    def run_preprocessor(self, **kwargs):
        """
        Executes the pre-processing steps for CAL-DISP PGE initialization.
        The CalDispPreProcessorMixin version of this class performs all actions
        of the PreProcessorMixin class. Parameterization of the validation
        functions is handled via specialized class attributes (i.e. _valid_input_extensions)

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the pre-processor
        """
        super().run_preprocessor(**kwargs)

        validate_cal_inputs(self.runconfig, self.logger, self.name)
        validate_algorithm_parameters_config(self.name,
                                             self.runconfig.algorithm_parameters_schema_path,
                                             self.runconfig.algorithm_parameters_file_config_path,
                                             self.logger)

class CalDispPostProcessorMixin(PostProcessorMixin):
    """
    Mixin class responsible for handling all post-processing steps for the CAL-DISP
    PGE. The post-processing phase is defined as all steps required after SAS
    execution has completed, prior to handover of output products to PCM.

    This particular pre-processor is currently a stub implementation, inheriting from the base pre-processor mixin
    and adding nothing at this time. New functionalities will be added as new versions of the CAL-DISP SAS are released.
    """

    _post_mixin_name = "CalDispPostProcessorMixin"

    _expected_extensions = ('.nc', '.png')
    _cached_core_filename = None
    _cached_product_metadata = None

    def _validate_outputs(self):
        output_product_files = self.runconfig.get_output_product_filenames()

        # Confirm one and only one of each expected output type
        for filename_ext in self._expected_extensions:
            gen = (f for f in output_product_files if splitext(f)[1] == filename_ext)
            try:
                output_filepath = next(gen)
            except StopIteration:
                error_msg = f"Could not locate {filename_ext} file."
                self.logger.critical(self.name, ErrorCode.OUTPUT_NOT_FOUND, error_msg)

            # Check for second file, if found raise error
            try:
                next(gen)
                error_msg = f"Found incorrect number of {filename_ext} files."
                self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)
            except StopIteration:
                pass

            output_filename = basename(output_filepath)

            # Check file size
            file_size = getsize(output_filepath)
            if not file_size > 0:
                error_msg = (f"Output file {output_filename} size is {file_size}. "
                             "Size must be greater than 0.")
                self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

            # Check filename matches expected pattern
            match = self._granule_filename_re.match(output_filename)
            if not bool(match):
                error_msg = f'Invalid product filename {output_filename}'
                self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)
            else:
                # Cache the core filename for later use
                self._cached_core_filename = match.groupdict()['id']

            if filename_ext == '.nc':
                self._cached_product_metadata = self._collect_cal_disp_product_metadata(output_filepath)

    def _core_filename(self, inter_filename=None):  # pylint: disable=unused-argument
        """
        Returns the core file name component for products produced by the
        CAL-DISP PGE. This is also the ancillary core filename.

        The core file name component of the CAL-DISP PGE consists of:

            <PROJECT>_<LEVEL>_<PGE NAME>_<PLATFORM>_<MODE>_<FRAME_ID>_
            <POL>_<REF_DT>_<SEC_DT>_<PRODUCT VERSION>_<PROC_DT>

        Notes
        -----
        The core filename is derived from the output product file name assigned
        by the CAL-DISP SAS. During output product validation, this PGE caches
        the core filename in the _cached_core_filename attribute, so this
        method should only be called after the outputs have been validated.

        Parameters
        ----------
        inter_filename : str, optional
            The intermediate filename of the output product to generate the
            core filename for. Currenly unused by this method.

        Returns
        -------
        core_filename : str
            The core file name component to assign to products created by this PGE.

        """
        # _validate_outputs() should have been called prior to this method to
        # set _cached_core_filename
        return self._cached_core_filename

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
        filtered_output_products = filter(
            lambda product: splitext(product)[-1] in self._expected_extensions,
            output_products
        )

        # Generate checksums on the filtered product list
        checksums = {
            basename(output_product): get_checksum(output_product)
            for output_product in filtered_output_products
        }

        return checksums

    def _collect_cal_disp_product_metadata(self, cal_disp_product):
        """
        Gathers the available metadata from a sample output CAL-DISP product for
        use in filling out the ISO metadata template for the CAL-DISP PGE.

        Parameters
        ----------
        disp_product : str
            Path to the CAL-DISP NetCDF product to collect metadata from.

        Returns
        -------
        output_product_metadata : dict
            Dictionary containing CAL-DISP output product metadata, formatted
            for use with the ISO metadata Jinja2 template.

        """
        # Extract all metadata assigned by the SAS at product creation time
        try:
            output_product_metadata = get_cal_disp_product_metadata(cal_disp_product)

            if output_product_metadata['metadata']['platform_id'].startswith('S1'):
                product_source = 'Sentinel-1'
            else:
                product_source = 'NISAR'

            # Add hardcoded values to metadata
            output_product_metadata['static'] = {
                'Project': 'OPERA',
                'ProductLevel': 4,
                'ProductType': 'CAL-DISP',
                'ProductSource': product_source,
                'ProcessingDateTime': get_catalog_metadata_datetime_str(self.production_datetime)
            }

            output_product_metadata['MeasuredParameters'] = augment_hdf5_measured_parameters(
                output_product_metadata,
                self.runconfig.iso_measured_parameter_descriptions,
                self.logger
            )
        except Exception as err:
            msg = f'Failed to extract metadata from {cal_disp_product}, reason: {err}'
            self.logger.critical(self.name, ErrorCode.ISO_METADATA_COULD_NOT_EXTRACT_METADATA, msg)

        # Parse the image polygon coordinates to conform with gml
        bounding_polygon_wkt_str = output_product_metadata['identification']['bounding_polygon']

        try:
            bounding_polygon_gml_str = parse_bounding_polygon_from_wkt(bounding_polygon_wkt_str)
            output_product_metadata['bounding_polygon'] = bounding_polygon_gml_str
        except ValueError as err:
            self.logger.critical(self.name, ErrorCode.ISO_METADATA_RENDER_FAILED, str(err))

        # Add some fields on the dimensions of the data.
        output_product_metadata['xCoordinates'] = {
            'size': len(output_product_metadata['x']),  # pixels
            'spacing': 30  # meters/pixel
        }
        output_product_metadata['yCoordinates'] = {
            'size': len(output_product_metadata['y']),  # pixels
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
            'ISO_OPERA_ProjectKeywords': ['OPERA', 'JPL', 'DISP', 'Displacement',
                                          'Surface', 'Land', 'Global', 'Calibration'],
            'ISO_OPERA_PlatformKeywords': ['S1', 'NI'],
            'ISO_OPERA_InstrumentKeywords': ['Sentinel 1 A', 'Sentinel 1 B', 'Sentinel 1 C', 'Sentinel 1 D', 'NISAR']
        }

        return custom_metadata

    def _create_iso_metadata(self):
        """
        Creates a rendered version of the ISO metadata template for CAL-DISP
        output products using metadata sourced from the following locations:

            * RunConfig (in dictionary form)
            * Output products (extracted from a sample product)
            * Catalog metadata
            * "Custom" metadata (all metadata not found anywhere else)

        Returns
        -------
        rendered_template : str
            The ISO metadata template for CAL-DISP filled in with values from
            the sourced metadata dictionaries.

        """
        # Use the base PGE implemenation to validate existence of the template
        super()._create_iso_metadata()

        runconfig_dict = self.runconfig.asdict()
        product_output_dict = self._cached_product_metadata
        catalog_metadata_dict = self._create_catalog_metadata().asdict()
        custom_data_dict = self._create_custom_metadata()

        iso_metadata = {
            'run_config': runconfig_dict,
            'product_output': product_output_dict,
            'catalog_metadata': catalog_metadata_dict,
            'custom_data': custom_data_dict
        }

        iso_template_path = abspath(self.runconfig.iso_template_path)

        rendered_template = render_jinja2(
            iso_template_path,
            iso_metadata,
            self.logger,
            self.runconfig.output_product_path
        )

        return rendered_template

    def run_postprocessor(self, **kwargs):
        """
        Executes the post-processing steps for the CAL-DISP PGE.
        The CalDispPostProcessorMixin version of this method currently
        validates the output product files and performs the same
        steps as the base PostProcessorMixin, but inserts a step to perform
        output product validation prior to staging and renaming of the output
        files.

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the post-processor
        """
        self._validate_outputs()

        super().run_postprocessor(**kwargs)


class CalDispExecutor(CalDispPreProcessorMixin, CalDispPostProcessorMixin, PgeExecutor):
    """
    Main class for execution of the CAL-DISP PGE, including the SAS layer.
    This class essentially rolls up the CAL-DISP-specific pre- and post-processor
    functionality, while inheriting all other functionality for setup and execution
    of the SAS from the base PgeExecutor class.
    """

    _granule_filename_re = re.compile(r"(?P<id>(?P<project>OPERA)_(?P<level>L4)_(?P<product_type>CAL-DISP)-"
                                      r"(?P<platform>S1|NI)_(?P<mode>IW|20|40|77|05)_(?P<frame_id>F\d{5})_"
                                      r"(?P<pol>[HV]{2})_(?P<reference_ts>\d{8}T\d{6}Z)_(?P<secondary_ts>\d{8}T\d{6}Z)_"
                                      r"(?P<product_version>v\d[.]\d)_(?P<creation_ts>\d{8}T\d{6}Z))[.](?P<ext>nc|png)")

    NAME = "CAL-DISP"
    """Short name for the CAL-DISP PGE"""

    LEVEL = "L4"
    """Processing Level for CAL-DISP Products"""

    SAS_VERSION = "0.1"  # Interface release https://github.com/opera-adt/cal-disp/releases/tag/v0.1
    """Version of the SAS wrapped by this PGE, should be updated as needed"""

    def __init__(self, pge_name, runconfig_path, **kwargs):
        super().__init__(pge_name, runconfig_path, **kwargs)

        self.rename_by_pattern_map = {}
