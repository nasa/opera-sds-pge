#!/usr/bin/env python3

"""
==============
tropo_pge.py
==============
Module defining the implementation for the TROPO PGE.
"""

from os.path import basename, splitext

from opera.pge.base.base_pge import PgeExecutor
from opera.pge.base.base_pge import PostProcessorMixin
from opera.pge.base.base_pge import PreProcessorMixin
from opera.util.run_utils import get_checksum


class TROPOPreProcessorMixin(PreProcessorMixin):
    """
    Mixin class responsible for handling all pre-processing steps for the TROPO
    PGE. The pre-processing phase is defined as all steps necessary prior
    to SAS execution.
    In addition to the base functionality inherited from PreProcessorMixin, this
    mixin adds an input validation step to ensure that input(s) defined by the
    RunConfig exist and are valid.

     """

    _pre_mixin_name = "TROPOPreProcessorMixin"

    def run_preprocessor(self, **kwargs):
        """
        Executes the pre-processing steps for TROPO PGE initialization.
        The TROPOPreProcessorMixin version of this class performs all actions
        of the base PreProcessorMixin class, and adds an input validation step for
        the inputs defined within the RunConfig (TODO).
        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the pre-processor
        """
        super().run_preprocessor(**kwargs)


class TROPOPostProcessorMixin(PostProcessorMixin):
    """
    Mixin class responsible for handling all post-processing steps for the TROPO
    PGE. The post-processing phase is defined as all steps required after SAS
    execution has completed, prior to handover of output products to PCM.
    In addition to the base functionality inherited from PostProcessorMixin, this
    mixin adds an output validation step to ensure that the output file(s) defined
    by the RunConfig exist and are valid (TODO).
    """

    _post_mixin_name = "TROPOPostProcessorMixin"
    _cached_core_filename = None
    
    def _checksum_output_products(self):
        """
        Generates a dictionary mapping output product file names to the
        corresponding MD5 checksum digest of the file's contents.

        The products to generate checksums for are determined by scanning
        the output product location specified by the RunConfig. Any files
        within the directory that have the expected file extensions for output
        products are then picked up for checksum generation.

        Returns
        -------
        checksums : dict
            Mapping of output product file names to MD5 checksums of said
            products.

        """
        output_products = self.runconfig.get_output_product_filenames()

        # Filter out any files that do not end with the expected extensions
        expected_extensions = ('.nc', '.png')
        filtered_output_products = filter(
            lambda product: splitext(product)[-1] in expected_extensions,
            output_products
        )

        # Generate checksums on the filtered product list
        checksums = {
            basename(output_product): get_checksum(output_product)
            for output_product in filtered_output_products
        }

        return checksums

    def run_postprocessor(self, **kwargs):
        """
        Executes the post-processing steps for the TROPO PGE.
        The TROPOPostProcessorMixin version of this method performs the same
        steps as the base PostProcessorMixin, but inserts a step to perform
        output product validation prior to staging and renaming of the output
        files (TODO).
        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the post-processor
        """
        super().run_postprocessor(**kwargs)


class TROPOExecutor(TROPOPreProcessorMixin, TROPOPostProcessorMixin, PgeExecutor):
    """
    Main class for execution of the TROPO PGE, including the SAS layer.
    This class essentially rolls up the TROPO-specific pre- and post-processor
    functionality, while inheriting all other functionality for setup and execution
    of the SAS from the base PgeExecutor class.
    """

    NAME = "TROPO"
    """Short name for the TROPO PGE"""

    LEVEL = "L4"
    """Processing Level for TROPO Products"""
    
    PGE_VERSION = "3.0.0-er.1.0"
    """Version of the PGE"""

    SAS_VERSION = "0.1"
    """Version of the SAS wrapped by this PGE, should be updated as needed"""

    def __init__(self, pge_name, runconfig_path, **kwargs):
        super().__init__(pge_name, runconfig_path, **kwargs)

        self.rename_by_pattern_map = {}
