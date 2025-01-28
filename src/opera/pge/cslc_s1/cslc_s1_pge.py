#!/usr/bin/env python3

"""
==============
cslc_s1_pge.py
==============

Module defining the implementation for the Co-registered Single Look Complex (CSLC)
from Sentinel-1 A/B (S1) PGE.

"""
import glob
import os.path
from datetime import datetime
from os import walk
from os.path import getsize, join
from pathlib import Path

import yaml

from opera.pge.base.base_pge import PgeExecutor
from opera.pge.base.base_pge import PostProcessorMixin
from opera.pge.base.base_pge import PreProcessorMixin
from opera.util.dataset_utils import parse_bounding_polygon_from_wkt
from opera.util.error_codes import ErrorCode
from opera.util.h5_utils import get_cslc_s1_product_metadata, MEASURED_PARAMETER_PATH_SEPARATOR
from opera.util.input_validation import validate_slc_s1_inputs
from opera.util.render_jinja2 import render_jinja2
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
        of the base PreProcessorMixin class, and adds an input validation step
        for the inputs defined within the RunConfig.

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the pre-processor

        """
        super().run_preprocessor(**kwargs)

        validate_slc_s1_inputs(self.runconfig, self.logger, self.name)


class CslcS1PostProcessorMixin(PostProcessorMixin):
    """
    Mixin class responsible for handling all post-processing steps for the CSLC-S1
    PGE. The post-processing phase is defined as all steps required after SAS
    execution has completed, prior to handover of output products to PCM.

    In addition to the base functionality inherited from PostProcessorMixin, this
    mixin adds an output validation step to ensure that the output file(s) defined
    by the RunConfig exist and are valid.

    """

    _post_mixin_name = "CslcS1PostProcessorMixin"
    _cached_core_filename = None
    _burst_metadata_cache = {}
    _burst_filename_cache = {}

    def _validate_output(self):
        """
        Evaluates the output file(s) generated from SAS execution to ensure
        existence, also validate that the file(s) contains some content
        (size is greater than 0).
        """
        out_dir_walk_dict = {}

        output_dir = os.path.abspath(self.runconfig.output_product_path)
        scratch_dir = os.path.abspath(self.runconfig.scratch_path)

        # from 'output_dir' make a dictionary of {sub_dir_name: [file1, file2,...]}
        for path, dirs, files in walk(output_dir):
            if not dirs and scratch_dir not in path:  # Ignore files in 'output_dir' and scratch directory
                dir_key = path.replace(output_dir, "")
                if dir_key.startswith('/'):
                    dir_key = dir_key[1:]
                out_dir_walk_dict[dir_key] = files

        if not out_dir_walk_dict:
            error_msg = f"No SAS output file(s) found within {output_dir}"

            self.logger.critical(self.name, ErrorCode.OUTPUT_NOT_FOUND, error_msg)

        expected_ext = ['tiff', 'tif', 'h5', 'png']

        # Verify: files in subdirectories, file length, and proper extension.
        for dir_name_key, file_names in out_dir_walk_dict.items():
            if len(file_names) == 0:
                error_msg = f"Empty SAS output directory: {'/'.join((output_dir, dir_name_key))}"

                self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

            for file_name in file_names:
                if not getsize(os.path.join(output_dir, dir_name_key, file_name)):
                    error_msg = f"SAS output file {file_name} exists, but is empty"

                    self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

                if file_name.split('.')[-1] not in expected_ext:
                    error_msg = f"SAS output file {file_name} extension error: expected one of {expected_ext}"

                    self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)

    def _core_filename(self, inter_filename=None):
        """
        Returns the core file name component for products produced by the
        CSLC-S1 PGE.

        The core file name component of the CSLC-S1 PGE consists of:

        <PROJECT>_<LEVEL>_<PGE NAME>

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

        # Assign the core file name to the cached class attribute
        self._cached_core_filename = (
            f"{self.PROJECT}_{self.LEVEL}_{self.NAME}"
        )

        return self._cached_core_filename

    def _core_static_filename(self, inter_filename=None):
        """
        Returns the core file name component for static layer products produced
        by the CSLC-S1 PGE.

        The core file name component of the CSLC-S1 PGE static layer products
        consists of:

        <Core filename>-STATIC

        Where <Core filename> is returned by CslcS1PostProcessorMixin._core_filename()

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
        core_static_filename : str
            The core file name component to assign to static layer products
            created by this PGE.

        """
        core_filename = self._core_filename(inter_filename)

        return f"{core_filename}-STATIC"

    def _cslc_filename(self, inter_filename, static_layer_product=False):
        """
        Returns the file name to use for burst-based CSLC products produced by this PGE.

        The filename for the CSLC-S1 burst products consists of:

            <Core filename>_<BURST ID>_<ACQUISITION TIMETAG>[_<PRODUCTION TIMETAG>]_<SENSOR>_<POL>_<PRODUCT_VERSION>

        Where <Core filename> is returned by CslcS1PostProcessorMixin._core_filename()
        if static_layer_product is False, otherwise it is the value returned by
        CslcS1PostProcessorMixin._core_static_filename()

        If static_layer_product is True, <ACQUISITION TIMETAG> will correspond
        to the configured data validity start time (as defined in the RunConfig),
        and <PRODUCTION TIMETAG> will be omitted altogether.

        Also note that this does not include a file extension, which should be
        added to the return value of this method by any callers to distinguish
        different file formats that are produced for each burst in an input SLC.

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the output GeoTIFF to generate a
            filename for. This parameter may be used to inspect the file in order
            to derive any necessary components of the returned filename.
        static_layer_product : bool, optional
            If True, use the file name conventions specific to static layer
            products. Otherwise, use the baseline conventions. Defaults to False.

        Returns
        -------
        cslc_filename : str
            The file name to assign to CSLC product(s) created by this PGE.

        Raises
        ------
        ValueError
            If static_layer_product is True and no value was specified for
            DataValidityStartDate within the RunConfig.

        """
        if static_layer_product:
            core_filename = self._core_static_filename(inter_filename)
        else:
            core_filename = self._core_filename(inter_filename)

        # The burst ID should be included within the file path for each
        # output directory, extract it and prepare it for use within the
        # final filename
        burst_id_dir = Path(os.path.dirname(inter_filename)).parts[-2]
        burst_id = burst_id_dir.upper().replace('_', '-')

        if burst_id in self._burst_metadata_cache:
            cslc_metadata = self._burst_metadata_cache[burst_id]
        else:
            # Collect the metadata from the HDF5 output product
            cslc_h5_product_pattern = join(os.path.dirname(inter_filename), f"*{burst_id_dir}*.h5")

            # Find the main .h5 product path based on location of the current file
            # and burst ID
            cslc_h5_product_paths = glob.glob(cslc_h5_product_pattern)

            if len(cslc_h5_product_paths) != 1:
                raise RuntimeError(f'Got unexpected number of CSLC .h5 paths: {cslc_h5_product_paths}')

            cslc_metadata = self._collect_cslc_product_metadata(cslc_h5_product_paths[0])

            self._burst_metadata_cache[burst_id] = cslc_metadata

        burst_metadata = cslc_metadata['processing_information']['input_burst_metadata']

        # If generating a filename for a static layer product, we use the
        # data validity start time configured in the RunConfig in lieu of
        # the acquisition time
        if static_layer_product:
            acquisition_time = self.runconfig.data_validity_start_date

            if acquisition_time is None:
                raise ValueError(
                    'static_layer_product was requested, but no value was provided '
                    'for DataValidityStartDate within the RunConfig'
                )
        else:
            acquisition_time = burst_metadata['sensing_start']

            if acquisition_time.endswith('Z'):
                acquisition_time = acquisition_time[:-1]

            acquisition_time = get_time_for_filename(
                datetime.strptime(acquisition_time, '%Y-%m-%d %H:%M:%S.%f')
            )

            if not acquisition_time.endswith('Z'):
                acquisition_time += 'Z'

        # We omit production time from static layer products to make the file
        # names more uniquely identifiable
        if static_layer_product:
            production_time = ""
        else:
            production_time = f"_{get_time_for_filename(self.production_datetime)}Z"

        sensor = burst_metadata['platform_id']

        # Polarization only included in file name for baseline products
        pol = "" if static_layer_product else f"_{burst_metadata['polarization']}"

        product_version = str(self.runconfig.product_version)

        if not product_version.startswith('v'):
            product_version = f'v{product_version}'

        cslc_filename = (
            f"{core_filename}_{burst_id}_{acquisition_time}{production_time}_"
            f"{sensor}{pol}_{product_version}"
        )

        # Cache the file name for this burst ID, so it can be used with the
        # ISO metadata later.
        self._burst_filename_cache[burst_id] = cslc_filename

        return cslc_filename

    def _h5_filename(self, inter_filename):
        """
        Returns the file name to use for HDF5 products produced by the CSLC-S1 PGE.

        The HDF5 filename for the CSLC-S1 PGE consists of:

            <CSLC filename>.h5

        Where <CSLC filename> is returned by CslcS1PostProcessorMixin._cslc_filename()

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the output HDF5 to generate a
            filename for. This parameter may be used to inspect the file in order
            to derive any necessary components of the returned filename.

        Returns
        -------
        h5_filename : str
            The file name to assign to HDF5 product(s) created by this PGE.

        """
        cslc_filename = self._cslc_filename(inter_filename)

        return f"{cslc_filename}.h5"

    def _static_layers_filename(self, inter_filename):
        """
        Returns the file name to use for the static layers product produced by
        the CSLC-S1 PGE.

        The static layers filename for the CSLC-S1 PGE consists of:

            <CSLC static filename>.h5

        Where <CSLC static filename> is returned by CslcS1PostProcessorMixin._cslc_filename()
        with static_layer_product set to True.

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the output HDF5 product containing all
            the output static layers. This parameter is used to derive the
            core CSLC file name component for static layer products.

        Returns
        -------
        static_layers_filename : str
            The file name to assign to static layers product(s) created by this PGE.

        """
        cslc_filename = self._cslc_filename(inter_filename, static_layer_product=True)

        static_layers_filename = f"{cslc_filename}.h5"

        return static_layers_filename

    def _browse_filename(self, inter_filename):
        """
        Returns the file name to use for the PNG browse image produced by
        the CSLC-S1 PGE.

        The browse image filename for the CSLC-S1 PGE consists of:

            <CSLC filename>_BROWSE.png

        Where <CSLC filename> is returned by CslcS1PostProcessorMixin._cslc_filename()

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the output browse image to generate a
            filename for. This parameter may be used to inspect the file in order
            to derive any necessary components of the returned filename.

        Returns
        -------
        browse_image_filename : str
            The file name to assign to browse image created by this PGE.

        """
        cslc_filename = self._cslc_filename(inter_filename)

        return f"{cslc_filename}_BROWSE.png"

    def _geotiff_filename(self, inter_filename):
        """
        Returns the file name to use for GeoTIFF's produced by the CSLC-S1 PGE.

        The GeoTIFF filename for the CSLC-S1 PGE consists of:

            <CSLC filename>.tif

        Where <CSLC filename> is returned by CslcS1PostProcessorMixin._cslc_filename()

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
        cslc_filename = self._cslc_filename(inter_filename)

        return f"{cslc_filename}.tif"

    def _json_metadata_filename(self, inter_filename):
        """
        Returns the file name to use for JSON metadata files produced by the
        CSLC-S1 PGE.

        The JSON metadata filename for the CSLC-S1 PGE consists of:

            <CSLC filename>.json

        Where <CSLC filename> is returned by CslcS1PostProcessorMixin._cslc_filename()

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
        cslc_filename = self._cslc_filename(inter_filename)

        return f"{cslc_filename}.json"

    def _ancillary_filename(self):
        """
        Helper method to derive the core component of the file names for the
        ancillary products associated to a PGE job (catalog metadata, log file,
        etc...).

        The core file name component for CSLC-S1 ancillary products consists of:

        <PROJECT>_<LEVEL>_<PGE NAME>_<PRODUCTION TIMETAG>_<SENSOR>_<POL>_<PRODUCT VER>

        Since these files are not specific to any particular burst processed for
        a CSLC job, fields such as burst ID and acquisition time are omitted from
        this file pattern.

        Also note that this does not include a file extension, which should be
        added to the return value of this method by any callers to distinguish
        the different formats of ancillary outputs produced by this PGE.

        Returns
        -------
        ancillary_filename : str
            The file name component to assign to ancillary products created by this PGE.

        """
        # Metadata fields we need for ancillary file name should be equivalent
        # across all bursts, so just take the first set of cached metadata as
        # a representative
        cslc_metadata = list(self._burst_metadata_cache.values())[0]

        burst_metadata = cslc_metadata['processing_information']['input_burst_metadata']

        sensor = burst_metadata['platform_id']
        pol = burst_metadata['polarization']

        product_version = str(self.runconfig.product_version)

        if not product_version.startswith('v'):
            product_version = f'v{product_version}'

        production_time = get_time_for_filename(self.production_datetime)

        ancillary_filename = (
            f"{self.PROJECT}_{self.LEVEL}_{self.NAME}_{production_time}Z_"
            f"{sensor}_{pol}_{product_version}"
        )

        return ancillary_filename

    def _catalog_metadata_filename(self):
        """
        Returns the file name to use for Catalog Metadata produced by the CSLC-S1 PGE.

        The Catalog Metadata file name for the CSLC-S1 PGE consists of:

            <Ancillary filename>.catalog.json

        Where <Ancillary filename> is returned by CslcPostProcessorMixin._ancillary_filename()

        Returns
        -------
        catalog_metadata_filename : str
            The file name to assign to the Catalog Metadata product created by this PGE.

        """
        return self._ancillary_filename() + ".catalog.json"

    def _iso_metadata_filename(self, burst_id):
        """
        Returns the file name to use for ISO Metadata produced by the CSLC-S1 PGE.

        The ISO Metadata file name for the CSLC-S1 PGE consists of:

            <CSLC filename>.iso.xml

        Where <CSLC filename> is returned by CslcS1PostProcessorMixin._cslc_filename()

        Parameters
        ----------
        burst_id : str
            The burst identifier used to look up the corresponding cached
            CSLC filename.

        Returns
        -------
        iso_metadata_filename : str
            The file name to assign to the ISO Metadata product created by this PGE.

        Raises
        ------
        RuntimeError
            If there is no file name cached for the provided burst ID.

        """
        if burst_id not in self._burst_filename_cache:
            raise RuntimeError(f"No file name cached for burst ID {burst_id}")

        iso_metadata_filename = self._burst_filename_cache[burst_id]

        return iso_metadata_filename + ".iso.xml"

    def _log_filename(self):
        """
        Returns the file name to use for the PGE/SAS log file produced by the CSLC-S1 PGE.

        The log file name for the CSLC-S1 PGE consists of:

            <Ancillary filename>.log

        Where <Ancillary filename> is returned by CslcS1PostProcessorMixin._ancillary_filename()

        Returns
        -------
        log_filename : str
            The file name to assign to the PGE/SAS log created by this PGE.

        """
        return self._ancillary_filename() + ".log"

    def _qa_log_filename(self):
        """
        Returns the file name to use for the Quality Assurance application log
        file produced by the CSLC-S1 PGE.

        The log file name for the CSLC-S1 PGE consists of:

            <Ancillary filename>.qa.log

        Where <Ancillary filename> is returned by CslcS1PostProcessorMixin._ancillary_filename()

        Returns
        -------
        log_filename : str
            The file name to assign to the QA log created by this PGE.

        """
        return self._ancillary_filename() + ".qa.log"

    def augment_measured_parameters(self, measured_parameters):
        """
        Override of the augment_measured_parameters() method in Base PGE with an added
        "preprocessing" step to handle the structure of HDF5 metadata. While GeoTIFF
        metadata is a flat dictionary, HDF5 metadata is a nested dictionary structure,
        wherein the variable "keys" can be arbitrarily deep into the structure and
        the values likewise can be nested dictionaries.

        The preprocessing step in this method selectively flattens the metadata
        dictionary based on the "paths" provided in the variable keys of the configuration
        YAML file. The result of this preprocessing is then safely passed to the base
        method to get the correct structure expected by the Jinja template.

        Parameters
        ----------
        measured_parameters : dict
            The HDF5 metadata from the output product. See get_cslc_s1_product_metadata()

        Returns
        -------
        augmented_parameters : dict
            The metadata fields converted to a list with name, value, types, etc
        """
        descriptions_file = self.runconfig.iso_measured_parameter_descriptions

        new_measured_parameters = {}

        if descriptions_file:
            with open(descriptions_file) as f:
                descriptions = yaml.safe_load(f)
        else:
            msg = ('Measured parameters configuration is needed to extract the measured parameters attributes from the'
                   'CSLC metadata')
            self.logger.critical(self.name, ErrorCode.ISO_METADATA_DESCRIPTIONS_CONFIG_NOT_FOUND, msg)

        for parameter_var_name in descriptions:
            key_path = parameter_var_name.split(MEASURED_PARAMETER_PATH_SEPARATOR)

            mp = measured_parameters

            while len(key_path) > 0:
                try:
                    mp = mp[key_path.pop(0)]
                except KeyError as e:
                    msg = (f'Measured parameters configuration contains an path {parameter_var_name} that is missing '
                           f'from the output product')
                    if descriptions[parameter_var_name].get('optional', False):
                        self.logger.warning(self.name, ErrorCode.ISO_METADATA_NO_ENTRY_FOR_DESCRIPTION, msg)
                    else:
                        self.logger.critical(self.name, ErrorCode.ISO_METADATA_DESCRIPTIONS_CONFIG_INVALID, msg)

            new_measured_parameters[parameter_var_name] = mp

        augmented_parameters = super().augment_measured_parameters(new_measured_parameters)

        return augmented_parameters

    def _collect_cslc_product_metadata(self, cslc_product):
        """
        Gathers the available metadata from the HDF5 product created by the
        CSLC-S1 SAS. This metadata is then formatted for use with filling in
        the ISO metadata template for the CSLC-S1 PGE.

        Parameters
        ----------
        cslc_product : str
            Path the HDF5/NETCDF product to collect metadata from.

        Returns
        -------
        output_product_metadata : dict
            Dictionary containing CSLC-S1 output product metadata, formatted for
            use with the ISO metadata Jinja2 template.

        """
        # Extract all metadata assigned by the SAS at product creation time
        try:
            output_product_metadata = get_cslc_s1_product_metadata(cslc_product)
            output_product_metadata['MeasuredParameters'] = self.augment_measured_parameters(output_product_metadata)
        except Exception as err:
            msg = f'Failed to extract metadata from {cslc_product}, reason: {err}'
            self.logger.critical(self.name, ErrorCode.ISO_METADATA_COULD_NOT_EXTRACT_METADATA, msg)

        # Fill in some additional fields expected within the ISO
        output_product_metadata['data']['width'] = len(output_product_metadata['data']['x_coordinates'])
        output_product_metadata['data']['length'] = len(output_product_metadata['data']['y_coordinates'])

        # Remove larger datasets to save memory when caching metadata for each burst
        for key in ['x_coordinates', 'y_coordinates']:
            array = output_product_metadata['data'].pop(key, None)

            if array is not None:
                del array

        # Parse the burst center coordinate to conform with gml schema
        # sample: {ndarray: (2,)} [-118.30363047, 33.8399832]
        burst_center = output_product_metadata['processing_information']['input_burst_metadata']['center']
        burst_center_str = f"{burst_center[0]} {burst_center[1]}"
        output_product_metadata['burst_center'] = burst_center_str

        # Parse the burst polygon coordinates to conform with gml
        burst_polygon_wtk_str = output_product_metadata['identification']['bounding_polygon']

        try:
            burst_polygon_gml_str = parse_bounding_polygon_from_wkt(burst_polygon_wtk_str)
            output_product_metadata['burst_polygon'] = burst_polygon_gml_str
        except ValueError as err:
            self.logger.critical(self.name, ErrorCode.ISO_METADATA_RENDER_FAILED, str(err))

        # Jinja2 cannot serialize int64 data types to JSON, so convert the shape array
        # to a list of native Python ints
        shape = output_product_metadata['processing_information']['input_burst_metadata']['shape']
        shape = list(map(int, shape))
        output_product_metadata['processing_information']['input_burst_metadata']['shape'] = shape

        # Some metadata fields which can be a list of files can also be specified
        # as a string if there is only a single file. Wrap these fields in a list
        # in order to maintain a consistent approach to serializing them in the
        # template.
        for key in ('calibration_files', 'l1_slc_files', 'noise_files', 'orbit_files'):
            inputs = output_product_metadata['processing_information']['inputs'][key]
            if isinstance(inputs, str):
                output_product_metadata['processing_information']['inputs'][key] = [inputs]

        return output_product_metadata

    def _create_custom_metadata(self):
        """
        Creates the "custom data" dictionary used with the ISO metadata rendering.

        Custom data contains all metadata information needed for the ISO template
        that is not found within any of the other metadata sources (such as the
        RunConfig, output product(s), or catalog metadata).

        Returns
        -------
        custom_metadata : dict
            Dictionary containing the custom metadata as expected by the ISO
            metadata Jinja2 template.

        """
        custom_metadata = {
            'ISO_OPERA_FilePackageName': self._core_filename(),
            'ISO_OPERA_ProducerGranuleId': self._core_filename(),
            'MetadataProviderAction': "creation",
            'GranuleFilename': self._core_filename(),
            'ISO_OPERA_ProjectKeywords': ['OPERA', 'JPL', 'CSLC', 'Co-registered', 'Single', 'Look', 'Complex'],
            'ISO_OPERA_PlatformKeywords': ['S1'],
            'ISO_OPERA_InstrumentKeywords': ['Sentinel 1 A/B']
        }

        return custom_metadata

    def _create_iso_metadata(self, burst_metadata):
        """
        Creates a rendered version of the ISO metadata template for CSLC-S1
        output products using metadata from the following locations:

            * RunConfig (in dictionary form)
            * Output product (dictionary extracted from HDF5 product, per-burst)
            * Catalog metadata
            * "Custom" metadata (all metadata not found anywhere else)

        Parameters
        ----------
        burst_metadata : dict
            The product metadata corresponding to a specific burst product to
            be included as the "product_output" metadata in the rendered ISO xml.

        Returns
        -------
        rendered_template : str
            The ISO metadata template for CSLC-S1 filled in with values from
            the sourced metadata dictionaries.

        """
        # Use the base PGE implemenation to validate existence of the template
        super()._create_iso_metadata()

        runconfig_dict = self.runconfig.asdict()

        product_output_dict = burst_metadata

        catalog_metadata_dict = self._create_catalog_metadata().asdict()

        custom_data_dict = self._create_custom_metadata()

        iso_metadata = {
            'run_config': runconfig_dict,
            'product_output': product_output_dict,
            'catalog_metadata': catalog_metadata_dict,
            'custom_data': custom_data_dict
        }

        iso_template_path = os.path.abspath(self.runconfig.iso_template_path)

        rendered_template = render_jinja2(iso_template_path, iso_metadata, self.logger)

        return rendered_template

    def _stage_output_files(self):
        """
        Ensures that all output products produced by both the SAS and this PGE
        are staged to the output location defined by the RunConfig. This includes
        reassignment of file names to meet the file-naming conventions required
        by the PGE.

        This version of the method performs the same steps as the base PGE
        implementation, except that an ISO xml metadata file is rendered for
        each burst product created from the input SLC, since each burst can
        have specific metadata fields, such as the bounding polygon.

        """
        # Gather the list of output files produced by the SAS
        output_products = self.runconfig.get_output_product_filenames()

        # For each output file name, assign the final file name matching the
        # expected conventions
        for output_product in output_products:
            self._assign_filename(output_product, self.runconfig.output_product_path)

        # Write the catalog metadata to disk with the appropriate filename
        catalog_metadata = self._create_catalog_metadata()

        if not catalog_metadata.validate(catalog_metadata.get_schema_file_path()):
            msg = f"Failed to create valid catalog metadata, reason(s):\n {catalog_metadata.get_error_msg()}"
            self.logger.critical(self.name, ErrorCode.INVALID_CATALOG_METADATA, msg)

        cat_meta_filename = self._catalog_metadata_filename()
        cat_meta_filepath = join(self.runconfig.output_product_path, cat_meta_filename)

        self.logger.info(self.name, ErrorCode.CREATING_CATALOG_METADATA,
                         f"Writing Catalog Metadata to {cat_meta_filepath}")

        try:
            catalog_metadata.write(cat_meta_filepath)
        except OSError as err:
            msg = f"Failed to write catalog metadata file {cat_meta_filepath}, reason: {str(err)}"
            self.logger.critical(self.name, ErrorCode.CATALOG_METADATA_CREATION_FAILED, msg)

        # Generate the ISO metadata for use with product submission to DAAC(s)
        # For CSLC-S1, each burst-based product gets its own ISO xml
        for burst_id, burst_metadata in self._burst_metadata_cache.items():
            iso_metadata = self._create_iso_metadata(burst_metadata)

            iso_meta_filename = self._iso_metadata_filename(burst_id)
            iso_meta_filepath = join(self.runconfig.output_product_path, iso_meta_filename)

            if iso_metadata:
                self.logger.info(self.name, ErrorCode.RENDERING_ISO_METADATA,
                                 f"Writing ISO Metadata to {iso_meta_filepath}")
                with open(iso_meta_filepath, 'w', encoding='utf-8') as outfile:
                    outfile.write(iso_metadata)

        # Write the QA application log to disk with the appropriate filename,
        # if necessary
        if self.runconfig.qa_enabled:
            qa_log_filename = self._qa_log_filename()
            qa_log_filepath = join(self.runconfig.output_product_path, qa_log_filename)
            self.qa_logger.move(qa_log_filepath)

            try:
                self._finalize_log(self.qa_logger)
            except OSError as err:
                msg = f"Failed to write QA log file to {qa_log_filepath}, reason: {str(err)}"
                self.logger.critical(self.name, ErrorCode.LOG_FILE_CREATION_FAILED, msg)

        # Lastly, write the combined PGE/SAS log to disk with the appropriate filename
        log_filename = self._log_filename()
        log_filepath = join(self.runconfig.output_product_path, log_filename)
        self.logger.move(log_filepath)

        try:
            self._finalize_log(self.logger)
        except OSError as err:
            msg = f"Failed to write log file to {log_filepath}, reason: {str(err)}"

            # Log stream might be closed by this point so raise an Exception instead
            raise RuntimeError(msg)

    def run_postprocessor(self, **kwargs):
        """
        Executes the post-processing steps for the CSLC-S1 PGE.

        The CslcS1PostProcessorMixin version of this method performs the same
        steps as the base PostProcessorMixin, but inserts a step to perform
        output product validation prior to staging and renaming of the output
        files.

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the post-processor

        """
        print(f'Running postprocessor for {self._post_mixin_name}')

        self._run_sas_qa_executable()
        self._validate_output()
        self._stage_output_files()


class CslcS1Executor(CslcS1PreProcessorMixin, CslcS1PostProcessorMixin, PgeExecutor):
    """
    Main class for execution of the CSLC-S1 PGE, including the SAS layer.

    This class essentially rolls up the CSLC-specific pre- and post-processor
    functionality, while inheriting all other functionality for setup and execution
    of the SAS from the base PgeExecutor class.

    """

    NAME = "CSLC-S1"
    """Short name for the CSLC-S1 PGE"""

    LEVEL = "L2"
    """Processing Level for CSLC-S1 Products"""

    PGE_VERSION = "2.1.1"
    """Version of the PGE (overrides default from base_pge)"""

    SAS_VERSION = "0.5.5"  # Final release https://github.com/opera-adt/COMPASS/releases/tag/v0.5.5
    """Version of the SAS wrapped by this PGE, should be updated as needed"""

    def __init__(self, pge_name, runconfig_path, **kwargs):
        super().__init__(pge_name, runconfig_path, **kwargs)

        self.rename_by_pattern_map = {
            't*.h5': self._h5_filename,
            'static_layers*.h5': self._static_layers_filename,
            '*.png': self._browse_filename,
            '*.slc': self._geotiff_filename,
            '*.tif*': self._geotiff_filename,
            '*.json': self._json_metadata_filename
        }
