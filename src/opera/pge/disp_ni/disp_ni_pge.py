#!/usr/bin/env python3

"""
==============
disp_ni_pge.py
==============
Module defining the implementation for the Surface Displacement (DISP) from NISAR PGE.
"""

from collections import OrderedDict
from datetime import datetime

from opera.pge.base.base_pge import PgeExecutor
from opera.pge.disp_s1.disp_s1_pge import DispS1PostProcessorMixin, DispS1PreProcessorMixin
from opera.util.dataset_utils import parse_bounding_polygon_from_wkt
from opera.util.error_codes import ErrorCode
from opera.util.h5_utils import get_disp_s1_product_metadata as get_disp_product_metadata
from opera.util.render_jinja2 import augment_hdf5_measured_parameters
from opera.util.time import get_catalog_metadata_datetime_str, get_time_for_filename


class DispNIPreProcessorMixin(DispS1PreProcessorMixin):
    """
    Mixin class responsible for handling all pre-processing steps for the DISP-NI
    PGE. The pre-processing phase is defined as all steps necessary prior
    to SAS execution.
    This particular pre-processor inherits from the DISP-S1 pre-processor mixin
    with one check disabled currently as it does not apply to DISP-NI currently.
    but may in the future.
    """

    _pre_mixin_name = "DispNIPreProcessorMixin"
    _valid_input_extensions = (".tif",)

    def _validate_runconfig_needed_options(self):
        """
        Bypass this method for NISAR. It may need to be re-implemented if we have a
        DISP-NI-STATIC PGE in the future.
        """
        pass

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


class DispNIPostProcessorMixin(DispS1PostProcessorMixin):
    """
    Mixin class responsible for handling all post-processing steps for the DISP-NI
    PGE. The post-processing phase is defined as all steps required after SAS
    execution has completed, prior to handover of output products to PCM.
    """

    _post_mixin_name = "DispNIPostProcessorMixin"
    _cached_core_filename = None
    _tile_metadata_cache = {}
    _tile_filename_cache = {}

    def _core_filename(self, inter_filename=None):
        """
        Returns the core file name component for products produced by the
        DISP-NI PGE.

        The core file name component of the DISP-NI PGE consists of:

        <PROJECT>_<LEVEL>_<PGE NAME>_<REL>_<P>_<FRM>_<MODE>_<PO>_\
        <ReferenceDateTime>_<SecondaryDateTime>_<ProductVersion>_\
        <ProductGenerationDateTime>

        Callers of this function are responsible for assignment of any other
        product-specific fields, such as the file extension.

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
            The filename component to assign to frame-based products created by
            this PGE.
        """
        core_filename = (
            f"{self.PROJECT}_{self.LEVEL}_{self.NAME}"
        )

        # TODO: Determine the following three fields from metadata (hardcode for now)
        orbit_track = "001"
        orbit_direction = "A"
        mode = "05"

        frame_id = f"{self.runconfig.sas_config['input_file_group']['frame_id']:03d}"
        pol = self.runconfig.sas_config['input_file_group']['polarization']

        inter_disp_product_filename = '.'.join(inter_filename.split('.')[:1] + ["nc"])

        # Check if we've already cached the product metadata corresponding to
        # this set of intermediate products (there can be multiple sets of
        # .nc and .png output files when running in historical mode)
        if inter_disp_product_filename in self._product_metadata_cache:
            disp_metadata = self._product_metadata_cache[inter_disp_product_filename]
        else:
            disp_metadata = self._collect_disp_ni_product_metadata(inter_disp_product_filename)
            self._product_metadata_cache[inter_disp_product_filename] = disp_metadata

        # ReferenceDateTime: The acquisition sensing start date and time of
        # the input satellite imagery for the first burst in the frame of the
        # reference product in the format YYYYMMDDTHHMMSSZ
        reference_date_time = disp_metadata['identification']['reference_zero_doppler_start_time']
        reference_date_time = datetime.strptime(reference_date_time, "%Y-%m-%d %H:%M:%S.%f")
        reference_date_time = f"{get_time_for_filename(reference_date_time)}Z"

        # SecondaryDateTime: The acquisition sensing start date and time of
        # the input satellite imagery for the first burst in the frame of this
        # secondary product in the format YYYYMMDDTHHMMSSZ
        secondary_date_time = disp_metadata['identification']['secondary_zero_doppler_start_time']
        secondary_date_time = datetime.strptime(secondary_date_time, "%Y-%m-%d %H:%M:%S.%f")
        secondary_date_time = f"{get_time_for_filename(secondary_date_time)}Z"

        # ProductVersion: OPERA DISP-NI product version number with four
        # characters, including the letter “v” and two digits indicating the
        # major and minor versions, which are delimited by a period
        product_version = f"v{disp_metadata['identification']['product_version']}"

        # ProductGenerationDateTime: The date and time at which the product
        # was generated by OPERA with the format of YYYYMMDDTHHMMSSZ
        product_generation_date_time = f"{get_time_for_filename(self.production_datetime)}Z"

        disp_ni_product_filename = (
            f"{core_filename}_{orbit_track}_{orbit_direction}_{frame_id}_{mode}_{pol}_"
            f"{reference_date_time}_{secondary_date_time}_{product_version}_"
            f"{product_generation_date_time}"
        )

        # Cache the file name for this set of DISP products, so it can be used
        # with the ISO metadata later.
        self._product_filename_cache[inter_disp_product_filename] = disp_ni_product_filename

        return disp_ni_product_filename

    def _compressed_gslc_filename(self, inter_filename):
        """
        Returns the file name to use for compressed GSLC files produced by the
        DISP-NI PGE.

        The compressed GSLC filename for the DISP-NI PGE consists of:

             <Project>_<Level>_COMPRESSED-GSLC-NI_<REL>_<P>_<FRM>_<MODE>_\
             <ReferenceDateTime>_<FirstDateTime>_<LastDateTime>_\
             <ProductGenerationDateTime>_<Polarization>_<ProductVersion>.h5

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the compressed CSLC product to generate
            a filename for. This parameter may be used to inspect the file
            in order to derive any necessary components of the returned filename.

        Returns
        -------
        compressed_cslc_filename : str
            The file name to assign to compressed CSLC product(s) created by this PGE.

        """
        level = "L2"
        name = "COMPRESSED-GSLC-NI"
        frame_id = f"{self.runconfig.sas_config['input_file_group']['frame_id']:03d}"

        from os.path import basename
        # TODO: Finalize naming convention & implement
        return basename(inter_filename)

    def _ancillary_filename(self):
        """
        Helper method to derive the core component of the file names for the
        ancillary products associated to a PGE job (catalog metadata, log file,
        etc...).

        The core file name component DISP-NI ancillary products consists of:

        <PROJECT>_<LEVEL>_<PGE NAME>_<REL>_<P>_<FRM>_<MODE>_<PO>_
        <ProductVersion>_<ProductGenerationDateTime>

        Since these files are note specific to any particular DISP-NI output
        product, fields such as reference and secondary time are omitted from
        this file pattern.

        Also note that this file name does not include a file extension, which
        should be added to the return value of this method by any callers to
        distinguish the different formats of ancillary outputs produced by this
        PGE.

        Returns
        -------
        ancillary_filename : str
            The file name component to assign to ancillary products created by
            this PGE.

        """
        core_filename = (
            f"{self.PROJECT}_{self.LEVEL}_{self.NAME}"
        )

        frame_id = f"{self.runconfig.sas_config['input_file_group']['frame_id']:03d}"
        pol = self.runconfig.sas_config['input_file_group']['polarization']

        product_version = self.runconfig.sas_config['product_path_group']['product_version']

        if not product_version.startswith('v'):
            product_version = f'v{product_version}'

        product_generation_date_time = f"{get_time_for_filename(self.production_datetime)}Z"

        ancillary_filename = (
            f"{core_filename}_{frame_id}_{pol}_{product_version}_{product_generation_date_time}"
        )

        return ancillary_filename

    def _collect_disp_ni_product_metadata(self, disp_product):
        """
        Gathers the available metadata from a sample output DISP-NI product for
        use in filling out the ISO metadata template for the DISP-NI PGE.

        Parameters
        ----------
        disp_product : str
            Path to the DISP-NI NetCDF product to collect metadata from.

        Returns
        -------
        output_product_metadata : dict
            Dictionary containing DISP-NI output product metadata, formatted
            for use with the ISO metadata Jinja2 template.

        """
        # Extract all metadata assigned by the SAS at product creation time
        try:
            output_product_metadata = get_disp_product_metadata(disp_product)

            # get_catalog_metadata_datetime_str(self.production_datetime)

            # Add hardcoded values to metadata
            output_product_metadata['static'] = {
                'Project': 'OPERA',
                'ProductLevel': 3,
                'ProductType': 'DISP-NI',
                'ProductSource': 'NISAR',
                'ProcessingDateTime': get_catalog_metadata_datetime_str(self.production_datetime)
            }

            output_product_metadata['MeasuredParameters'] = augment_hdf5_measured_parameters(
                output_product_metadata,
                self.runconfig.iso_measured_parameter_descriptions,
                self.logger
            )
        except Exception as err:
            msg = f'Failed to extract metadata from {disp_product}, reason: {err}'
            self.logger.critical(self.name, ErrorCode.ISO_METADATA_COULD_NOT_EXTRACT_METADATA, msg)

        # Parse the image polygon coordinates to conform with gml
        bounding_polygon_wkt_str = output_product_metadata['identification']['bounding_polygon']

        try:
            bounding_polygon_gml_str = parse_bounding_polygon_from_wkt(bounding_polygon_wkt_str)
            output_product_metadata['bounding_polygon'] = bounding_polygon_gml_str
        except ValueError as err:
            self.logger.critical(self.name, ErrorCode.ISO_METADATA_RENDER_FAILED, str(err))

        # Add some fields on the dimensions of the data.
        output_product_metadata['xCoordinates'] = {
            'size': len(output_product_metadata['x']),  # pixels
            'spacing': 30  # meters/pixel
        }
        output_product_metadata['yCoordinates'] = {
            'size': len(output_product_metadata['y']),  # pixels
            'spacing': 30  # meters/pixel
        }

        return output_product_metadata

    def _create_custom_metadata(self, inter_filename):
        """
        Creates the "custom data" dictionary used with the ISO metadata rendering.

        Custom data contains all metadata information needed for the ISO template
        that is not found within any of the other metadata sources (such as the
        RunConfig, output product(s), or catalog metadata).

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the output product to generate a
            core filename for. This core filename will be used as the "granule"
            identifier within the returned metadata dictionary.

        Returns
        -------
        custom_metadata : dict
            Dictionary containing the custom metadata as expected by the ISO
            metadata Jinja2 template.

        """
        custom_metadata = super()._create_custom_metadata(inter_filename)

        custom_metadata['ISO_OPERA_PlatformKeywords'] = ['NI']
        custom_metadata['ISO_OPERA_InstrumentKeywords'] = ['NISAR']

        return custom_metadata

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

        self.rename_by_pattern_map = OrderedDict(
            {
                '*.nc': self._netcdf_filename,
                '*displacement.png': self._browse_filename,
                'compressed*.h5': self._compressed_gslc_filename
            }
        )
