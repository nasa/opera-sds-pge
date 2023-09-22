#!/usr/bin/env python3

"""
==============
disp_s1_pge.py
==============
Module defining the implementation for the Land-Surface Displacement (DISP) product
from Sentinel-1 A/B (S1-A/B) data.
"""

import glob
import os.path
import re
from collections import OrderedDict
from os import listdir
from os.path import abspath, basename, exists, getsize, join, splitext

from opera.pge.base.base_pge import PgeExecutor
from opera.pge.base.base_pge import PostProcessorMixin
from opera.pge.base.base_pge import PreProcessorMixin
from opera.util.error_codes import ErrorCode
from opera.util.input_validation import validate_algorithm_parameters_config, validate_disp_inputs
from opera.util.metadata_utils import get_disp_s1_product_metadata
from opera.util.time import get_time_for_filename
from opera.util.render_jinja2 import render_jinja2


class DispS1PreProcessorMixin(PreProcessorMixin):
    """
    Mixin class responsible for handling all pre-processing steps for the DISP-S1
    PGE. The pre-processing phase is defined as all steps necessary prior
    to SAS execution.

    In addition to the base functionality inherited from PreProcessorMixin, this
    mixin adds an input validation step to ensure that input(s) defined by the
    RunConfig exist and are valid.

    """

    _pre_mixin_name = "DispS1PreProcessorMixin"

    def run_preprocessor(self, **kwargs):
        """
        Executes the pre-processing steps for DISP-S1 PGE initialization.
        The DispS1PreProcessorMixin version of this class performs all actions
        of the base PreProcessorMixin class, and adds an input validation step for
        the inputs defined within the RunConfig (TODO).

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the pre-processor

        """
        super().run_preprocessor(**kwargs)

        validate_disp_inputs(self.runconfig, self.logger, self.name)

        self.algorithm_parameters_runconfig = self.runconfig.algorithm_parameters_file_config_path
        validate_algorithm_parameters_config(self.name,
                                             self.runconfig.algorithm_parameters_schema_path,
                                             self.runconfig.algorithm_parameters_file_config_path,
                                             self.logger)


class DispS1PostProcessorMixin(PostProcessorMixin):
    """
    Mixin class responsible for handling all post-processing steps for the DISP-S1
    PGE. The post-processing phase is defined as all steps required after SAS
    execution has completed, prior to handover of output products to PCM.

    In addition to the base functionality inherited from PostProcessorMixin, this
    mixin adds an output validation step to ensure that the output file(s) defined
    by the RunConfig exist and are valid.

    """

    _post_mixin_name = "DispS1PostProcessorMixin"
    _cached_core_filename = None

    def _validate_output(self):
        """
        Evaluates the output files generated from SAS execution to ensure:
            - That one expected .nc file exists in the output directory designated
              by the RunConfig and is non-zero in size
            - A .png file corresponding to the expected output .nc product exists
              alongside and is non-zero in size (TODO)
            - If the SAS runconfig has the product_path_group.save_compressed_slc
              flag set to True, validate that a "compressed_slcs" directory
              exists within the designated output directory, and that it is not
              empty
            - For each file within "compressed_slcs", ensure the file is non-zero
              in size
        """
        output_dir = abspath(self.runconfig.output_product_path)

        # Validate .nc product file
        nc_files = glob.glob(join(output_dir, '*.nc'))

        if len(nc_files) != 1:
            if len(nc_files) == 0:
                error_msg = "The SAS did not create an output file with the expected '.nc' extension"
            elif len(nc_files) > 1:
                error_msg = f"The SAS created too many files with the expected '.nc' extension: {nc_files}"

            self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

        nc_file = nc_files[0]
        if not getsize(nc_file):
            error_msg = f"SAS output file {basename(nc_file)} exists, but is empty"

            self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

        # Validate .png file
        nc_file_no_ext, ext = splitext(basename(nc_file))
        png_file = join(output_dir, f'{nc_file_no_ext}.png')
        if not exists(png_file):
            error_msg = f"SAS output file {basename(png_file)} does not exist"

            self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)
        elif not getsize(png_file):
            error_msg = f"SAS output file {basename(png_file)} exists but is empty"

            self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

        save_compressed_slc = self.runconfig.sas_config['product_path_group']['save_compressed_slc']
        if save_compressed_slc:
            # Validate compressed_slcs directory
            comp_dir = join(output_dir, 'compressed_slcs')
            if not exists(comp_dir):
                error_msg = f"SAS output directory '{basename(comp_dir)}' does not exist"

                self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

            comp_dir_list = listdir(comp_dir)
            if len(comp_dir_list) == 0:
                error_msg = f"SAS output directory '{basename(comp_dir)}' exists but is empty"

                self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

            # Validate each file in compressed_slcs directory
            for f in comp_dir_list:
                if not getsize(join(comp_dir, f)):
                    error_msg = f"SAS compressed_slcs file '{basename(f)}' exists but is empty"

                    self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

    def _core_filename(self, inter_filename=None):
        """
        Returns the core file name component for products produced by the
        DISP-S1 PGE.

        The core file name component of the DISP-S1 PGE consists of:

        <PROJECT>_<LEVEL>_<PGE NAME>_<Mode>_<FrameID>_<Polarization>_\
        <ReferenceDateTime>_<SecondaryDateTime>_<ProductVersion>_\
        <ProductGenerationDateTime>

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
            The filename component to assign to frame-based products created by
            this PGE.
        """
        # Check if the core filename has already been generated and cached,
        # and return it if so
        if self._cached_core_filename is not None:
            return self._cached_core_filename

        core_filename = (
            f"{self.PROJECT}_{self.LEVEL}_{self.NAME}"
        )

        disp_metadata = self._collect_disp_s1_product_metadata()

        # Mode: S1-A/B acquisition mode, should be fixed to "IW"
        mode = "IW"

        # FrameID: Unique frame identification number as a 5-digit string in
        # the format FXXXXX
        frame_id = f"F{disp_metadata['identification']['frame_id']:05d}"

        # Polarization:  polarization of the input bursts
        # derived from names of input CSLCs in the runconfig
        cslc_file_list = self.runconfig.sas_config['input_file_group']['cslc_file_list']

        ps = r"t\w{3}_\d{6}_iw[1|2|3]_[0-9]{8}_(?P<polarization>VV|VH|HH|HV|VV\+VH|HH\+HV).h5"
        pattern = re.compile(ps)
        for cslc_file in cslc_file_list:
            cslc_file_basename = basename(cslc_file)
            result = pattern.match(cslc_file_basename)
            if result:
                polarization = result.groupdict()['polarization']
                break
        else:
            raise RuntimeError(
                'No cslc_file_list file matches the expected naming pattern to '
                'retrieve the polarization information.'
            )

        # ReferenceDateTime: The acquisition sensing start date and time of
        # the input satellite imagery for the first burst in the frame of the
        # reference product in the format YYYYMMDDTHHMMSSZ
        reference_date_time = disp_metadata['identification']['reference_datetime']

        # SecondaryDateTime: The acquisition sensing start date and time of
        # the input satellite imagery for the first burst in the frame of this
        # secondary product in the format YYYYMMDDTHHMMSSZ
        secondary_date_time = disp_metadata['identification']['secondary_datetime']

        # ProductVersion: OPERA DISP-S1 product version number with four
        # characters, including the letter “v” and two digits indicating the
        # major and minor versions, which are delimited by a period
        product_version = f"v{disp_metadata['identification']['product_version']}"

        # ProductGenerationDateTime: The date and time at which the product
        # was generated by OPERA with the format of YYYYMMDDTHHMMSSZ
        product_generation_date_time = f"{get_time_for_filename(self.production_datetime)}Z"

        # Assign the core file name to the cached class attribute
        self._cached_core_filename = (
            f"{core_filename}_{mode}_{frame_id}_{polarization}_"
            f"{reference_date_time}_{secondary_date_time}_{product_version}_"
            f"{product_generation_date_time}"
        )

        return self._cached_core_filename

    def _browse_filename(self, inter_filename):
        """
        Returns the file name to use for the PNG browse image produced by
        the DISP-S1 PGE.

        The browse image filename for the DISP-S1 PGE consists of:

            <Core filename>.png

        Where <Core filename> is returned by DispS1PostProcessorMixin._core_filename()

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the output browse image to generate a
            filename for. This parameter may be used to inspect the file in order
            to derive any necessary components of the returned filename.

        Returns
        -------
        browse_image_filename : str
            The file name to assign to browse image created by this PGE.

        """
        browse_image_filename = f"{self._core_filename(inter_filename)}.png"

        return browse_image_filename

    def _netcdf_filename(self, inter_filename):
        """
        Returns the file name to use for netCDF files produced by the DISP-S1 PGE.

        The netCDF filename for the DISP-S1 PGE consists of:

            <Core filename>.nc

        Where <Core filename> is returned by DispS1PostProcessorMixin._core_filename().

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the output netCDF to generate
            a filename for. This parameter may be used to inspect the file
            in order to derive any necessary components of the returned filename.

        Returns
        -------
        netcdf_filename : str
            The file name to assign to netCDF product(s) created by this PGE.

        """
        netcdf_filename = f"{self._core_filename(inter_filename)}.nc"

        return netcdf_filename

    def _collect_disp_s1_product_metadata(self):
        """
        Gathers the available metadata from a sample output DISP-S1 product for
        use in filling out the ISO metadata template for the DISP-S1 PGE.

        Returns
        -------
        output_product_metadata : dict
            Dictionary containing DISP-S1 output product metadata, formatted
            for use with the ISO metadata Jinja2 template.

        """
        # Find a single representative output DISP-S1 product, they should all
        # have identical sets of metadata
        output_products = self.runconfig.get_output_product_filenames()
        representative_product = None

        for output_product in output_products:
            if basename(output_product).endswith(".nc"):
                representative_product = output_product
                break
        else:
            msg = (f"Could not find sample output product to derive metadata from "
                   f"within {self.runconfig.output_product_path}")
            self.logger.critical(self.name, ErrorCode.ISO_METADATA_RENDER_FAILED, msg)

        # Extract all metadata assigned by the SAS at product creation time
        output_product_metadata = get_disp_s1_product_metadata(representative_product)

        # TODO: temporary fields, remove once available from product metadata
        # "identification/reference_datetime" is missing from
        # the current delivery. We should assign a placeholder datetime in
        # the meantime
        output_product_metadata['identification']['reference_datetime'] = "20230101T000000Z"

        # "identification/secondary_datetime" is missing from
        # the current delivery. We should assign a placeholder datetime in
        # the meantime
        output_product_metadata['identification']['secondary_datetime'] = "20230101T000000Z"

        output_product_metadata['geospatial_lon_min'] = 10.0
        output_product_metadata['geospatial_lon_max'] = 20.0
        output_product_metadata['geospatial_lat_min'] = 10.0
        output_product_metadata['geospatial_lat_max'] = 30.0

        output_product_metadata['polarization'] = 'VV'
        # TODO: end temporary fields

        # Add some fields on the dimensions of the data.
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
            'ISO_OPERA_ProjectKeywords': ['OPERA', 'JPL', 'DISP', 'Displacement', 'Surface', 'Land', 'Global'],
            'ISO_OPERA_PlatformKeywords': ['S1'],
            'ISO_OPERA_InstrumentKeywords': ['Sentinel 1 A/B']
        }

        return custom_metadata

    def _create_iso_metadata(self):
        """
        Creates a rendered version of the ISO metadata template for DISP-S1
        output products using metadata sourced from the following locations:

            * RunConfig (in dictionary form)
            * Output products (extracted from a sample product)
            * Catalog metadata
            * "Custom" metadata (all metadata not found anywhere else)

        Returns
        -------
        rendered_template : str
            The ISO metadata template for DISP-S1 filled in with values from
            the sourced metadata dictionaries.

        """
        runconfig_dict = self.runconfig.asdict()

        product_output_dict = self._collect_disp_s1_product_metadata()

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
        Executes the post-processing steps for the DISP-S1 PGE.
        The DispS1PostProcessorMixin version of this method performs the same
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


class DispS1Executor(DispS1PreProcessorMixin, DispS1PostProcessorMixin, PgeExecutor):
    """
    Main class for execution of the DISP-S1 PGE, including the SAS layer.
    This class essentially rolls up the DISP-specific pre- and post-processor
    functionality, while inheriting all other functionality for setup and execution
    of the SAS from the base PgeExecutor class.

    """

    NAME = "DISP-S1"
    """Short name for the DISP-S1 PGE"""

    LEVEL = "L3"
    """Processing Level for DISP-S1 Products"""

    SAS_VERSION = "0.1"
    """Version of the SAS wrapped by this PGE, should be updated as needed"""

    def __init__(self, pge_name, runconfig_path, **kwargs):
        super().__init__(pge_name, runconfig_path, **kwargs)

        self.rename_by_pattern_map = OrderedDict(
            {
                # Note: ordering matters here!
                '*.nc': self._netcdf_filename,
                '*.png': self._browse_filename
            }
        )
