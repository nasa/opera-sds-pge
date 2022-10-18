#!/usr/bin/env python3

"""
=============
rtc_s1_pge.py
=============

Module defining the implementation for the Radiometric Terrain Corrected (RTC)
from Sentinel-1 A/B (S1) PGE.

"""

import os.path
from pathlib import Path

from opera.pge.base.base_pge import PgeExecutor
from opera.pge.base.base_pge import PostProcessorMixin
from opera.pge.base.base_pge import PreProcessorMixin
from opera.util.input_validation import validate_slc_s1_inputs
from opera.util.time import get_time_for_filename


class RtcS1PreProcessorMixin(PreProcessorMixin):
    """
    Mixin class responsible for handling all pre-processing steps for the RTC-S1
    PGE. The pre-processing phase is defined as all steps necessary prior to
    SAS execution.

    In addition to the base functionality inherited from PreProcessorMixin, this
    mixin adds an input validation step to ensure that input(s) defined by the
    RunConfig exist and are valid.

    """

    _pre_mixin_name = "RtcS1PreProcessorMixin"

    def run_preprocessor(self, **kwargs):
        """
        Executes the pre-processing steps for RTC-S1 PGE initialization.

        The RtcS1PreProcessorMixin version of this class performs all actions of
        the base PreProcessorMixin class, and adds an input validation step for
        the inputs defined within the RunConfig.

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the pre-processor

        """
        super().run_preprocessor(**kwargs)

        validate_slc_s1_inputs(self.runconfig, self.logger, self.name)


class RtcS1PostProcessorMixin(PostProcessorMixin):
    """
    Mixin class responsible for handling all post-processing steps for the RTC-S1
    PGE. The post-processing phase is defined as all steps required after SAS
    execution has completed, prior to handover of output products to PCM.

    In addition to the base functionality inherited from PostProcessorMixin, this
    mixin adds an output validation step to ensure that the output file(s) defined
    by the RunConfig exist and are valid. (TODO)

    """

    _post_mixin_name = "RtcS1PostProcessorMixin"
    _cached_core_filename = None

    def _core_filename(self, inter_filename=None):
        """
        Returns the core file name component for products produced by the
        RTC-S1 PGE.

        The core file name component for RTC-S1 products consists of:

        <PROJECT>_<LEVEL>_<PGE NAME>_<SOURCE>_{burst_id}_{acquisition_time}_
        {production_time}_<SENSOR>_<SPACING>_<PRODUCT VERSION>

        Where {burst_id}, {acquisition_time} and {production_time} are literal
        format-string placeholders and are NOT filled in by this method.
        Callers are responsible for assignment of these fields product-specific
        fields via a format() call.

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

        product_version = str(self.runconfig.product_version)

        if not product_version.startswith('v'):
            product_version = f'v{product_version}'

        # Assign the core file to the cached class attribute
        self._cached_core_filename = (
            f"{self.PROJECT}_{self.LEVEL}_{self.NAME}_{self.SOURCE}_"
            "{burst_id}_{acquisition_time}Z_{production_time}Z_"  # To be filled in per-product
            f"{self.SENSOR}_{self.SPACING}_{product_version}"
        )

        return self._cached_core_filename

    def _rtc_filename(self, inter_filename):
        """
        Returns the file name to use for RTC products produced by this PGE.

        The filename for the RTC PGE consists of:

            <Core filename>.<ext>

        Where <Core filename> is returned by RtcS1PostProcessorMixin._core_filename()
        and <ext> is the file extension carried over from inter_filename

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the output product to generate
            a filename for. This parameter may be used to inspect the file
            in order to derive any necessary components of the returned filename.

        Returns
        -------
        rtc_filename : str
            The file name to assign to RTC product(s) created by this PGE.

        """
        core_filename = self._core_filename(inter_filename)

        # Each RTC product is stored in a directory named for the corresponding burst ID
        burst_id = Path(os.path.dirname(inter_filename)).parts[-1]

        ext = os.path.splitext(inter_filename)[-1]

        # TODO: this will come from product metadata eventually
        production_time = get_time_for_filename(self.production_datetime)

        # TODO: this needs to be parsed from input SAFE file
        acquisition_time = production_time

        rtc_filename = core_filename.format(
            burst_id=burst_id,
            acquisition_time=acquisition_time,
            production_time=production_time
        ) + ext

        return rtc_filename

    def _ancillary_filename(self):
        """
        Helper method to derive the core component of the file names for
        the ancillary products associated to a PGE job (catalog metadata, log
        file, etc...).

        The core file name component for RTC-S1 ancillary products consists of:

        <PROJECT>_<LEVEL>_<PGE NAME>_<SOURCE>_<PRODUCTION TIME>_<SENSOR>_<SPACING>_<PRODUCT VERSION>

        Since these files are not specific to any particular burst processed
        for an RTC job, fields such as burst ID and acquisition time are omitted
        from this file pattern.

        Returns
        -------
        ancillary_filename : str
            The file name component to assign to ancillary products created by this PGE.

        """
        production_time = get_time_for_filename(self.production_datetime)
        product_version = str(self.runconfig.product_version)

        if not product_version.startswith('v'):
            product_version = f'v{product_version}'

        ancillary_filename = (
            f"{self.PROJECT}_{self.LEVEL}_{self.NAME}_{self.SOURCE}_"
            f"{production_time}Z_{self.SENSOR}_{self.SPACING}_{product_version}"
        )

        return ancillary_filename

    def _catalog_metadata_filename(self):
        """
        Returns the file name to use for Catalog Metadata produced by the RTC-S1 PGE.

        The Catalog Metadata file name for the RTC-S1 PGE consists of:

            <Ancillary filename>.catalog.json

        Where <Ancillary filename> is returned by RtcS1PostProcessorMixin._ancillary_filename()

        Returns
        -------
        catalog_metadata_filename : str
            The file name to assign to the Catalog Metadata product created by this PGE.

        """
        return self._ancillary_filename() + ".catalog.json"

    def _iso_metadata_filename(self):
        """
        Returns the file name to use for ISO Metadata produced by the RTC-S1 PGE.

        The ISO Metadata file name for the RTC-S1 PGE consists of:

            <Ancillary filename>.iso.xml

        Where <Ancillary filename> is returned by RtcS1PostProcessorMixin._ancillary_filename()

        Returns
        -------
        iso_metadata_filename : str
            The file name to assign to the ISO Metadata product created by this PGE.

        """
        return self._ancillary_filename() + ".iso.xml"

    def _log_filename(self):
        """
        Returns the file name to use for the PGE/SAS log file produced by the RTC-S1 PGE.

        The log file name for the RTC-S1 PGE consists of:

            <Ancillary filename>.log

        Where <Ancillary filename> is returned by RtcS1PostProcessorMixin._ancillary_filename()

        Returns
        -------
        log_filename : str
            The file name to assign to the PGE/SAS log created by this PGE.

        """
        return self._ancillary_filename() + ".log"

    def _qa_log_filename(self):
        """
        Returns the file name to use for the Quality Assurance application log
        file produced by the RTC-S1 PGE.

        The log file name for the RTC-S1 PGE consists of:

            <Ancillary filename>.qa.log

        Where <Ancillary filename> is returned by RtcS1PostProcessorMixin._ancillary_filename()

        Returns
        -------
        log_filename : str
            The file name to assign to the QA log created by this PGE.

        """
        return self._ancillary_filename() + ".qa.log"

    def run_postprocessor(self, **kwargs):
        """
        Executes the post-processing steps for the RTC-S1 PGE.

        The RtcS1PostProcessorMixin version of this method performs the same
        steps as the base PostProcessorMixin, but inserts a step to perform
        output product validation prior to staging and renaming of the output
        files. (TODO)

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the post-processo

        """
        super().run_postprocessor(**kwargs)

        # TODO replace super().run_postprocessor() call with reimplementation
        #      that invokes the output validation step in-between the SAS QA and
        #      output file staging steps inherited from the base PGE


class RtcS1Executor(RtcS1PreProcessorMixin, RtcS1PostProcessorMixin, PgeExecutor):
    """
    Main class for execution of the RTC-S1 PGE, including the SAS layer.

    This class essentially rolls up the RTC-specific pre- and post-processor
    functionality, while inheriting all other functionality for setup and execution
    of the SAS from the base PgeExecutor class.

    """

    NAME = "RTC"
    """Short name for the RTC-S1 PGE"""

    LEVEL = "L2"
    """Processing Level for RTC-S1 Products"""

    SAS_VERSION = "0.1"  # Interface release https://github.com/opera-adt/RTC/releases/tag/v0.1
    """Version of the SAS wrapped by this PGE, should be updated as needed"""

    # TODO: these are hardcoded for now, need to determine if they will come
    #       from product metadata
    SOURCE = "S1"
    SENSOR = "S1A"
    SPACING = "30"

    def __init__(self, pge_name, runconfig_path, **kwargs):
        super().__init__(pge_name, runconfig_path, **kwargs)

        self.rename_by_pattern_map = {
            "*.nc": self._rtc_filename
        }
