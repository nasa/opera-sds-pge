#!/usr/bin/env python3

"""
===============
cal_disp_pge.py
===============
Module defining the implementation of the Calibration for Surface Displacement from Sentinel-1 and NISAR (CAL-DISP) PGE.
"""

from opera.pge.base.base_pge import PgeExecutor, PostProcessorMixin, PreProcessorMixin
from opera.util.input_validation import validate_algorithm_parameters_config, validate_cal_inputs


class CalDispPreProcessorMixin(PreProcessorMixin):
    """
    Mixin class responsible for handling all pre-processing steps for the DISP-NI
    PGE. The pre-processing phase is defined as all steps necessary prior
    to SAS execution.
    This particular pre-processor is currently a stub implementation, inheriting from the base pre-processor mixin
    and adding nothing at this time. New functionalities will be added as new versions of the DISP-NI SAS are released.
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
    and adding nothing at this time. New functionalities will be added as new versions of the DISP-NI SAS are released.
    """

    _pre_mixin_name = "CalDispPostProcessorMixin"
    _product_metadata_cache = {}
    _product_filename_cache = {}

    def run_postprocessor(self, **kwargs):
        """
        Executes the post-processing steps for the CAL-DISP PGE.
        The CalDispPostProcessorMixin version of this method performs the same
        steps as the base PostProcessorMixin.

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the post-processor
        """
        super().run_postprocessor(**kwargs)


class CalDispExecutor(CalDispPreProcessorMixin, CalDispPostProcessorMixin, PgeExecutor):
    """
    Main class for execution of the CAL-DISP PGE, including the SAS layer.
    This class essentially rolls up the CAL-DISP-specific pre- and post-processor
    functionality, while inheriting all other functionality for setup and execution
    of the SAS from the base PgeExecutor class.
    """

    NAME = "CAL-DISP"
    """Short name for the CAL-DISP PGE"""

    LEVEL = "L4"
    """Processing Level for CAL-DISP Products"""

    SAS_VERSION = "0.1"  # Interface release https://github.com/opera-adt/cal-disp/releases/tag/v0.1
    """Version of the SAS wrapped by this PGE, should be updated as needed"""

    def __init__(self, pge_name, runconfig_path, **kwargs):
        super().__init__(pge_name, runconfig_path, **kwargs)

        self.rename_by_pattern_map = {}
