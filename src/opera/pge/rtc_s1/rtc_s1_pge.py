#!/usr/bin/env python3

"""
=============
rtc_s1_pge.py
=============

Module defining the implementation for the Radiometric Terrain Corrected (RTC)
from Sentinel-1 A/B (S1) PGE.

"""

import os.path
from datetime import datetime
from os import walk
from os.path import basename, getsize, join

from opera.pge.base.base_pge import PgeExecutor
from opera.pge.base.base_pge import PostProcessorMixin
from opera.pge.base.base_pge import PreProcessorMixin
from opera.util.error_codes import ErrorCode
from opera.util.input_validation import validate_slc_s1_inputs
from opera.util.metadata_utils import get_rtc_s1_product_metadata
from opera.util.metadata_utils import get_sensor_from_spacecraft_name
from opera.util.render_jinja2 import render_jinja2
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
    by the RunConfig exist and are valid.

    """

    _post_mixin_name = "RtcS1PostProcessorMixin"
    _cached_core_filename = None
    _burst_metadata_cache = {}
    _burst_filename_cache = {}

    def _validate_output(self):
        """
        Evaluates the output file(s) generated from SAS execution to ensure
        the existence of a directory for each burst containing a single output
        file.  Verify each output file exists, is named with the proper extension,
        and is non-zero in size.

        """
        out_dir_walk_dict = {}
        expected_ext = []

        output_dir = os.path.abspath(self.runconfig.output_product_path)
        scratch_dir = os.path.abspath(self.runconfig.scratch_path)

        # from 'output_dir' make a dictionary of {sub_dir_name: [file1, file2,...]}
        for path, dirs, files in walk(output_dir):
            if not dirs and scratch_dir not in path:  # Ignore files in 'output_dir' and scratch directory
                out_dir_walk_dict[basename(path)] = files

        sas_product_group = self.runconfig.sas_config['runconfig']['groups']['product_group']
        output_format = sas_product_group['output_imagery_format']

        if output_format == 'NETCDF':
            expected_ext = ['nc']
        elif output_format == 'HDF5':
            expected_ext = ['h5']
        elif output_format in ('GTiff', 'COG', 'ENVI'):
            expected_ext = ['tiff', 'tif', 'h5']

        save_browse = sas_product_group['save_browse']

        if save_browse:
            expected_ext.append('png')

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
        RTC-S1 PGE.

        The core file name component for RTC-S1 products consists of:

        <PROJECT>_<LEVEL>_<PGE NAME>-<SOURCE>

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

        # Assign the core file to the cached class attribute
        self._cached_core_filename = (
            f"{self.PROJECT}_{self.LEVEL}_{self.NAME}-{self.SOURCE}"
        )

        return self._cached_core_filename

    def _core_static_filename(self, inter_filename=None):
        """
        Returns the core file name component for static layer products produced
        by the RTC-S1 PGE.

        The core file name component for RTC-S1 products consists of:

        <Core filename>-STATIC

        Where <Core filename> is returned by RtcS1PostProcessorMixin._core_filename().

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

    def _rtc_filename(self, inter_filename, static_layer_product=False):
        """
        Returns the base file name to use for RTC products produced by this PGE.

        The base filename for the RTC PGE consists of:

            <Core filename>_<BURST ID>_<ACQUISITION TIME>_<PRODUCTION TIME>_<SENSOR>_<SPACING>_<PRODUCT VERSION>

        Where <Core filename> is returned by RtcS1PostProcessorMixin._core_filename()
        if static_layer_product is False, otherwise it is the value returned by
        RtcS1PostProcessorMixin._core_static_filename()

        If static_layer_product is True, <ACQUISITION TIME> will correspond
        to the configured data validity start time (as defined in the RunConfig).

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the output product to generate
            a filename for. This parameter may be used to inspect the file
            in order to derive any necessary components of the returned filename.
        static_layer_product : bool, optional
            If True, use the file name conventions specific to static layer
            products. Otherwise, use the baseline conventions. Defaults to False.

        Returns
        -------
        rtc_filename : str
            The file name to assign to RTC product(s) created by this PGE.

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

        product_dir = os.path.dirname(inter_filename)

        # Each RTC product is stored in a directory named for the corresponding burst ID
        burst_id = os.path.basename(product_dir)
        burst_id = burst_id.upper().replace('_', '-')

        if burst_id in self._burst_metadata_cache:
            product_metadata = self._burst_metadata_cache[burst_id]
        else:
            metadata_product = None

            # Locate the HDF5 product which contains the RTC metadata
            for output_product in os.listdir(product_dir):
                if output_product.endswith('.nc') or output_product.endswith('.h5'):
                    metadata_product = output_product
                    break
            else:
                msg = (f"Could not find a NetCDF format RTC product to extract "
                       f"metadata from within {self.runconfig.output_product_path}")
                self.logger.critical(self.name, ErrorCode.FILE_MOVE_FAILED, msg)

            product_metadata = self._collect_rtc_product_metadata(
                os.path.join(product_dir, metadata_product)
            )

            self._burst_metadata_cache[burst_id] = product_metadata

        production_time = get_time_for_filename(self.production_datetime)

        if static_layer_product:
            acquisition_time = self.runconfig.data_validity_start_date

            if acquisition_time is None:
                raise ValueError(
                    'static_layer_product was requested, but no value was provided '
                    'for DataValidityStartDate within the RunConfig'
                )
        else:
            # Use doppler start time as the acq time and convert it to our format
            # used for file naming
            acquisition_time = product_metadata['identification']['zeroDopplerStartTime']

            if acquisition_time.endswith('Z'):
                acquisition_time = acquisition_time[:-1]

            acquisition_time = get_time_for_filename(
                datetime.strptime(acquisition_time, "%Y-%m-%dT%H:%M:%S.%f")
            )

            if not acquisition_time.endswith('Z'):
                acquisition_time += 'Z'

        # Get the sensor (should be either S1A or S1B)
        sensor = get_sensor_from_spacecraft_name(product_metadata['identification']['platform'])

        # Spacing is assumed to be identical in both X and Y direction
        spacing = int(product_metadata['data']['xCoordinateSpacing'])

        product_version = str(self.runconfig.product_version)

        if not product_version.startswith('v'):
            product_version = f'v{product_version}'

        rtc_file_components = (
            f"{burst_id}_{acquisition_time}_{production_time}Z_{sensor}_"
            f"{spacing}_{product_version}"
        )

        rtc_filename = f"{core_filename}_{rtc_file_components}"

        # Cache the file name for this burst ID, so it can be used with the ISO
        # metadata later.
        self._burst_filename_cache[burst_id] = rtc_filename

        return rtc_filename

    def _static_layer_filename(self, inter_filename):
        """
        Returns the final file name for the static layer RTC product which
        may be optionally produced by this PGE. There are currently 5 static layer
        products which may be produced by this PGE, each identified by a
        static layer name appended to the end of the intermediate filename.

        The filename for static layer RTC products consists of:

            <RTC static filename>_<Static layer name>.tif

        Where <RTC static filename> is returned by RtcS1PostProcessorMixin._rtc_filename()
        with static_layer_product set to True.
        <Static layer name> is the identifier for the specific static layer
        as parsed from the intermediate filename.

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the static layer output product to generate
            a filename for. This parameter may is used to derive the core RTC
            file name component, to which the particular static layer name (nlooks,
            shadow_mask, etc...) is appended to denote the type.

        Returns
        -------
        static_layer_filename : str
            The file name to assign to static layer GeoTIFF product(s) created
            by this PGE.

        """
        filename, ext = os.path.splitext(basename(inter_filename))

        # The name of the static layer should always follow the product version
        # within the intermediate filename
        sas_product_group = self.runconfig.sas_config['runconfig']['groups']['product_group']
        product_version = str(sas_product_group['product_version'])

        if not product_version.startswith('v'):
            product_version = f"v{product_version}"

        static_layer_name = filename.split(product_version)[-1]

        rtc_filename = self._rtc_filename(inter_filename, static_layer_product=True)

        static_layer_filename = f"{rtc_filename}{static_layer_name}.tif"

        return static_layer_filename

    def _rtc_geotiff_filename(self, inter_filename):
        """
        Returns the file name to use for GeoTIFF format RTC products produced
        by this PGE.

        The filename for GeoTIFF RTC products consists of:

            <RTC filename>_<POLARIZATION>.tif

        Where <RTC filename> is returned by RtcS1PostProcessorMixin._rtc_filename(),
        and <POLARIZATION> is the polarization value of the GeoTIFF, as extracted from
        inter_filename.

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the output product to generate
            a filename for. This parameter may be used to inspect the file
            in order to derive any necessary components of the returned filename.

        Returns
        -------
        rtc_geotiff_filename : str
            The file name to assign to RTC GeoTIFF product(s) created by this PGE.

        """
        filename, ext = os.path.splitext(basename(inter_filename))

        # For geotiff products, the last field should be the polarization, which
        # needs to be carried over to the applied filename
        polarization = filename.split('_')[-1]

        rtc_filename = self._rtc_filename(inter_filename)

        return f"{rtc_filename}_{polarization}.tif"

    def _mask_filename(self, inter_filename):
        """
        Returns the file name to use for RTC mask products produced by this PGE.

        The filename for GeoTIFF RTC products consists of:

            <RTC filename>_mask.tif

        Where <RTC filename> is returned by RtcS1PostProcessorMixin._rtc_filename().

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the output product to generate
            a filename for. This parameter may be used to inspect the file
            in order to derive any necessary components of the returned filename.

        Returns
        -------
        mask_filename : str
            The file name to assign to RTC GeoTIFF product(s) created by this PGE.

        """
        rtc_filename = self._rtc_filename(inter_filename)

        return f"{rtc_filename}_mask.tif"

    def _browse_filename(self, inter_filename):
        """
        Returns the final file name of the PNG browse image product which may
        be optionally produced by this PGE.

        The filename for RTC browse product consists of:

            <RTC filename>_BROWSE.png

        Where <RTC filename> is returned by RtcS1PostProcessorMixin._rtc_filename().

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the output product to generate
            a filename for. This parameter may be used to inspect the file
            in order to derive any necessary components of the returned filename.

        Returns
        -------
        browse_filename : str
            The file name to assign to browse product created by this PGE.

        """
        rtc_filename = self._rtc_filename(inter_filename)

        browse_filename = f"{rtc_filename}_BROWSE.png"

        return browse_filename

    def _static_browse_filename(self, inter_filename):
        """
        Returns the final file name of the static layer PNG browse image product
        which may be optionally produced by this PGE.

        The filename for the RTC static layer browse product consists of:

            <RTC static filename>_BROWSE.png

        Where <RTC static filename> is returned by RtcS1PostProcessorMixin._rtc_filename()
        with static_layer_product set ot True.

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the output product to generate
            a filename for. This parameter may be used to inspect the file
            in order to derive any necessary components of the returned filename.

        Returns
        -------
        browse_filename : str
            The file name to assign to browse product created by this PGE.

        """
        rtc_filename = self._rtc_filename(inter_filename, static_layer_product=True)

        browse_filename = f"{rtc_filename}_BROWSE.png"

        return browse_filename

    def _rtc_metadata_filename(self, inter_filename):
        """
        Returns the file name to use for RTC metadata products produced by this PGE.

        The filename for RTC metadata products consists of:

            <RTC filename>.<ext>

        Where <RTC filename> is returned by RtcS1PostProcessorMixin._rtc_filename(),
        and <ext> is the file extension carried over from inter_filename (usually
        .h5 or .nc).

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the output product to generate
            a filename for. This parameter may be used to inspect the file
            in order to derive any necessary components of the returned filename.

        Returns
        -------
        rtc_metadata_filename : str
            The file name to assign to RTC metadata product(s) created by this PGE.

        """
        ext = os.path.splitext(inter_filename)[-1]

        rtc_filename = self._rtc_filename(inter_filename)

        return f"{rtc_filename}{ext}"

    def _static_metadata_filename(self, inter_filename):
        """
        Returns the file name to use for RTC metadata products produced by this PGE.

        The filename for RTC metadata products consists of:

            <RTC static filename>.<ext>

        Where <RTC static filename> is returned by RtcS1PostProcessorMixin._rtc_filename()
        with static_layer_product set ot True, and <ext> is the file extension
        carried over from inter_filename (usually .h5 or .nc).

        Parameters
        ----------
        inter_filename : str
            The intermediate filename of the output product to generate
            a filename for. This parameter may be used to inspect the file
            in order to derive any necessary components of the returned filename.

        Returns
        -------
        static_metadata_filename : str
            The file name to assign to static layer metadata product(s) created
            by this PGE.

        """
        ext = os.path.splitext(inter_filename)[-1]

        rtc_filename = self._rtc_filename(inter_filename, static_layer_product=True)

        return f"{rtc_filename}{ext}"

    def _ancillary_filename(self):
        """
        Helper method to derive the core component of the file names for
        the ancillary products associated to a PGE job (catalog metadata, log
        file, etc...).

        The core file name component for RTC-S1 ancillary products consists of:

        <PROJECT>_<LEVEL>_<PGE NAME>-<SOURCE>_<PRODUCTION TIME>_<SENSOR>_<SPACING>_<PRODUCT VERSION>

        Since these files are not specific to any particular burst processed
        for an RTC job, fields such as burst ID and acquisition time are omitted
        from this file pattern.

        Returns
        -------
        ancillary_filename : str
            The file name component to assign to ancillary products created by this PGE.

        """
        # Metadata fields we need for ancillary file name should be equivalent
        # across all bursts, so just take the first set of cached metadata as
        # a representative
        product_metadata = list(self._burst_metadata_cache.values())[0]

        # Get the sensor (should be either S1A or S1B)
        sensor = get_sensor_from_spacecraft_name(product_metadata['identification']['platform'])

        # Spacing is assumed to be identical in both X and Y direction
        spacing = int(product_metadata['data']['xCoordinateSpacing'])

        production_time = get_time_for_filename(self.production_datetime)
        product_version = str(self.runconfig.product_version)

        if not product_version.startswith('v'):
            product_version = f'v{product_version}'

        ancillary_filename = (
            f"{self.PROJECT}_{self.LEVEL}_{self.NAME}-{self.SOURCE}_"
            f"{production_time}Z_{sensor}_{spacing}_{product_version}"
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

    def _iso_metadata_filename(self, burst_id):
        """
        Returns the file name to use for ISO Metadata produced by the RTC-S1 PGE.

        The ISO Metadata file name for the RTC-S1 PGE consists of:

            <RTC filename>.iso.xml

        Where <RTC filename> is returned by RtcS1PostProcessorMixin._rtc_filename()

        Parameters
        ----------
        burst_id : str
            The burst identifier used to look up the corresponding cached RTC
            filename.

        Returns
        -------
        iso_metadata_filename : str
            The file name to assign to the ISO Metadata product created by this PGE.

        """
        if burst_id not in self._burst_filename_cache:
            raise RuntimeError(f"No file name cached for burst ID {burst_id}")

        iso_metadata_filename = self._burst_filename_cache[burst_id]

        return iso_metadata_filename + ".iso.xml"

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

    def _collect_rtc_product_metadata(self, metadata_product):
        """
        Gathers the available metadata from an HDF5 product created by
        the RTC-S1 SAS. This metadata is then formatted for use with filling in
        the ISO metadata template for the RTC-S1 PGE.

        Parameters
        ----------
        metadata_product : str
            Path the HDF5/NETCDF metadata product to collect metadata from.

        Returns
        -------
        output_product_metadata : dict
            Dictionary containing RTC-S1 output product metadata, formatted for
            use with the ISO metadata Jinja2 template.

        """
        output_product_metadata = get_rtc_s1_product_metadata(metadata_product)

        # Fill in some additional fields expected within the ISO
        output_product_metadata['data']['width'] = len(output_product_metadata['data']
                                                       ['xCoordinates'])
        output_product_metadata['data']['length'] = len(output_product_metadata['data']
                                                        ['yCoordinates'])

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
            'ISO_OPERA_FilePackageName': self._ancillary_filename(),
            'ISO_OPERA_ProducerGranuleId': self._ancillary_filename(),
            'MetadataProviderAction': "creation",
            'GranuleFilename': self._ancillary_filename(),
            'ISO_OPERA_ProjectKeywords': ['OPERA', 'JPL', 'RTC', 'Radiometric', 'Terrain', 'Corrected'],
            'ISO_OPERA_PlatformKeywords': ['S1'],
            'ISO_OPERA_InstrumentKeywords': ['Sentinel 1 A/B']
        }

        return custom_metadata

    def _create_iso_metadata(self, burst_metadata):
        """
        Creates a rendered version of the ISO metadata template for RTC-S1
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
            The ISO metadata template for RTC-S1 filled in with values from the
            sourced metadata dictionaries.

        """
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

        if not os.path.exists(iso_template_path):
            msg = f"Could not load ISO template {iso_template_path}, file does not exist"
            self.logger.critical(self.name, ErrorCode.ISO_METADATA_TEMPLATE_NOT_FOUND, msg)

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
        # For RTC-S1, each burst-based product gets its own ISO xml
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
        Executes the post-processing steps for the RTC-S1 PGE.

        The RtcS1PostProcessorMixin version of this method performs the same
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

    PGE_VERSION = "2.0.0-rc.2.1"
    """Version of the PGE (overrides default from base_pge)"""

    SAS_VERSION = "0.4.1"  # CalVal release https://github.com/opera-adt/RTC/releases/tag/v0.4.1
    """Version of the SAS wrapped by this PGE, should be updated as needed"""

    SOURCE = "S1"

    def __init__(self, pge_name, runconfig_path, **kwargs):
        super().__init__(pge_name, runconfig_path, **kwargs)

        self.rename_by_pattern_map = {
            # Note: Order matters here
            "*_VV.tif": self._rtc_geotiff_filename,
            "*_VH.tif": self._rtc_geotiff_filename,
            "*_HH.tif": self._rtc_geotiff_filename,
            "*_HV.tif": self._rtc_geotiff_filename,
            "*_VV+VH.tif": self._rtc_geotiff_filename,
            "*_HH+HV.tif": self._rtc_geotiff_filename,
            "*-STATIC_*_mask.tif": self._static_layer_filename,
            "*-STATIC_*_rtc_anf*.tif": self._static_layer_filename,
            "*-STATIC_*_number_of_looks.tif": self._static_layer_filename,
            "*-STATIC_*_local_incidence_angle.tif": self._static_layer_filename,
            "*-STATIC_*_incidence_angle.tif": self._static_layer_filename,
            "*-STATIC_*.png": self._static_browse_filename,
            "*-STATIC_*.h5": self._static_metadata_filename,
            "*_mask.tif": self._mask_filename,
            "*.png": self._browse_filename,
            "*.h5": self._rtc_metadata_filename,
            "*.nc": self._rtc_metadata_filename
        }
