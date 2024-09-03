#!/usr/bin/env python3

"""
==============
disp_s1_pge.py
==============

Module defining the implementation for the Land-Surface Displacement (DISP) product
from Sentinel-1 A/B (S1-A/B) data.

"""
import datetime
import glob
import os.path
import re
import subprocess
from collections import OrderedDict
from os import listdir
from os.path import abspath, basename, exists, getsize, join, splitext

from opera.pge.base.base_pge import PgeExecutor
from opera.pge.base.base_pge import PostProcessorMixin
from opera.pge.base.base_pge import PreProcessorMixin
from opera.util.dataset_utils import parse_bounding_polygon_from_wkt
from opera.util.error_codes import ErrorCode
from opera.util.h5_utils import get_cslc_s1_product_metadata
from opera.util.h5_utils import get_disp_s1_product_metadata
from opera.util.input_validation import validate_algorithm_parameters_config, validate_disp_inputs
from opera.util.render_jinja2 import render_jinja2
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
        The DispS1PreProcessorMixin version of this class performs all actions
        of the base PreProcessorMixin class, and adds an input validation step
        for the inputs defined within the RunConfig.

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the pre-processor

        """
        super().run_preprocessor(**kwargs)

        # If debug mode is enabled, skip the input validation, since we might
        # be working with only a partial set of inputs/ancillaries
        if not self.runconfig.debug_switch:
            validate_disp_inputs(self.runconfig, self.logger, self.name)

        validate_algorithm_parameters_config(self.name,
                                             self.runconfig.algorithm_parameters_schema_path,
                                             self.runconfig.algorithm_parameters_file_config_path,
                                             self.logger)

    def convert_troposphere_model_files(self):
        """
        Convert grib (.grb) files to netCDF (.nc)
        Update the in-memory runconfig object such that the SAS/dynamic_ancillary_file_group/troposphere_files
        section now points to the converted .nc files in the scratch directory.

        """
        # Retrieve the troposphere weather model file group (if provided) from
        # the run config file
        troposphere_model_files_list = \
            self.runconfig.sas_config['dynamic_ancillary_file_group'].get('troposphere_files', {})

        # Converted files will be stored in the scratch directory.
        scratch_dir = self.runconfig.sas_config['product_path_group']['scratch_path']

        netcdf_file_list = []

        for tropo_file in troposphere_model_files_list:
            if splitext(tropo_file)[-1] == '.grb':
                # change the extension to .nc
                netcdf_file = join(scratch_dir, splitext(basename(tropo_file))[0] + '.nc')

                # This list of will the new paths to the converted files in the in-memory runconfig file.
                grib_file_name = tropo_file
                result = subprocess.run(
                    [
                        "/opt/conda/envs/eccodes/bin/grib_to_netcdf",
                        "-D",
                        "NC_FLOAT",
                        "-o",
                        netcdf_file,
                        grib_file_name,
                    ],
                    env={'ENV_NAME': 'eccodes', 'LD_LIBRARY_PATH': '/opt/conda/envs/eccodes/lib'},
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    shell=False,
                    check=False,
                )

                if result.returncode != 0:
                    error_msg = (
                        f"Failed to convert GRIB file {tropo_file} to NetCDF, reason:\n"
                        f"{result.stdout.decode()}"
                    )
                    self.logger.critical(self.name, ErrorCode.GRIB_TO_NETCDF_CONVERSION_FAILED, error_msg)
            else:
                # no conversion necessary, carry NetCDF file along as-is
                netcdf_file = tropo_file

            netcdf_file_list.append(netcdf_file)

        # Update the in-memory runconfig instance
        self.runconfig.sas_config['dynamic_ancillary_file_group']['troposphere_files'] = netcdf_file_list


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
    _product_metadata_cache = {}
    _product_filename_cache = {}

    def _validate_output(self):
        """
        Evaluates the output files generated from SAS execution to ensure:
            - That one expected .nc file exists in the output directory designated
              by the RunConfig and is non-zero in size
            - .png files corresponding to the expected output .nc product exists
              alongside and is non-zero in size
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

        if len(nc_files) == 0:
            error_msg = ("The SAS did not create any output file(s) with the "
                         "expected '.nc' extension")
            self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

        product_type = self.runconfig.sas_config['primary_executable']['product_type']

        if product_type == 'DISP_S1_FORWARD' and len(nc_files) > 1:
            error_msg = f"The SAS created too many files with the expected '.nc' extension: {nc_files}"
            self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

        for nc_file in nc_files:
            if not getsize(nc_file):
                error_msg = f"SAS output file {basename(nc_file)} exists, but is empty"
                self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

            # Validate .png file(s)
            nc_file_no_ext, ext = splitext(basename(nc_file))
            png_files = [
                join(output_dir, f'{nc_file_no_ext}.displacement.png'),
                join(output_dir, f'{nc_file_no_ext}.short_wavelength_displacement.png')
            ]

            for png_file in png_files:
                if not exists(png_file):
                    error_msg = f"Expected SAS output file {basename(png_file)} does not exist"
                    self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)
                elif not getsize(png_file):
                    error_msg = f"SAS output file {basename(png_file)} exists, but is empty"
                    self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

        save_compressed_slc = self.runconfig.sas_config['product_path_group']['save_compressed_slc']
        if save_compressed_slc:
            # Validate compressed_slcs directory
            comp_dir = join(output_dir, 'compressed_slcs')
            if not exists(comp_dir):
                error_msg = f"Expected SAS output directory '{basename(comp_dir)}' does not exist"
                self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

            comp_dir_list = listdir(comp_dir)
            if len(comp_dir_list) == 0:
                error_msg = f"Expected SAS output directory '{basename(comp_dir)}' exists, but is empty"
                self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

            # Validate each file in compressed_slcs directory
            for file_name in comp_dir_list:
                if not getsize(join(comp_dir, file_name)):
                    error_msg = f"Compressed CSLC file '{basename(file_name)}' exists, but is empty"
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
        core_filename = (
            f"{self.PROJECT}_{self.LEVEL}_{self.NAME}"
        )

        # Mode: S1-A/B acquisition mode, should be fixed to "IW"
        mode = "IW"

        # FrameID: Unique frame identification number as a 5-digit string in
        # the format FXXXXX
        frame_id = f"F{self.runconfig.sas_config['input_file_group']['frame_id']:05d}"

        inter_disp_product_filename = '.'.join(inter_filename.split('.')[:1] + ["nc"])

        # Check if we've already cached the product metadata corresponding to
        # this set of intermediate products (there can be multiple sets of
        # .nc and .png output files when running in historical mode)
        if inter_disp_product_filename in self._product_metadata_cache:
            disp_metadata = self._product_metadata_cache[inter_disp_product_filename]
        else:
            disp_metadata = self._collect_disp_s1_product_metadata(inter_disp_product_filename)
            self._product_metadata_cache[inter_disp_product_filename] = disp_metadata

        # Polarization: polarization of the input bursts
        # derived from product metadata of the input CSLC files
        cslc_file_list = self.runconfig.sas_config['input_file_group']['cslc_file_list']

        # Search for a CSLC file containing the metadata we expect
        for cslc_file in cslc_file_list:
            try:
                cslc_metadata = get_cslc_s1_product_metadata(abspath(cslc_file))
                polarization = cslc_metadata["processing_information"]["input_burst_metadata"]["polarization"]
                break
            except Exception:
                continue
        else:
            raise RuntimeError(
                'No input CSLC file contains the expected polarization information.'
            )

        # ReferenceDateTime: The acquisition sensing start date and time of
        # the input satellite imagery for the first burst in the frame of the
        # reference product in the format YYYYMMDDTHHMMSSZ
        reference_date_time = disp_metadata['identification']['reference_datetime']
        reference_date_time = datetime.datetime.strptime(reference_date_time, "%Y-%m-%d %H:%M:%S.%f")
        reference_date_time = f"{get_time_for_filename(reference_date_time)}Z"

        # SecondaryDateTime: The acquisition sensing start date and time of
        # the input satellite imagery for the first burst in the frame of this
        # secondary product in the format YYYYMMDDTHHMMSSZ
        secondary_date_time = disp_metadata['identification']['secondary_datetime']
        secondary_date_time = datetime.datetime.strptime(secondary_date_time, "%Y-%m-%d %H:%M:%S.%f")
        secondary_date_time = f"{get_time_for_filename(secondary_date_time)}Z"

        # ProductVersion: OPERA DISP-S1 product version number with four
        # characters, including the letter “v” and two digits indicating the
        # major and minor versions, which are delimited by a period
        product_version = f"v{disp_metadata['identification']['product_version']}"

        # ProductGenerationDateTime: The date and time at which the product
        # was generated by OPERA with the format of YYYYMMDDTHHMMSSZ
        product_generation_date_time = f"{get_time_for_filename(self.production_datetime)}Z"

        # Assign the file name conventions
        disp_s1_product_filename = (
            f"{core_filename}_{mode}_{frame_id}_{polarization}_"
            f"{reference_date_time}_{secondary_date_time}_{product_version}_"
            f"{product_generation_date_time}"
        )

        # Cache the file name for this set of DISP products, so it can be used
        # with the ISO metadata later.
        self._product_filename_cache[inter_disp_product_filename] = disp_s1_product_filename

        return disp_s1_product_filename

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
        browse_image_filename = f"{self._core_filename(inter_filename)}_BROWSE.png"

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

    def _compressed_cslc_filename(self, inter_filename):
        """
        Returns the file name to use for compressed CSLC files produced by the
        DISP-S1 PGE.

        The compressed CSLC filename for the DISP-S1 PGE consists of:

             <Project>_<Level>_COMPRESSED-CSLC-S1_<BurstID>_<ReferenceDateTime>_\
             <FirstDateTime>_<LastDateTime>_<ProductGenerationDateTime>_\
             <Polarization>_<ProductVersion>.h5

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the compressed CSLC product to generate
            a filename for. This parameter may be used to inspect the file
            in order to derive any necessary components of the returned filename.

        Returns
        -------
        compressed_cslc_filename : str
            The file name to assign to compressed CSLC product(s) created by this PGE.

        """
        level = "L2"
        name = "COMPRESSED-CSLC-S1"

        ccslc_regex = (r'compressed_(?P<burst_id>\w{4}_\w{6}_\w{3})_'
                       r'(?P<ref_date>\d{8})_'
                       r'(?P<start_date>\d{8})_'
                       r'(?P<stop_date>\d{8})[.](?P<ext>h5)$')

        result = re.match(ccslc_regex, os.path.basename(inter_filename))

        if not result:
            raise ValueError(
                f"Compressed CSLC file {inter_filename} does not conform to "
                f"expected file pattern"
            )

        # Cannonicalize the burst ID
        burst_id = result.groupdict()["burst_id"]
        burst_id = burst_id.upper().replace('_', '-')

        # Get the dates from the parsed intermediate filename
        ref_date = result.groupdict()["ref_date"]
        start_date = result.groupdict()["start_date"]
        stop_date = result.groupdict()["stop_date"]

        # Get the production time
        prod_time = f"{get_time_for_filename(self.production_datetime)}Z"

        # Polarization: polarization of the input bursts
        # derived from product metadata of the input CSLC files
        cslc_file_list = self.runconfig.sas_config['input_file_group']['cslc_file_list']

        # Search for a CSLC file containing the metadata we expect
        for cslc_file in cslc_file_list:
            try:
                cslc_metadata = get_cslc_s1_product_metadata(abspath(cslc_file))
                polarization = cslc_metadata["processing_information"]["input_burst_metadata"]["polarization"]
                break
            except Exception:
                continue
        else:
            raise RuntimeError(
                'No input CSLC file contains the expected polarization information.'
            )

        # Product version hardcoded to 1.0 for now since CCSLCs are not
        # intended for widespread distribution
        product_version = "1.0"

        # Carry the file extension over from the original filename
        ext = result.groupdict()["ext"]

        return (f"{self.PROJECT}_{level}_{name}_{burst_id}_"
                f"{ref_date}T000000Z_{start_date}T000000Z_"
                f"{stop_date}T000000Z_{prod_time}_"
                f"{polarization}_v{product_version}.{ext}")

    def _ancillary_filename(self):
        """
        Helper method to derive the core component of the file names for the
        ancillary products associated to a PGE job (catalog metadata, log file,
        etc...).

        The core file name component DISP-S1 ancillary products consists of:

        <PROJECT>_<LEVEL>_<PGE NAME>_<Mode>_<FrameID>_<ProductVersion>_<ProductGenerationDateTime>

        Since these files are note specific to any particular DISP-S1 output
        product, fields such as reference and secondary time are omitted from
        this file pattern.

        Also note that this file name does not include a file extension, which
        should be added to the return value of this method by any callers to
        distinguish the different formats of ancillary outputs produced by this
        PGE.

        Returns
        -------
        ancillary_filename : str
            The file name component to assign to ancillary products created by
            this PGE.

        """
        core_filename = (
            f"{self.PROJECT}_{self.LEVEL}_{self.NAME}"
        )

        mode = "IW"

        frame_id = f"F{self.runconfig.sas_config['input_file_group']['frame_id']:05d}"

        product_version = self.runconfig.sas_config['product_path_group']['product_version']

        if not product_version.startswith('v'):
            product_version = f'v{product_version}'

        product_generation_date_time = f"{get_time_for_filename(self.production_datetime)}Z"

        ancillary_filename = (
            f"{core_filename}_{mode}_{frame_id}_{product_version}_"
            f"{product_generation_date_time}"
        )

        return ancillary_filename

    def _catalog_metadata_filename(self):
        """
        Returns the file name to use for Catalog Metadata produced by the DISP-S1 PGE.

        The Catalog Metadata file name for the DISP-S1 PGE consists of:

            <Ancillary filename>.catalog.json

        Where <Ancillary filename> is returned by DispS1PostProcessorMixin._ancillary_filename()

        Returns
        -------
        catalog_metadata_filename : str
            The file name to assign to the Catalog Metadata product created by this PGE.

        """
        return self._ancillary_filename() + ".catalog.json"

    def _iso_metadata_filename(self, inter_disp_product_filename):
        """
        Returns the file name to use for ISO Metadata produced by the DISP-S1 PGE.

        The ISO Metadata file name for the DISP-S1 PGE consists of:

            <DISP filename>.iso.xml

        Where <DISP filename> is returned by DispS1PostProcessorMixin._core_filename()

        Parameters
        ----------
        inter_disp_product_filename : str
            The DISP-S1 product intermediate file name used to look-up the
            full filename assigned to the DISP-S1 output products.

        Returns
        -------
        iso_metadata_filename : str
            The file name to assign to the ISO Metadata product created by this PGE.

        Raises
        ------
        RuntimeError
            If there is no file name cached for the provided filename.

        """
        if inter_disp_product_filename not in self._product_filename_cache:
            raise RuntimeError(
                f"No file name cached for intermediate file name {inter_disp_product_filename}"
            )

        iso_metadata_filename = self._product_filename_cache[inter_disp_product_filename]

        return iso_metadata_filename + ".iso.xml"

    def _log_filename(self):
        """
        Returns the file name to use for the PGE/SAS log file produced by the DISP-S1 PGE.

        The log file name for the DISP-S1 PGE consists of:

            <Ancillary filename>.log

        Where <Ancillary filename> is returned by DispS1PostProcessorMixin._ancillary_filename()

        Returns
        -------
        log_filename : str
            The file name to assign to the PGE/SAS log created by this PGE.

        """
        return self._ancillary_filename() + ".log"

    def _qa_log_filename(self):
        """
        Returns the file name to use for the Quality Assurance application log
        file produced by the DISP-S1 PGE.

        The log file name for the DISP-S1 PGE consists of:

            <Ancillary filename>.qa.log

        Where <Ancillary filename> is returned by DispS1PostProcessorMixin._ancillary_filename()

        Returns
        -------
        log_filename : str
            The file name to assign to the QA log created by this PGE.

        """
        return self._ancillary_filename() + ".qa.log"

    def _collect_disp_s1_product_metadata(self, disp_product):
        """
        Gathers the available metadata from a sample output DISP-S1 product for
        use in filling out the ISO metadata template for the DISP-S1 PGE.

        Parameters
        ----------
        disp_product : str
            Path to the DISP-S1 NetCDF product to collect metadata from.

        Returns
        -------
        output_product_metadata : dict
            Dictionary containing DISP-S1 output product metadata, formatted
            for use with the ISO metadata Jinja2 template.

        """
        # Extract all metadata assigned by the SAS at product creation time
        output_product_metadata = get_disp_s1_product_metadata(disp_product)

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
            'ISO_OPERA_FilePackageName': self._ancillary_filename(),
            'ISO_OPERA_ProducerGranuleId': self._ancillary_filename(),
            'MetadataProviderAction': "creation",
            'GranuleFilename': self._ancillary_filename(),
            'ISO_OPERA_ProjectKeywords': ['OPERA', 'JPL', 'DISP', 'Displacement', 'Surface', 'Land', 'Global'],
            'ISO_OPERA_PlatformKeywords': ['S1'],
            'ISO_OPERA_InstrumentKeywords': ['Sentinel 1 A/B']
        }

        return custom_metadata

    def _create_iso_metadata(self, disp_metadata):
        """
        Creates a rendered version of the ISO metadata template for DISP-S1
        output products using metadata sourced from the following locations:

            * RunConfig (in dictionary form)
            * Output products (extracted from a sample product)
            * Catalog metadata
            * "Custom" metadata (all metadata not found anywhere else)

        Parameters
        ----------
        disp_metadata : dict
            The product metadata corresponding to the DISP-S1 product to generate
            the corresponding ISO xml for.

        Returns
        -------
        rendered_template : str
            The ISO metadata template for DISP-S1 filled in with values from
            the sourced metadata dictionaries.

        """
        runconfig_dict = self.runconfig.asdict()

        product_output_dict = disp_metadata

        catalog_metadata_dict = self._create_catalog_metadata().asdict()

        custom_data_dict = self._create_custom_metadata()

        iso_metadata = {
            'run_config': runconfig_dict,
            'product_output': product_output_dict,
            'catalog_metadata': catalog_metadata_dict,
            'custom_data': custom_data_dict
        }

        iso_template_path = self.runconfig.iso_template_path

        if iso_template_path is None:
            msg = "ISO template path not provided in runconfig"
            self.logger.critical(self.name, ErrorCode.ISO_METADATA_TEMPLATE_NOT_PROVIDED_WHEN_NEEDED, msg)

        iso_template_path = os.path.abspath(iso_template_path)

        if not os.path.exists(iso_template_path):
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
        each set of DISP-S1 products created from the set of input CSLCs, since
        each running in historical mode can product multiple sets of outputs, each
        with their own specific metadata fields.

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
        # For CSLC-S1, each burst-based product gets its own ISO xml
        for inter_filename, disp_metadata in self._product_metadata_cache.items():
            iso_metadata = self._create_iso_metadata(disp_metadata)

            iso_meta_filename = self._iso_metadata_filename(inter_filename)
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

    PGE_VERSION = "3.0.0-rc.3.0"
    """Version of the PGE (overrides default from base_pge)"""

    SAS_VERSION = "0.4.2"  # Gamma release https://github.com/opera-adt/disp-s1/releases/tag/v0.4.2

    def __init__(self, pge_name, runconfig_path, **kwargs):
        super().__init__(pge_name, runconfig_path, **kwargs)

        self.rename_by_pattern_map = OrderedDict(
            {
                # Note: ordering matters here!
                '*.nc': self._netcdf_filename,
                '*.displacement.png': self._browse_filename,
                'compressed*.h5': self._compressed_cslc_filename
            }
        )
