#!/usr/bin/env python3
#
# Copyright 2021-22, by the California Institute of Technology.
# ALL RIGHTS RESERVED.
# United States Government sponsorship acknowledged.
# Any commercial use must be negotiated with the Office of Technology Transfer
# at the California Institute of Technology.
# This software may be subject to U.S. export control laws and regulations.
# By accepting this document, the user agrees to comply with all applicable
# U.S. export laws and regulations. User has the responsibility to obtain
# export licenses, or other export authority as may be required, before
# exporting such information to foreign countries or providing access to
# foreign persons.
#

"""
===========
dswx_pge.py
===========

Module defining the implementation for the Dynamic Surface Water Extent (DSWx) PGE.

"""

import glob
import os.path
from os.path import abspath, exists, isdir, join, splitext

from opera.util.error_codes import ErrorCode
from opera.util.img_utils import get_geotiff_hls_dataset
from opera.util.img_utils import get_geotiff_metadata
from opera.util.img_utils import get_geotiff_spacecraft_name
from opera.util.img_utils import get_hls_filename_fields
from opera.util.render_jinja2 import render_jinja2
from opera.util.run_utils import get_extension

from .base_pge import PgeExecutor
from .base_pge import PostProcessorMixin
from .base_pge import PreProcessorMixin


class DSWxPreProcessorMixin(PreProcessorMixin):
    """
    Mixin class responsible for handling all pre-processing steps for the
    DSWx PGE. The pre-processing phase is defined as all steps necessary prior
    to SAS execution.

    In addition to the base functionality inherited from PreProcessorMixin, this
    mixin adds a input validation step to ensure that the input(s) defined by
    the RunConfig exist and are valid.

    """

    _pre_mixin_name = "DSWxPreProcessorMixin"

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
                list_of_input_tifs = glob.glob(join(input_file_path, '*.tif'))

                if len(list_of_input_tifs) <= 0:
                    error_msg = f"Input directory {input_file_path} does not contain any tif files"

                    self.logger.critical(self.name, ErrorCode.INPUT_NOT_FOUND, error_msg)
            elif not input_file_path.endswith(".tif"):
                error_msg = f"Input file {input_file_path} does not have .tif extension"

                self.logger.critical(self.name, ErrorCode.INVALID_INPUT, error_msg)

    def run_preprocessor(self, **kwargs):
        """
        Executes the pre-processing steps for DSWx PGE initialization.

        The DSWxPreProcessorMixin version of this function performs all actions
        of the base PreProcessorMixin class, and adds the validation check for
        input files/directories.

        Parameters
        ----------
        **kwargs : dict
            Any keyword arguments needed by the pre-processor

        """
        super().run_preprocessor(**kwargs)

        self._validate_inputs()


class DSWxPostProcessorMixin(PostProcessorMixin):
    """
    Mixin class responsible for handling all post-processing steps for the DSWx
    PGE. The post-processing phase is defined as all steps necessary after
    SAS execution has completed.

    In addition to the base functionality inherited from PostProcessorMixin, this
    mixin adds a output validation step to ensure that the output file defined by
    the RunConfig exist and are valid.

    """

    _post_mixin_name = "DSWxPostProcessorMixin"
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
            error_msg = f"No SAS output file(s) containing product ID {product_id} " \
                        f"found within {self.runconfig.output_product_path}"

            self.logger.critical(self.name, ErrorCode.OUTPUT_NOT_FOUND, error_msg)

        for output_product in output_products:
            if not os.path.getsize(output_product):
                error_msg = f"SAS output file {output_product} was created, but is empty"

                self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

    def _core_filename(self, inter_filename=None):
        """
        Returns the core file name component for products produced by the
        DSWx PGE.

        The core file name component of the DSWx PGE consists of:

        <PROJECT>_<LEVEL>_<PGE NAME>_<SOURCE>_<SPACECRAFT_NAME>_<TILE ID>_<TIMETAG>_<PRODUCT VERSION>_<PRODUCT_COUNTER>

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

        dataset = get_geotiff_hls_dataset(inter_filename)

        dataset_fields = get_hls_filename_fields(dataset)

        source = dataset_fields['product']
        spacecraft_name = get_geotiff_spacecraft_name(inter_filename).upper()
        tile_id = dataset_fields['tile_id']
        timetag = dataset_fields['acquisition_time']
        version = dataset_fields['collection_version']

        # Assign the core file to the cached class attribute
        self._cached_core_filename = (
            f"{self.PROJECT}_{self.LEVEL}_{self.NAME}_{source}_{spacecraft_name}_"
            f"{tile_id}_{timetag}_{version}_{str(self.runconfig.product_counter).zfill(3)}"
        )

        return self._cached_core_filename

    def _geotiff_filename(self, inter_filename):
        """
        Returns the file name to use for GeoTIFF's produced by the DSWx PGE.

        The GeoTIFF filename for the DSWx PGE consists of:

            <Core filename>_<Band Index>_<Band Name>.tif

        Where <Core filename> is returned by DSWxPostProcessorMixin._core_filename()
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

    def _collect_dswx_product_metadata(self):
        """
        Gathers the available metadata from a sample output DSWx product for
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
            if get_extension(output_product) in self.rename_by_extension_map:
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

        output_product_metadata['tileCode'] = hls_fields['tile_id']
        output_product_metadata['zoneIdentifier'] = hls_fields['tile_id'][:2]

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
            'MetadataProviderAction': "revision" if int(self.runconfig.product_counter) > 1 else "creation",
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
        Executes the post-processing steps for DSWx PGE job completion.

        The DSWxPostProcessorMixin version of this function performs the same
        steps as the base PostProcessorMixin, but inserts the output file
        validation check prior to staging of the output files.

        Parameters
        ----------
        **kwargs : dict
            Any keyword arguments needed by the post-processor

        """
        print(f'Running postprocessor for {self._post_mixin_name}')

        self._run_sas_qa_executable()
        self._validate_output()
        self._stage_output_files()


class DSWxExecutor(DSWxPreProcessorMixin, DSWxPostProcessorMixin, PgeExecutor):
    """
    Main class for execution of a DSWx PGE, including the SAS layer.

    This class essentially rolls up the DSWx-tailored pre- and post-processors
    while inheriting all other functionality from the base PgeExecutor class.

    """

    NAME = "DSWx"
    """Short name for the DSWx PGE"""

    LEVEL = "L3"
    """Processing Level for DSWx Products"""

    SAS_VERSION = "0.1"
    """Version of the SAS wrapped by this PGE, should be updated as needed with new SAS deliveries"""
