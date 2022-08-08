#!/usr/bin/env python3

"""
==============
cslc_s1_pge.py
==============

Module defining the implementation for the Co-registered Single Look Complex (CSLC)
from Sentinel-1 A/B (S1) PGE.

"""

import json
import os.path
from datetime import datetime

from opera.pge.base.base_pge import PgeExecutor
from opera.pge.base.base_pge import PostProcessorMixin
from opera.pge.base.base_pge import PreProcessorMixin
from opera.util.error_codes import ErrorCode
from opera.util.time import get_time_for_filename


class CslcS1PreProcessorMixin(PreProcessorMixin):
    """
    Mixin class responsible for handling all pre-processing steps for the CSLC-S1
    PGE. The pre-processing phase is defined as all steps necessary prior
    to SAS execution.

    In addition to the base functionality inherited from PreProcessorMixin, this
    mixin adds an input validation step to ensure that input(s) defined by the
    RunConfig exist and are valid.

    """

    _pre_mixin_name = "CslcS1PreProcessorMixin"

    def run_preprocessor(self, **kwargs):
        """
        Executes the pre-processing steps for CSLC-S1 PGE initialization.

        The CslcS1PreProcessorMixin version of this class performs all actions
        of the base PreProcessorMixin class, and adds an input validation step for
        the inputs defined within the RunConfig (TODO).

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the pre-processor

        """
        super().run_preprocessor(**kwargs)


class CslcS1PostProcessorMixin(PostProcessorMixin):
    """
    Mixin class responsible for handling all post-processing steps for the CSLC-S1
    PGE. The post-processing phase is defined as all steps required after SAS
    execution has completed, prior to handover of output products to PCM.

    In addition to the base functionality inherited from PostProcessorMixin, this
    mixin adds an output validation step to ensure that the output file(s) defined
    by the RunConfig exist and are valid (TODO).

    """

    _post_mixin_name = "CslcS1PostProcessorMixin"
    _cached_core_filename = None

    def _core_filename(self, inter_filename=None):
        """
        Returns the core file name component for products produced by the
        CSLC-S1 PGE.

        The core file name component of the CSLC-S1 PGE consists of:

        <PROJECT>_<LEVEL>_<PGE NAME>_<SENSOR>_<MODE>_<BURST ID>_<POL>_<ACQ TIMETAG>_<PRODUCT VER>_<PROD TIMETAG>

        Callers of this function are responsible for assignment of any other
        product-specific fields, such as the file extension.

        Notes
        -----
        On first call to this function, the returned core filename is cached
        for subsequent calls. This allows the core filename to be easily reused
        across product types without needing to provide inter_filename for each
        subsequent call.

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

        # CSLC-S1 SAS produces two output files: the image and a separate
        # json metadata file, each with the same base filename.
        # We use that here to always locate and read the json metadata file.
        metadata_filename = os.path.splitext(inter_filename)[0] + '.json'

        with open(metadata_filename, 'r') as infile:
            cslc_metadata = json.load(infile)

        sensor = cslc_metadata['platform_id']
        mode = 'IW'  # fixed for all S1-based CSLC products
        burst_id = cslc_metadata['burst_id'].upper().replace('_', '-')
        pol = cslc_metadata['polarization']
        acquisition_time = get_time_for_filename(
            datetime.strptime(cslc_metadata['sensing_start'], '%Y-%m-%d %H:%M:%S.%f')
        )
        product_version = self.SAS_VERSION  # TODO: may extract from cslc_metadata eventually
        production_time = get_time_for_filename(self.production_datetime)

        self._cached_core_filename = (
            f"{self.PROJECT}_{self.LEVEL}_{self.NAME}_{sensor}_{mode}_{burst_id}_"
            f"{pol}_{acquisition_time}Z_v{product_version}_{production_time}Z"
        )

        return self._cached_core_filename

    def _geotiff_filename(self, inter_filename):
        """
        Returns the file name to use for GeoTIFF's produced by the CSLC-S1 PGE.

        The GeoTIFF filename for the CSLC-S1 PGE consists of:

            <Core filename>.tiff

        Where <Core filename> is returned by CslcS1PostProcessorMixin._core_filename()

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the output GeoTIFF to generate a
            filename for. This parameter may be used to inspect the file in order
            to derive any necessary components of the returned filename.

        Returns
        -------
        geotiff_filename : str
            The file name to assign to GeoTIFF product(s) created by this PGE.

        """
        core_filename = self._core_filename(inter_filename)

        return f"{core_filename}.tiff"

    def _json_metadata_filename(self, inter_filename):
        """
        Returns the file name to use for JSON metadata files produced by the
        CSLC-S1 PGE.

        The JSON metadata filename for the CSLC-S1 PGE consists of:

            <Core filename>.json

        Where <Core filename> is returned by CslcS1PostProcessorMixin._core_filename()

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the output JSON metadata to generate a
            filename for. This parameter may be used to inspect the file in order
            to derive any necessary components of the returned filename.

        Returns
        -------
        json_metadata_filename : str
            The file name to assign to JSON metadata product(s) created by this PGE.

        """
        core_filename = self._core_filename(inter_filename)

        return f"{core_filename}.json"

    def run_postprocessor(self, **kwargs):
        """
        Executes the post-processing steps for the CSLC-S1 PGE.

        The CslcS1PostProcessorMixin version of this method performs the same
        steps as the base PostProcessorMixin, but inserts a step to perform
        output product validation prior to staging and renaming of the output
        files (TODO).

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the post-processor

        """
        super().run_postprocessor(**kwargs)


class CslcS1Executor(CslcS1PreProcessorMixin, CslcS1PostProcessorMixin, PgeExecutor):
    """
    Main class for execution of the CSLC-S1 PGE, including the SAS layer.

    This class essentially rolls up the CSLC-specific pre- and post-processor
    functionality, while inheriting all other functionality for setup and execution
    of the SAS from the base PgeExecutor class.

    """

    NAME = "CSLC"
    """Short name for the CSLC-S1 PGE"""

    LEVEL = "L2"
    """Processing Level for CSLC-S1 Products"""

    SAS_VERSION = "0.1"
    """Version of the SAS wrapped by this PGE, should be updated as needed"""

    def __init__(self, pge_name, runconfig_path, **kwargs):
        super().__init__(pge_name, runconfig_path, **kwargs)

        self.rename_by_pattern_map = {
            '*.slc': self._geotiff_filename,
            '*.tif*': self._geotiff_filename,
            '*.json': self._json_metadata_filename
        }
