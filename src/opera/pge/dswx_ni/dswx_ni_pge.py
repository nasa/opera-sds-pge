#!/usr/bin/env python3

"""
==============
dswx_ni_pge.py
==============
Module defining the implementation for the Dynamic Surface Water Extent (DSWX)
from NISAR (NI) PGE.
"""

from opera.pge.base.base_pge import PgeExecutor
from opera.pge.base.base_pge import PostProcessorMixin
from opera.pge.base.base_pge import PreProcessorMixin
from opera.pge.dswx_s1.dswx_s1_pge import DSWxS1PreProcessorMixin

class DSWxNIPreProcessorMixin(DSWxS1PreProcessorMixin):
    """
    Mixin class responsible for handling all pre-processing steps for the DSWX-NI
    PGE. The pre-processing phase is defined as all steps necessary prior
    to SAS execution.
    In addition to the base functionality inherited from PreProcessorMixin, this
    mixin adds an input validation step to ensure that input(s) defined by the
    RunConfig exist and are valid.

     """

    _pre_mixin_name = "DSWxNIPreProcessorMixin"

    def run_preprocessor(self, **kwargs):
        """
        Executes the pre-processing steps for DSWx-NI PGE initialization.
        The DswxS1PreProcessorMixin version of this class performs all actions
        of the base PreProcessorMixin class, and adds an input validation step for
        the inputs defined within the RunConfig (TODO).
        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the pre-processor
        """
        super().run_preprocessor(**kwargs)

    def _validate_dynamic_ancillary_inputs(self):
        """
        Evaluates the list of dynamic ancillary inputs from the RunConfig to
        ensure they exist and have an expected file extension.

        """
        dynamic_ancillary_file_group_dict = \
            self.runconfig.sas_config['runconfig']['groups']['dynamic_ancillary_file_group']

        for key, value in dynamic_ancillary_file_group_dict.items():
            if key in ('dem_file', 'reference_water_file', 'worldcover_file', 'hand_file'):
                input_validation.check_input(
                    value, self.logger, self.name, valid_extensions=('.tif', '.tiff', '.vrt')
                )
            elif key in ('shoreline_shapefile',):
                if value is not None:
                    input_validation.check_input(
                        value, self.logger, self.name, valid_extensions=('.shp',))
                    # Only the .shp file is configured in the runconfig, but we
                    # need to ensure the other required files are co-located with it
                    for extension in ('.dbf', '.prj', '.shx'):
                        additional_shapefile = splitext(value)[0] + extension

                        if not exists(abspath(additional_shapefile)):
                            error_msg = f"Additional shapefile {additional_shapefile} could not be located"

                            self.logger.critical(self.name, ErrorCode.INVALID_INPUT, error_msg)
                else:
                    msg = "No shoreline_shapefile specified in runconfig file."
                    self.logger.info(self.name, ErrorCode.INPUT_NOT_FOUND, msg)

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

    def _validate_static_ancillary_inputs(self):
        """
        Evaluates the list of static ancillary inputs from the RunConfig to
        ensure they exist and have an expected file extension.

        """
        static_ancillary_file_group_dict = \
            self.runconfig.sas_config['runconfig']['groups']['static_ancillary_file_group']

        for key, value in static_ancillary_file_group_dict.items():
            if key in ('mgrs_database_file', 'mgrs_collection_database_file'):
                input_validation.check_input(
                    value, self.logger, self.name, valid_extensions=('.sqlite', '.sqlite3')
                )
            elif key in ('static_ancillary_inputs_flag', ):
                # these fields are included in the SAS input paths, but are not
                # actually file paths, so skip them
                continue

class DSWxNIPostProcessorMixin(PostProcessorMixin):
    """
    Mixin class responsible for handling all post-processing steps for the DSWx-NI
    PGE. The post-processing phase is defined as all steps required after SAS
    execution has completed, prior to handover of output products to PCM.
    In addition to the base functionality inherited from PostProcessorMixin, this
    mixin adds an output validation step to ensure that the output file(s) defined
    by the RunConfig exist and are valid (TODO).
    """

    _post_mixin_name = "DSWxNIPostProcessorMixin"
    _cached_core_filename = None

    def run_postprocessor(self, **kwargs):
        """
        Executes the post-processing steps for the DSWx-NI PGE.
        The DSWxNIPostProcessorMixin version of this method performs the same
        steps as the base PostProcessorMixin, but inserts a step to perform
        output product validation prior to staging and renaming of the output
        files (TODO).
        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the post-processor
        """
        super().run_postprocessor(**kwargs)


class DSWxNIExecutor(DSWxNIPreProcessorMixin, DSWxNIPostProcessorMixin, PgeExecutor):
    """
    Main class for execution of the DSWx-NI PGE, including the SAS layer.
    This class essentially rolls up the DSWx-specific pre- and post-processor
    functionality, while inheriting all other functionality for setup and execution
    of the SAS from the base PgeExecutor class.
    """

    NAME = "DSWx-NI"
    """Short name for the DSWx-NI PGE"""

    LEVEL = "L3"
    """Processing Level for DSWx-NI Products"""

    SAS_VERSION = "0.1"
    """Version of the SAS wrapped by this PGE, should be updated as needed"""

    def __init__(self, pge_name, runconfig_path, **kwargs):
        super().__init__(pge_name, runconfig_path, **kwargs)

        self.rename_by_pattern_map = {}

