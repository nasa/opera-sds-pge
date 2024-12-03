#!/usr/bin/env python3

"""
==============
dist_s1_pge.py
==============
Module defining the implementation for the Surface Disturbance (DIST) from Sentinel-1 A/C (S1) PGE.

"""

from opera.pge.base.base_pge import PreProcessorMixin, PgeExecutor, PostProcessorMixin


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

    def run_postprocessor(self, **kwargs):
        """
        Executes the post-processing steps for the DSWx-NI PGE.
        The DistS1PostProcessorMixin version of this method performs the same
        steps as the base PostProcessorMixin.

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the post-processor
        """
        super().run_postprocessor(**kwargs)


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
