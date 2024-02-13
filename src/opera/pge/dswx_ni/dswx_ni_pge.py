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


class DSWxNIPreProcessorMixin(PreProcessorMixin):
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

