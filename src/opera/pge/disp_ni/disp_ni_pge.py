#!/usr/bin/env python3

"""
==============
disp_ni_pge.py
==============
Module defining the implementation for the Surface Displacement (DISP) from NISAR PGE.
"""

from opera.pge.base.base_pge import PgeExecutor, PostProcessorMixin, PreProcessorMixin


class DispNIPreProcessorMixin(PreProcessorMixin):
    """
    Mixin class responsible for handling all pre-processing steps for the DISP-NI
    PGE. The pre-processing phase is defined as all steps necessary prior
    to SAS execution.
    This particular pre-processor is currently a stub implementation, inheriting from the base pre-processor mixin
    and adding nothing at this time. New functionalities will be added as new versions of the DISP-NI SAS are released.
    """

    _pre_mixin_name = "DispNIPreProcessorMixin"
    _valid_input_extensions = (".tif",)

    def run_preprocessor(self, **kwargs):
        """
        Executes the pre-processing steps for DISP-NI PGE initialization.
        The DispNIPreProcessorMixin version of this class performs all actions
        of the PreProcessorMixin class. Parameterization of the validation
        functions is handled via specialized class attributes (i.e. _valid_input_extensions)

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the pre-processor
        """
        super().run_preprocessor(**kwargs)


class DispNIPostProcessorMixin(PostProcessorMixin):
    """
    Mixin class responsible for handling all post-processing steps for the DISP-NI
    PGE. The post-processing phase is defined as all steps required after SAS
    execution has completed, prior to handover of output products to PCM.
    This particular pre-processor is currently a stub implementation, inheriting from the base pre-processor mixin
    and adding nothing at this time. New functionalities will be added as new versions of the DISP-NI SAS are released.
    """

    _post_mixin_name = "DispNIPostProcessorMixin"
    _cached_core_filename = None
    _tile_metadata_cache = {}
    _tile_filename_cache = {}

    def run_postprocessor(self, **kwargs):
        """
        Executes the post-processing steps for the DISP-NI PGE.
        The DispNIPostProcessorMixin version of this method performs the same
        steps as the base PostProcessorMixin.

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the post-processor
        """
        super().run_postprocessor(**kwargs)


class DispNIExecutor(DispNIPreProcessorMixin, DispNIPostProcessorMixin, PgeExecutor):
    """
    Main class for execution of the DISP-NI PGE, including the SAS layer.
    This class essentially rolls up the DISP-specific pre- and post-processor
    functionality, while inheriting all other functionality for setup and execution
    of the SAS from the base PgeExecutor class.
    """

    NAME = "DISP-NI"
    """Short name for the DISP-NI PGE"""

    LEVEL = "L3"
    """Processing Level for DISP-NI Products"""

    SAS_VERSION = "0.1.1"  # Interface release https://github.com/opera-adt/disp-nisar/releases/tag/v0.1.1
    """Version of the SAS wrapped by this PGE, should be updated as needed"""

    def __init__(self, pge_name, runconfig_path, **kwargs):
        super().__init__(pge_name, runconfig_path, **kwargs)

        self.rename_by_pattern_map = {}
