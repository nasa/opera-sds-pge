#!/usr/bin/env python3

"""
==============
tropo_pge.py
==============
Module defining the implementation for the TROPO PGE.
"""

from os.path import abspath, basename, exists, getsize, join, splitext
from os import listdir
import re

from opera.pge.base.base_pge import PgeExecutor
from opera.pge.base.base_pge import PostProcessorMixin
from opera.pge.base.base_pge import PreProcessorMixin
from opera.util.error_codes import ErrorCode
from opera.util.input_validation import check_input
from opera.util.render_jinja2 import augment_hdf5_measured_parameters, render_jinja2
from opera.util.run_utils import get_checksum
from opera.util.h5_utils import get_tropo_product_metadata


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
        the inputs defined within the RunConfig.

        Parameters
        ----------
        **kwargs: dict
            Any keyword arguments needed by the pre-processor
        """
        super().run_preprocessor(**kwargs)
        
        for input_file in self.runconfig.input_files:
            check_input(
                input_file,
                self.logger, 
                self.runconfig.pge_name, 
                valid_extensions=(".nc",), 
                check_zero_size=True
            )


class TROPOPostProcessorMixin(PostProcessorMixin):
    """
    Mixin class responsible for handling all post-processing steps for the TROPO
    PGE. The post-processing phase is defined as all steps required after SAS
    execution has completed, prior to handover of output products to PCM.
    In addition to the base functionality inherited from PostProcessorMixin, this
    mixin adds an output validation step to ensure that the output file(s) defined
    by the RunConfig exist and are valid.
    """

    _post_mixin_name = "TROPOPostProcessorMixin"
    _cached_core_filename = None
    
    _expected_extensions = ('.nc', '.png')
        
    def _validate_outputs(self):
        """
        Confirms that there exists one and only of each expected output type.
        Also confirms that for each output:
        - File has nonzero size
        - Filename matches expected pattern
        """
        filename_pattern = re.compile(
            rf"^OPERA_L4_TROPO-ZENITH_\d{{8}}T\d{{6}}Z_\d{{8}}T\d{{6}}Z_HRES_{re.escape('v' + self.SAS_VERSION)}$"
        )

        output_product_path = abspath(self.runconfig.output_product_path)
        output_product_files = listdir(output_product_path)
        
        # Confirm one and only one of each expected output type
        for filename_ext in self._expected_extensions:
            gen = (f for f in output_product_files if splitext(f)[1] == filename_ext)
            try:
                output_filename = next(gen)
            except StopIteration:
                error_msg = f"Could not locate {filename_ext} file."
                self.logger.critical(self.name, ErrorCode.OUTPUT_NOT_FOUND, error_msg)
                
            # Check for second file, if found raise error
            try:
                next(gen)
                error_msg = f"Found incorrect number of {filename_ext} files."
                self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)
            except StopIteration:
                pass
            
            # Validate the one file found for this extension
            output_filepath = join(output_product_path, output_filename)
            
            # Check file size
            file_size = getsize(output_filepath)
            if not file_size > 0:
                error_msg = (f"Output file {output_filename} size is {file_size}. "
                        "Size must be greater than 0.")
                self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)
            
            # Check filename matches expected pattern
            if not bool(filename_pattern.match(splitext(output_filename)[0])):
                error_msg = f'Invalid product filename {output_filename}'
                self.logger.critical(self.name, ErrorCode.INVALID_OUTPUT, error_msg)
                
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
        filtered_output_products = filter(
            lambda product: splitext(product)[-1] in self._expected_extensions,
            output_products
        )

        # Generate checksums on the filtered product list
        checksums = {
            basename(output_product): get_checksum(output_product)
            for output_product in filtered_output_products
        }

        return checksums

    def _collect_tropo_product_metadata(self, tropo_product):
        '''
         to extract metadata from a product, then creates the Measured Parameters dictionary for 
         use with ISO XML template (see utils.render_jinja2.augment_hdf5_measured_parameters)
        '''
        output_product_metadata = dict()
        
        try:
            measured_parameters = get_tropo_product_metadata(tropo_product)
            output_product_metadata['MeasuredParameters'] = augment_hdf5_measured_parameters(
                measured_parameters,
                self.runconfig.iso_measured_parameter_descriptions,
                self.logger
            )
        except Exception as err:
            msg = f'Failed to extract metadata from {tropo_product}, reason: {err}'
            self.logger.critical(self.name, ErrorCode.ISO_METADATA_COULD_NOT_EXTRACT_METADATA, msg)
    
        return output_product_metadata
    
    def _create_custom_metadata(self, granule_filename):
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
            'ISO_OPERA_FilePackageName': granule_filename,
            'ISO_OPERA_ProducerGranuleId': granule_filename,
            'MetadataProviderAction': "creation",
            'GranuleFilename': granule_filename,
            'ISO_OPERA_ProjectKeywords': ['OPERA', 'JPL', 'DSWx', 'Dynamic', 'Surface', 'Water', 'Extent'],
            'ISO_OPERA_PlatformKeywords': ['TROPO'],
            'ISO_OPERA_InstrumentKeywords': ['TROPO']
        }

        return custom_metadata
    
    def _create_iso_metadata(self, tropo_metadata):
        """
        Creates a rendered version of the ISO metadata template for TROPO
        output products using metadata from the following locations:

            * RunConfig (in dictionary form)
            * Output product (dictionary extracted from NetCDF product attributes)
            * Catalog metadata
            * "Custom" metadata (all metadata not found anywhere else)

        Parameters
        ----------
        tropo_metadata : dict
            The product metadata corresponding to a NetCDF product to
            be included as the "product_output" metadata in the rendered ISO xml.

        Returns
        -------
        rendered_template : str
            The ISO metadata template for TROPO filled in with values from the
            sourced metadata dictionaries.

        """
        # Use the base PGE implemenation to validate existence of the template
        super()._create_iso_metadata()
        
        granule_filename = self._cached_core_filename

        runconfig_dict = self.runconfig.asdict()

        product_output_dict = tropo_metadata

        catalog_metadata_dict = self._create_catalog_metadata().asdict()

        custom_data_dict = self._create_custom_metadata(granule_filename)

        iso_metadata = {
            'run_config': runconfig_dict,
            'product_output': product_output_dict,
            'catalog_metadata': catalog_metadata_dict,
            'custom_data': custom_data_dict
        }

        iso_template_path = abspath(self.runconfig.iso_template_path)

        rendered_template = render_jinja2(iso_template_path, iso_metadata, self.logger)

        return rendered_template    
    
    def _stage_output_files(self):
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

        tropo_metadata = self._collect_tropo_product_metadata()

        # Generate the ISO metadata for use with product submission to DAAC(s)
        iso_metadata = self._create_iso_metadata(tropo_metadata)

        iso_meta_filename = self._iso_metadata_filename()
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
        Executes the post-processing steps for the TROPO PGE.
        The TROPOPostProcessorMixin version of this method performs the same
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
        self._validate_outputs()
        self._stage_output_files()
        


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

    PGE_VERSION = "3.0.0-er.2.0"
    """Version of the PGE"""

    SAS_VERSION = "0.2"
    """Version of the SAS wrapped by this PGE, should be updated as needed"""

    def __init__(self, pge_name, runconfig_path, **kwargs):
        super().__init__(pge_name, runconfig_path, **kwargs)

        self.rename_by_pattern_map = {}
