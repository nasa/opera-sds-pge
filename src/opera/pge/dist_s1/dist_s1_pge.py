#!/usr/bin/env python3

"""
==============
dist_s1_pge.py
==============
Module defining the implementation for the Surface Disturbance (DIST) from Sentinel-1 A/C (S1) PGE.

"""

import os
import re
from os.path import join, isdir, isfile, abspath

from opera.pge.base.base_pge import PreProcessorMixin, PgeExecutor, PostProcessorMixin
from opera.util.error_codes import ErrorCode
from opera.util.input_validation import check_input_list


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
    _tile_metadata_cache = {}
    _tile_filename_cache = {}
    _output_layer_names = ['DATE-FIRST', 'DATE-LATEST', 'DIST-STATUS-ACQ',
                           'DIST-STATUS', 'GEN-METRIC', 'N-DIST', 'N-OBS']

    def _validate_outputs(self):
        # TODO: Below is a pattern better aligned with the product spec. The uncommented pattern aligns with the current
        #  SAS output
        # product_id_pattern = (r'(?P<id>(?P<project>OPERA)_(?P<level>L3)_(?P<product_type>DIST)-(?P<source>S1)_'
        #                       r'(?P<tile_id>T[^\W_]{5})_(?P<acquisition_ts>(?P<acq_year>\d{4})(?P<acq_month>\d{2})'
        #                       r'(?P<acq_day>\d{2})T(?P<acq_hour>\d{2})(?P<acq_minute>\d{2})(?P<acq_second>\d{2})Z)_'
        #                       r'(?P<creation_ts>(?P<cre_year>\d{4})(?P<cre_month>\d{2})(?P<cre_day>\d{2})T'
        #                       r'(?P<cre_hour>\d{2})(?P<cre_minute>\d{2})(?P<cre_second>\d{2})Z)_(?P<sensor>S1[AC])_'
        #                       r'(?P<spacing>30)_(?P<product_version>v\d+[.]\d+[.]\d+))')

        product_id_pattern = (r'(?P<id>(?P<project>OPERA)_(?P<level>L3)_(?P<product_type>DIST-ALERT)-(?P<source>S1)_'
                              r'(?P<tile_id>T[^\W_]{5})_(?P<acquisition_ts>(?P<acq_year>\d{4})(?P<acq_month>\d{2})'
                              r'(?P<acq_day>\d{2})T(?P<acq_hour>\d{2})(?P<acq_minute>\d{2})(?P<acq_second>\d{2})Z)_'
                              r'(?P<creation_ts>(?P<cre_year>\d{4})(?P<cre_month>\d{2})(?P<cre_day>\d{2})T'
                              r'(?P<cre_hour>\d{2})(?P<cre_minute>\d{2})(?P<cre_second>\d{2})Z)_(?P<sensor>S1)_'
                              r'(?P<spacing>30)_(?P<product_version>v\d+[.]\d+[.]\d+))')

        granule_filename_pattern = (product_id_pattern + rf'((_(?P<layer_name>{"|".join(self._output_layer_names)}))|'
                                                         r'_BROWSE)?[.](?P<ext>tif|tiff|png)$')

        product_id = re.compile(product_id_pattern + r'$')
        granule_filename = re.compile(granule_filename_pattern)

        output_product_path = abspath(self.runconfig.output_product_path)
        output_products = []

        for file in os.listdir(output_product_path):
            dir_path = join(output_product_path, file)
            if isdir(dir_path) and product_id.match(file):
                bands = []
                generated_band_names = []

                for granule in os.listdir(dir_path):
                    granule_path = join(dir_path, granule)
                    if isfile(granule_path):
                        match_result = granule_filename.match(granule)

                        if match_result is None:  # or match_result.groupdict()['ext'] != 'tif':
                            error_msg = f'Invalid product filename {granule}'
                            self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)
                        elif os.stat(granule_path).st_size == 0:
                            error_msg = f'Output file {granule_path} is empty.'
                            self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)
                        elif match_result.groupdict()['layer_name'] not in self._output_layer_names:
                            error_msg = f'Invalid layer name "{match_result.groupdict()["layer_name"]}" in output.'
                            self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

                        bands.append(granule_path)
                        generated_band_names.append(match_result.groupdict()['layer_name'])

                if len(bands) != len(self._output_layer_names):
                    error_msg = f'Incorrect number of output bands generated: {len(generated_band_names)}'
                    self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

                output_products.append(dir_path)

        if len(output_products) != 1:
            error_msg = f'Incorrect number of output granules generated: {len(output_products)}'
            self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

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

    SAS_VERSION = "0.0.3"  # Beta release https://github.com/opera-adt/dist-s1/releases/tag/v0.0.3
    """Version of the SAS wrapped by this PGE, should be updated as needed"""

    def __init__(self, pge_name, runconfig_path, **kwargs):
        super().__init__(pge_name, runconfig_path, **kwargs)

        self.rename_by_pattern_map = {}
