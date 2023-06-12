#!/usr/bin/env python3

"""
==============
dswx_s1_pge.py
==============
Module defining the implementation for the Dynamic Surface Water Extent (DSWx)
from Sentinel-1 A/B (S1) PGE.
"""

from os.path import abspath, exists, getsize, splitext

import opera.util.input_validation as input_validation
from opera.pge.base.base_pge import PgeExecutor
from opera.pge.base.base_pge import PostProcessorMixin
from opera.pge.base.base_pge import PreProcessorMixin
from opera.util.error_codes import ErrorCode
from opera.util.input_validation import validate_algorithm_parameters_config
from opera.util.input_validation import validate_dswx_inputs


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

    def _validate_ancillary_inputs(self):
        """
        Evaluates the list of ancillary inputs from the RunConfig to ensure they
        exist and have an expected file extension.

        """
        dynamic_ancillary_file_group_dict = \
            self.runconfig.sas_config['runconfig']['groups']['dynamic_ancillary_file_group']

        print(f"ANCILLARY_DICT: {dynamic_ancillary_file_group_dict}")

        for key, value in dynamic_ancillary_file_group_dict.items():
            if key in ('dem_file', ):
                input_validation.check_input(
                    value, self.logger, self.name, valid_extensions=('.tif', '.tiff', '.vrt')
                )
            elif key in ('reference_water_file', 'world_file', 'hand_file'):
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
        self._validate_ancillary_inputs()


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

    def _validate_output(self):
        """
        Evaluates the output file(s) generated from SAS execution to ensure:
            - That the file(s) contains some content (size is greater than 0).
            - That the .tif output files (band data) end with 'B01_WTR',
              'B02_BWTR', or 'B03_CONF'
            - That the there are the same number of each type of file, implying
              3 output bands per tile

        """
        EXPECTED_NUM_BANDS: int = 3
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
            error_msg = f"Invalid SAS output file, too many band types: {band_dict.keys()}"

            self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

        # Make a list of the numbers of bands per band type
        for band in band_dict.keys():
            num_bands.append(len(band_dict[band]))
        if not all(band_type == num_bands[0] for band_type in num_bands):
            error_msg = f"Missing or extra band files: number of band files per " \
                        f"band: {num_bands}"

            self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

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

    NAME = "DSWx"
    """Short name for the DSWx-S1 PGE"""

    LEVEL = "L3"
    """Processing Level for DSWx-S1 Products"""

    SAS_VERSION = "0.1"
    """Version of the SAS wrapped by this PGE, should be updated as needed"""

    def __init__(self, pge_name, runconfig_path, **kwargs):
        super().__init__(pge_name, runconfig_path, **kwargs)

        self.rename_by_pattern_map = {}
