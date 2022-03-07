#!/usr/bin/env python3
#
# Copyright 2021, by the California Institute of Technology.
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
from os.path import abspath, exists, isdir, join

from opera.util.error_codes import ErrorCode
from opera.util.img_utils import get_geotiff_hls_dataset
from opera.util.img_utils import get_geotiff_spacecraft_name
from opera.util.img_utils import get_hls_filename_fields

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
        Evaluates the output file generated from SAS execution to ensure its
        existence, and that the file contains some content (size is greater than
        0).
        """
        output_path = abspath(
            join(self.runconfig.output_product_path, self.runconfig.sas_output_file)
        )

        if not exists(output_path):
            error_msg = f"Expected SAS output file {output_path} does not exist"

            self.logger.critical(self.name, ErrorCode.OUTPUT_NOT_FOUND, error_msg)

        if not os.path.getsize(output_path):
            error_msg = f"SAS output file {output_path} was created but is empty"

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

        # TODO: Kludge to be removed once SAS produces per-band outputs
        dataset_fields = get_hls_filename_fields(f"{dataset}.BAND.tif")

        source = dataset_fields['product']
        spacecraft_name = get_geotiff_spacecraft_name(inter_filename)
        tile_id = dataset_fields['tile_id']
        timetag = dataset_fields['acquisition_time']
        version = dataset_fields['collection_version']
        subversion = dataset_fields['sub_version']

        # Assign the core file to the cached class attribute
        self._cached_core_filename = (
            f"{self.PROJECT}_{self.LEVEL}_{self.NAME}_{source}_{spacecraft_name}_"
            f"{tile_id}_{timetag}_{version}.{subversion}_{str(self.runconfig.product_counter).zfill(3)}"
        )

        return self._cached_core_filename

    def _geotiff_filename(self, inter_filename):
        """
        Returns the file name to use for GeoTIFF's produced by the DSWx PGE.

        The GeoTIFF filename for the DSWx PGE consists of:

            <Core filename>.tif

        Where <Core filename> is returned by DSWxPostProcessorMixin._core_filename()

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

        # TODO: include band once SAS produces per-band outputs
        return f"{core_filename}.tif"

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
