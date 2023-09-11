#!/usr/bin/env python3

"""
==============
disp_s1_pge.py
==============
Module defining the implementation for the Land-Surface Displacement (DISP) product
from Sentinel-1 A/B (S1-A/B) data.
"""

import glob
from os import listdir
from os.path import abspath, basename, exists, getsize, join, splitext
import re

from opera.pge.base.base_pge import PgeExecutor
from opera.pge.base.base_pge import PostProcessorMixin
from opera.pge.base.base_pge import PreProcessorMixin
from opera.util.error_codes import ErrorCode
from opera.util.input_validation import validate_algorithm_parameters_config, validate_disp_inputs
from opera.util.metadata_utils import get_disp_s1_product_metadata
from opera.util.time import get_time_for_filename


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
        The DswxS1PreProcessorMixin version of this class performs all actions
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


    def _frame_filename(self, inter_filename=None):
        """
        Returns the file name to use for frame-based DISP products produced
        by this PGE.

        The filename for the DISP-S1 frame products consists of:

        <CoreFilename>_<Mode>-<FrameID>_<Polarization>_<ReferenceDateTime>_<SecondaryDateTime>_<ProductVersion>_<ProductGenerationDateTime>

        Where <CoreFilename> is returned by DispS1PostProcessorMixin._core_filename()

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
        frame_filename : str
            The filename component to assign to frame-based products created by
            this PGE.
        """
        core_filename = self._core_filename(inter_filename)

        disp_metadata = self._collect_disp_s1_product_metadata(inter_filename)

        # Mode: S1-A/B acquisition mode, should be fixed to "IW"
        mode = "IW"

        # FrameID: Unique frame identification number as a 5-digit string in
        # the format FXXXXX
        frame_id = f"F{disp_metadata['identification']['frame_id']:05d}"

        # Polarization:  polarization of the input bursts
        # derived from names of input CSLCs in the runconfig
        cslc_file_list = self.runconfig.sas_config['input_file_group']['cslc_file_list']
        pattern = re.compile(r"t[0-9]{3}_[0-9]{6}_iw2_[0-9]{8}_(VV|VH).h5")
        for cslc_file in cslc_file_list:
            cslc_file_basename = basename(cslc_file)
            if pattern.match(cslc_file_basename):
                polarization = cslc_file_basename.split('_')[-1].split('.')[0]
                break
        else:
            raise RuntimeError(
                'No cslc_file_list file matches the expected naming pattern to '
                'retrieve the polarization information.'
            )

        # ReferenceDateTime: The acquisition sensing start date and time of
        # the input satellite imagery for the first burst in the frame of the
        # reference product in the format YYYYMMDDTHHMMSSZ
        # TODO This should come from the product metadata under
        # "identification/reference_datetime", however, it is missing from
        # the current delivery. We should assign a placeholder datetime in
        # the meantime
        reference_date_time = "YYYYMMDDTHHMMSSZ"

        # SecondaryDateTime: The acquisition sensing start date and time of
        # the input satellite imagery for the first burst in the frame of this
        # secondary product in the format YYYYMMDDTHHMMSSZ
        # TODO This should come from the product metadata
        secondary_date_time = "YYYYMMDDTHHMMSSZ"

        # ProductVersion: OPERA DISP-S1 product version number with four
        # characters, including the letter “v” and two digits indicating the
        # major and minor versions, which are delimited by a period
        product_version = f"v{disp_metadata['identification']['product_version']}"


        # ProductGenerationDateTime: The date and time at which the product
        # was generated by OPERA with the format of YYYYMMDDTHHMMSSZ
        product_generation_date_time = f"{get_time_for_filename(self.production_datetime)}Z"

        frame_filename = (
            f"{core_filename}_{mode}_{frame_id}_{polarization}_"
            f"{reference_date_time}_{secondary_date_time}_{product_version}_"
            f"{product_generation_date_time}"
        )

        return frame_filename


    def _netcdf_filename(self, inter_filename):
        """
        Returns the file name to use for netCDF files produced by the DISP-S1 PGE.

        The netCDF filename for the DISP-S1 PGE consists of:

            <FrameFilename>.nc

        Where <FrameFilename> is returned by DispS1PostProcessorMixin._frame_filename().

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
        frame_filename = self._frame_filename(inter_filename)

        return f"{frame_filename}.nc"


    def _collect_disp_s1_product_metadata(self, netcdf_product):
        """
        Gathers the available metadata from an output DISP-S1 product for
        use in filling out the ISO metadata template for the DISP-S1 PGE.

        Parameters
        ----------
        netcdf_product : str
            Path to the netcdf product to collect metadata from.

        Returns
        -------
        output_product_metadata : dict
            Dictionary containing DISP-S1 output product metadata, formatted
            for use with the ISO metadata Jinja2 template.

        """
        # Extract all metadata assigned by the SAS at product creation time
        output_product_metadata = get_disp_s1_product_metadata(netcdf_product)

        return output_product_metadata


    def run_postprocessor(self, **kwargs):
        """
        Executes the post-processing steps for the DISP-S1 PGE.
        The DispS1PostProcessorMixin version of this method performs the same
        steps as the base PostProcessorMixin, but inserts a step to perform
        output product validation prior to staging and renaming of the output
        files (TODO).

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

    NAME = "DISP"
    """Short name for the DISP-S1 PGE"""

    LEVEL = "L3"
    """Processing Level for DISP-S1 Products"""

    SAS_VERSION = "0.1"
    """Version of the SAS wrapped by this PGE, should be updated as needed"""

    def __init__(self, pge_name, runconfig_path, **kwargs):
        super().__init__(pge_name, runconfig_path, **kwargs)

        self.rename_by_pattern_map = {}
