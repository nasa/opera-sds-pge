#!/usr/bin/env python3

"""
===================
test_dswx_ni_pge.py
===================
Unit tests for the pge/dswx_ni/dswx_ni_pge.py module.
"""

import glob
import os
import shutil
import tempfile
import unittest
from io import StringIO
from os.path import abspath, join
from unittest.mock import patch

from pkg_resources import resource_filename

import yaml

import opera.util.tiff_utils
from opera.pge import RunConfig
from opera.pge.dswx_ni.dswx_ni_pge import DSWxNIExecutor
from opera.util import PgeLogger
from opera.util.input_validation import validate_algorithm_parameters_config
from opera.util.mock_utils import MockGdal


class DswxNIPgeTestCase(unittest.TestCase):
    """Base test class using unittest"""

    starting_dir = None
    working_dir = None
    test_dir = None
    input_file = None

    @classmethod
    def setUpClass(cls) -> None:
        """Set up directories and files for testing"""
        cls.starting_dir = abspath(os.curdir)
        cls.test_dir = resource_filename(__name__, "")
        cls.data_dir = join(cls.test_dir, os.pardir, os.pardir, "data")

        os.chdir(cls.test_dir)

    @classmethod
    def tearDownClass(cls) -> None:
        """At completion re-establish starting directory"""
        os.chdir(cls.starting_dir)

    def setUp(self) -> None:
        """Use the temporary directory as the working directory"""
        self.working_dir = tempfile.TemporaryDirectory(
            prefix="test_dswx_ni_pge_", suffix="_temp", dir=os.curdir
        )

        # Create the input dir expected by the test RunConfig and add a
        # dummy input file
        input_dir = join(self.working_dir.name, "dswx_ni_pge_test/input_dir")
        os.makedirs(input_dir, exist_ok=True)

        # Copy the algorithm_parameters config file into the test input directory.
        shutil.copy(join(self.data_dir, 'test_dswx_ni_algorithm_parameters.yaml'), input_dir)

        # Create the input dir expected by the test RunConfig and add a
        # dummy input file
        self.input_file = tempfile.NamedTemporaryFile(
            dir=input_dir, prefix="test_input_", suffix=".h5"
        )

        # Create dummy versions of the expected ancillary inputs
        for ancillary_file in ('dem.tif', 'worldcover.tif', 'glad_classification.tif',
                               'reference_water.tif', 'shoreline.shp',
                               'shoreline.dbf', 'shoreline.prj',
                               'shoreline.shx', 'hand.tif',
                               'MGRS_tile.sqlite', 'MGRS_tile_collection.sqlite'):
            os.system(
                f"touch {join(input_dir, ancillary_file)}"
            )

        # Create the output directories expected by the test Runconfig file
        self.test_output_dir = abspath(join(self.working_dir.name, "dswx_ni_pge_test/output_dir"))
        os.makedirs(self.test_output_dir, exist_ok=True)
        os.chdir(self.working_dir.name)

    def tearDown(self) -> None:
        """Return to starting directory"""
        os.chdir(self.test_dir)
        self.input_file.close()
        self.working_dir.cleanup()

    def generate_band_data_output(self, band_data, empty_file=False, clear=True):
        """
        Add files to the output directory.

        Parameters
        ----------
        band_data: tuple of str
            Files to add to the output directory.
        empty_file: bool
            if 'True' do not add text to the file (leave empty)
            if 'False' (default) add 'Test data string' to the file
        clear : bool
            Clear the output directory before writing new files (default=True)

        """
        # example of band data passed to method:
        # band_data = ('OPERA_L3_DSWx-NI_band_1_B01_WTR.tif', 'OPERA_L3_DSWx-NI_band_1_B02_BWTR.tif',
        #              'OPERA_L3_DSWx-NI_band_1_B03_CONF.tif', 'OPERA_L3_DSWx-NI_band_2_B01_WTR.tif',
        #              'OPERA_L3_DSWx-NI_band_2_B02_BWTR.tif', 'OPERA_L3_DSWx-NI_band_2_B03_CONF.tif')

        if clear:
            path = self.test_output_dir
            for file_path in glob.glob(f"{path}/*.tif"):
                os.unlink(file_path)

        # Add files to the output directory
        for band_output_file in band_data:
            if not empty_file:
                os.system(f"echo 'Test data string' >> {join(self.test_output_dir, band_output_file)}")
            else:
                os.system(f"touch {join(self.test_output_dir, band_output_file)}")

    def test_dswx_ni_pge_execution(self):
        """
        Test execution of the DswxNIExecutor class and its associated mixins
        using a test RunConfig that creates dummy expected output files and logs
        a message to be captured by PgeLogger.
        """
        runconfig_path = join(self.data_dir, 'test_dswx_ni_config.yaml')

        pge = DSWxNIExecutor(pge_name="DswxNIPgeTest", runconfig_path=runconfig_path)

        # Check that basic attributes were initialized
        self.assertEqual(pge.name, "DSWx-NI")
        self.assertEqual(pge.pge_name, "DswxNIPgeTest")
        self.assertEqual(pge.runconfig_path, runconfig_path)

        # Check that other objects have not been instantiated yet
        self.assertIsNone(pge.runconfig)
        self.assertIsNone(pge.logger)

        # Kickoff execution of DSWx-NI PGE
        pge.run()

        # Check that the runconfig and logger were instantiated
        self.assertIsInstance(pge.runconfig, RunConfig)
        self.assertIsInstance(pge.logger, PgeLogger)

        # Check that directories were created according to RunConfig
        self.assertTrue(os.path.isdir(pge.runconfig.output_product_path))
        self.assertTrue(os.path.isdir(pge.runconfig.scratch_path))

        # Check that an in-memory log was created
        stream = pge.logger.get_stream_object()
        self.assertIsInstance(stream, StringIO)

        # Check that a RunConfig for the SAS was isolated within the scratch directory
        expected_sas_config_file = join(pge.runconfig.scratch_path, 'test_dswx_ni_config_sas.yaml')
        self.assertTrue(os.path.exists(expected_sas_config_file))

        # Check that the catalog metadata file was created in the output directory
        expected_catalog_metadata_file = join(
            pge.runconfig.output_product_path, pge._catalog_metadata_filename())
        self.assertTrue(os.path.exists(expected_catalog_metadata_file))

        # Check that the ISO metadata file was created and filled in as expected
        expected_iso_metadata_file = join(
            pge.runconfig.output_product_path, pge._iso_metadata_filename(tile_id='T11SLS'))
        self.assertTrue(os.path.exists(expected_iso_metadata_file))

        with open(expected_iso_metadata_file, 'r', encoding='utf-8') as infile:
            iso_contents = infile.read()

        self.assertNotIn('!Not found!', iso_contents)

        # Check that the log file was created and moved into the output directory
        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        # Lastly, check that the dummy output products were created
        slc_files = glob.glob(join(pge.runconfig.output_product_path, "*.tif"))
        self.assertEqual(len(slc_files), 5)

        output_browse_files = glob.glob(join(pge.runconfig.output_product_path, "*.png"))
        self.assertEqual(len(output_browse_files), 1)

        # Open and read the log
        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn(f"DSWx-NI invoked with RunConfig {expected_sas_config_file}", log_contents)

    def test_dswx_ni_pge_input_validation(self):
        """Test the input validation checks made by DSWxNIPreProcessorMixin."""
        runconfig_path = join(self.data_dir, 'test_dswx_ni_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_dswx_ni_runconfig.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as stream:
            runconfig_dict = yaml.safe_load(stream)

        input_files_group = runconfig_dict['RunConfig']['Groups']['PGE']['InputFilesGroup']

        # Test that a non-existent file path is detected by pre-processor
        input_files_group['InputFilePaths'] = ['temp/non_existent_file.h5']

        with open(test_runconfig_path, 'w', encoding='utf-8') as input_path:
            yaml.safe_dump(runconfig_dict, input_path, sort_keys=False)

        try:
            pge = DSWxNIExecutor(pge_name="DSWxNIPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            # Config validation occurs before the log is fully initialized, but the
            # initial log file should still exist and contain details of the validation
            # error
            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            # Open the log file, and check that the validation error details were captured
            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f"Could not locate specified input file/directory "
                          f"{abspath('temp/non_existent_file.h5')}", log_contents)

            # Test that an input directory with no .tif files is caught
            input_files_group['InputFilePaths'] = ['dswx_ni_pge_test/scratch_dir']

            with open(test_runconfig_path, 'w', encoding='utf-8') as out_file:
                yaml.safe_dump(runconfig_dict, out_file, sort_keys=False)

            pge = DSWxNIExecutor(pge_name="DSWxNIPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f"Input directory {abspath('dswx_ni_pge_test/scratch_dir')} "
                          f"does not contain any .h5 files", log_contents)

            # Test that an input directory with no .h5 files is caught
            input_files_group['InputFilePaths'] = ['dswx_ni_pge_test/scratch_dir']

            os.system(f"touch {abspath('dswx_ni_pge_test/scratch_dir/test.tiff')}")

            with open(test_runconfig_path, 'w', encoding='utf-8') as out_file:
                yaml.safe_dump(runconfig_dict, out_file, sort_keys=False)

            pge = DSWxNIExecutor(pge_name="DSWxNIPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f"Input directory {abspath('dswx_ni_pge_test/scratch_dir')} "
                          f"does not contain any .h5 files", log_contents)

            # Lastly, check that a file that exists but is not a tif or a h5 is caught
            input_files_group['InputFilePaths'] = [runconfig_path]

            with open(test_runconfig_path, 'w', encoding='utf-8') as runconfig_fh:
                yaml.safe_dump(runconfig_dict, runconfig_fh, sort_keys=False)

            pge = DSWxNIExecutor(pge_name="DSWxNIPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f"Input file {abspath(runconfig_path)} does not have "
                          f"an expected extension", log_contents)

        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

    def test_dswx_ni_pge_output_validation(self):
        """Test the output validation checks made by DSWxNIPostProcessorMixin."""
        runconfig_path = join(self.data_dir, 'test_dswx_ni_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_dswx_ni_runconfig.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as stream:
            runconfig_dict = yaml.safe_load(stream)

        primary_executable_group = runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']

        # Set up an output directory with no .tif files
        band_data = ()
        self.generate_band_data_output(band_data, clear=True)

        # Test with a SAS command that does not produce any output file,
        # post-processor should detect that expected output is missing
        primary_executable_group['ProgramPath'] = 'echo'
        primary_executable_group['ProgramOptions'] = ['hello world']

        with open(test_runconfig_path, 'w', encoding='utf-8') as config_fh:
            yaml.safe_dump(runconfig_dict, config_fh, sort_keys=False)

        try:
            pge = DSWxNIExecutor(pge_name="DSWxNIPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("No SAS output file(s) with '.tif' extension found",
                          log_contents)

            # Test with a SAS command that produces the expected output files, but
            # with empty files (size 0 bytes). Post-processor should detect this
            # and flag an error
            band_data = ('OPERA_L3_DSWx-NI_b1_B01_WTR.tif',)
            self.generate_band_data_output(band_data, empty_file=True, clear=False)

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = DSWxNIExecutor(pge_name="DSWxNIPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_output_file = 'dswx_ni_pge_test/output_dir/OPERA_L3_DSWx-NI_b1_B01_WTR.tif'
            self.assertTrue(os.path.exists(expected_output_file))

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f"SAS output file {abspath(expected_output_file)} was "
                          f"created, but is empty", log_contents)

            # Test a missing band type.  Post-processor should detect this and flag an error
            band_data = ('OPERA_L3_DSWx-NI_b1_B01_WTR.tif', 'OPERA_L3_DSWx-NI_b1_B02_BWTR.tif',
                         'OPERA_L3_DSWx-NI_b1_B03_CONF.tif')
            self.generate_band_data_output(band_data, clear=True)

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = DSWxNIExecutor(pge_name="DSWxNIPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("Invalid SAS output file, wrong number of bands,",
                          log_contents)

            # Test for missing or extra band files
            # Test a misnamed band file.  Post-processor should detect this and flag an error
            band_data = ('OPERA_L3_DSWx-NI_b1_B01_WTR.tif', 'OPERA_L3_DSWx-NI_b1_B02_BWTR.tif',
                         'OPERA_L3_DSWx-NI_b1_B03_CONF.tif', 'OPERA_L3_DSWx-NI_b1_B04_DIAG.tif',
                         'OPERA_L3_DSWx-NI_b1_BROWSE.tif', 'OPERA_L3_DSWx-NI_b2_B01_WTR.tif',
                         'OPERA_L3_DSWx-NI_b2_B02_BWTR.tif', 'OPERA_L3_DSWx-NI_b2_B04_DIAG.tif')
            self.generate_band_data_output(band_data, clear=True)

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = DSWxNIExecutor(pge_name="DSWxNIPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("Missing or extra band files: number of band files per band:",
                          log_contents)

        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

    def test_dswx_ni_pge_validate_output_product_filenames(self):
        """Test the _validate_output_product_filenames() method in DSWxNIPostProcessorMixin."""
        # for the nominal test use the output file names from the test runconfig file.
        runconfig_path = join(self.data_dir, 'test_dswx_ni_config.yaml')

        pge = DSWxNIExecutor(pge_name="DSWxNIPgeTest", runconfig_path=runconfig_path)

        # Running the preprocessor allows the test access to the RunConfig file
        pge.run_preprocessor()

        pge._validate_output_product_filenames()

        # Verify good test data before triggering errors
        band_data = ('OPERA_L3_DSWx-NI_T11SLS_20210101T120000Z_20210101T120000Z_LSAR_30_v1.0_B01_WTR.tif',
                     'OPERA_L3_DSWx-NI_T11SLS_20210101T120000Z_20210101T120000Z_LSAR_30_v1.0_B02_BWTR.tif',
                     'OPERA_L3_DSWx-NI_T11SLS_20210101T120000Z_20210101T120000Z_LSAR_30_v1.0_B03_CONF.tif',
                     'OPERA_L3_DSWx-NI_T11SLS_20210101T120000Z_20210101T120000Z_LSAR_30_v0.1_B04_DIAG.tif',
                     'OPERA_L3_DSWx-NI_T11SLS_20210101T120000Z_20210101T120000Z_LSAR_30_v1.0_BROWSE.tif',
                     'OPERA_L3_DSWx-NI_T11SLS_20210101T120000Z_20210101T120000Z_LSAR_30_v1.0_BROWSE.png')

        self.generate_band_data_output(band_data, clear=True)

        pge = DSWxNIExecutor(pge_name="DSWxNIPgeTest", runconfig_path=runconfig_path)

        pge.run_preprocessor()

        pge._validate_output_product_filenames()

        # Change an extension name to an illegal extension
        band_data = ('OPERA_L3_DSWx-NI_T11SLS_20210101T120000Z_20210101T120000Z_LSAR_30_v1.0_B01_WTR.jpg',
                     'OPERA_L3_DSWx-NI_T11SLS_20210101T120000Z_20210101T120000Z_LSAR_30_v1.0_B02_BWTR.tif',
                     'OPERA_L3_DSWx-NI_T11SLS_20210101T120000Z_20210101T120000Z_LSAR_30_v1.0_B03_CONF.tif',
                     'OPERA_L3_DSWx-NI_T11SLS_20110226T061749Z_20240329T181033Z_LSAR_30_v0.1_B04_DIAG.tif',
                     'OPERA_L3_DSWx-NI_T11SLS_20210101T120000Z_20210101T120000Z_LSAR_30_v1.0_BROWSE.tif',
                     'OPERA_L3_DSWx-NI_T11SLS_20210101T120000Z_20210101T120000Z_LSAR_30_v1.0_BROWSE.png')

        self.generate_band_data_output(band_data, clear=True)

        pge = DSWxNIExecutor(pge_name="DSWxNIPgeTest", runconfig_path=runconfig_path)

        pge.run_preprocessor()

        with self.assertRaises(RuntimeError):
            pge._validate_output_product_filenames()

        # Note: the log files exists because the critical() method in the PgeLogger class save it to disk.
        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn('does not match the output naming convention.', log_contents)

        # This time take out the 'Z' in the last entry
        band_data = ('OPERA_L3_DSWx-NI_T11SLS_20210101T120000Z_20210101T120000Z_LSAR_30_v1.0_B01_WTR.tif',
                     'OPERA_L3_DSWx-NI_T11SLS_20210101T120000Z_20210101T120000Z_LSAR_30_v1.0_B02_BWTR.tif',
                     'OPERA_L3_DSWx-NI_T11SLS_20210101T120000Z_20210101T120000Z_LSAR_30_v1.0_B03_CONF.tif',
                     'OPERA_L3_DSWx-NI_T11SLS_20110226T061749Z_20240329T181033Z_LSAR_30_v0.1_B04_DIAG.tif',
                     'OPERA_L3_DSWx-NI_T11SLS_20210101T120000Z_20210101T120000Z_LSAR_30_v1.0_BROWSE.tif',
                     'OPERA_L3_DSWx-NI_T11SLS_20210101T120000_20210101T120000_LSAR_30_v1.0_BROWSE.png')

        self.generate_band_data_output(band_data, clear=True)

        pge = DSWxNIExecutor(pge_name="DSWxNIPgeTest", runconfig_path=runconfig_path)

        pge.run_preprocessor()

        with self.assertRaises(RuntimeError):
            pge._validate_output_product_filenames()

        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn('does not match the output naming convention.', log_contents)

    @patch.object(opera.util.tiff_utils, "gdal", MockGdal)
    def test_iso_metadata_creation(self):
        """
        Mock ISO metadata is created when the PGE post processor runs.
        Successful creation of metadata is verified in test_dswx_ni_pge_execution().
        This test will verify that error conditions are caught.
        """
        runconfig_path = join(self.data_dir, 'test_dswx_ni_config.yaml')

        pge = DSWxNIExecutor(pge_name="DSWxNIPgeTest", runconfig_path=runconfig_path)

        # Run only the pre-processor steps to ingest the runconfig and set
        # up directories
        pge.run_preprocessor()

        output_dir = join(os.curdir, 'dswx_ni_pge_test/output_dir')
        dummy_tif_file = join(
            output_dir, 'OPERA_L3_DSWx-NI_T11SLS_20110226T061749Z_20240329T181033Z_LSAR_30_v0.1_B01_WTR.tif'
        )

        with open(dummy_tif_file, 'w') as outfile:
            outfile.write('dummy dswx data')

        dswx_ni_metadata = pge._collect_dswx_ni_product_metadata(dummy_tif_file)

        # Initialize the core filename for the catalog metadata generation step
        pge._core_filename()

        # Render ISO metadata using the sample metadata
        iso_metadata = pge._create_iso_metadata(dswx_ni_metadata)

        # Rendered template should not have any missing placeholders
        self.assertNotIn('!Not found!', iso_metadata)

        # Test bad iso_template_path
        test_runconfig_path = join(self.data_dir, 'invalid_dswx_ni_runconfig.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)

        primary_executable = runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']
        primary_executable['IsoTemplatePath'] = "pge/dswx_ni/templates/OPERA_ISO_metadata_L3_DSWx_NI_template.xml"

        with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        try:
            pge = DSWxNIExecutor(pge_name="DswxNiPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("Could not load ISO template", log_contents)
        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

        # Test that a non-existent file path is detected by pre-processor
        test_runconfig_path = join(self.data_dir, 'invalid_dswx_hls_runconfig.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as stream:
            runconfig_dict = yaml.safe_load(stream)

        input_files_group = runconfig_dict['RunConfig']['Groups']['PGE']['InputFilesGroup']

        input_files_group['InputFilePaths'] = ['temp/non_existent_file.h5']

        with open(test_runconfig_path, 'w', encoding='utf-8') as input_path:
            yaml.safe_dump(runconfig_dict, input_path, sort_keys=False)

        try:
            pge = DSWxNIExecutor(pge_name="DSWxNIPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()
            # Config validation occurs before the log is fully initialized, but the
            # initial log file should still exist and contain details of the validation
            # error
            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            # Open the log file, and check that the validation error details were captured
            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f"Could not locate specified input file/directory "
                          f"{abspath('temp/non_existent_file.h5')}", log_contents)

        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

    def test_dswx_ni_pge_ancillary_input_validation(self):
        """Test validation checks made on the set of ancillary input files"""
        runconfig_path = join(self.data_dir, 'test_dswx_ni_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_dswx_ni_runconfig.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as stream:
            runconfig_dict = yaml.safe_load(stream)

        ancillary_file_group_dict = \
            runconfig_dict['RunConfig']['Groups']['SAS']['runconfig']['groups']['dynamic_ancillary_file_group']

        # Test an invalid (missing) ancillary file
        ancillary_file_group_dict['dem_file'] = 'non_existent_dem.tif'

        with open(test_runconfig_path, 'w', encoding='utf-8') as input_path:
            yaml.safe_dump(runconfig_dict, input_path, sort_keys=False)

        try:
            pge = DSWxNIExecutor(pge_name="DSWxNiPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            # Config validation occurs before the log is fully initialized, but the
            # initial log file should still exist and contain details of the validation
            # error
            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            # Open the log file, and check that the validation error details were captured
            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("Could not locate specified input non_existent_dem.tif.", log_contents)

            # Reset to valid dem path
            ancillary_file_group_dict['dem_file'] = 'dswx_ni_pge_test/input_dir/dem.tif'

            # Test with an unexpected file extension (should be 'tif', 'tiff', or 'vrt)
            os.system("touch dswx_ni_pge_test/input_dir/worldcover.png")
            ancillary_file_group_dict['worldcover_file'] = 'dswx_ni_pge_test/input_dir/worldcover.png'

            with open(test_runconfig_path, 'w', encoding='utf-8') as input_path:
                yaml.safe_dump(runconfig_dict, input_path, sort_keys=False)

            pge = DSWxNIExecutor(pge_name="DSWxNiPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            # Open the log file, and check that the validation error details were captured
            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))
            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("Input file dswx_ni_pge_test/input_dir/worldcover.png "
                          "does not have an expected file extension.", log_contents)

            # Reset to valid worldcover_file path
            ancillary_file_group_dict['worldcover_file'] = 'dswx_ni_pge_test/input_dir/worldcover.tif'

            # Test with incomplete shoreline shapefile set
            os.system("touch dswx_ni_pge_test/input_dir/missing_shoreline.shp")
            ancillary_file_group_dict['shoreline_shapefile'] = 'dswx_ni_pge_test/input_dir/missing_shoreline.shp'

            with open(test_runconfig_path, 'w', encoding='utf-8') as input_path:
                yaml.safe_dump(runconfig_dict, input_path, sort_keys=False)

            pge = DSWxNIExecutor(pge_name="DSWxNiPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            # Open the log file, and check that the validation error details were captured
            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))
            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("Additional shapefile dswx_ni_pge_test/input_dir/missing_shoreline.dbf "
                          "could not be located", log_contents)
        finally:

            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

    def test_dswx_ni_pge_validate_algorithm_parameters_config(self):
        """Test basic parsing and validation of an algorithm parameters RunConfig file"""
        runconfig_path = join(self.data_dir, 'test_dswx_ni_config.yaml')

        self.runconfig = RunConfig(runconfig_path)

        algorithm_parameters_runconfig = self.runconfig.algorithm_parameters_file_config_path
        algorithm_parameters_schema_path = self.runconfig.algorithm_parameters_schema_path

        pge = DSWxNIExecutor(pge_name="DswxNiPgeTest", runconfig_path=runconfig_path)

        # Kickoff execution of DSWX-NI PGE
        pge.run()

        self.assertEqual(algorithm_parameters_runconfig, pge.runconfig.algorithm_parameters_file_config_path)
        # parse the run config file
        runconfig_dict = self.runconfig._parse_algorithm_parameters_run_config_file \
            (pge.runconfig.algorithm_parameters_file_config_path)  # noqa E211
        # Check the properties of the algorithm parameters RunConfig to ensure they match as expected
        validate_algorithm_parameters_config(
            pge.name,
            algorithm_parameters_schema_path,
            algorithm_parameters_runconfig,
            pge.logger
        )

    @patch.object(opera.util.tiff_utils, "gdal", MockGdal)
    def test_dswx_ni_pge_bad_algorithm_parameters_schema_path(self):
        """
        Test for invalid path in the optional 'AlgorithmParametersSchemaPath'
        section of in the PGE runconfig file.
        section of the runconfig file.  Also test for no AlgorithmParametersSchemaPath
        """
        runconfig_path = join(self.data_dir, 'test_dswx_ni_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_dswx_ni_config.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)

        runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']['AlgorithmParametersSchemaPath'] = \
            'test/data/test_algorithm_parameters_non_existent.yaml'  # noqa E211

        with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        try:
            pge = DSWxNIExecutor(pge_name="DswxNiPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

        # Verify that None is returned when 'AlgorithmParametersSchemaPath' is set to None
        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)

        runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']['AlgorithmParametersSchemaPath'] = None

        with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        try:
            pge = DSWxNIExecutor(pge_name="DswxNiPgeTest", runconfig_path=test_runconfig_path)

            pge.run()

            # Check that the log file was created and moved into the output directory
            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            # Open and read the log
            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("No algorithm_parameters_schema_path provided in runconfig file", log_contents)

        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

    def test_dswx_ni_pge_bad_algorithm_parameters_path(self):
        """Test for invalid path to 'algorithm_parameters' in SAS runconfig file"""
        runconfig_path = join(self.data_dir, 'test_dswx_ni_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_dswx_ni_config.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)

        runconfig_dict['RunConfig']['Groups']['SAS']['runconfig']['groups']['dynamic_ancillary_file_group'] \
            ['algorithm_parameters'] = 'test/data/test_algorithm_parameters_non_existent.yaml'  # noqa E211

        with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        try:
            pge = DSWxNIExecutor(pge_name="DswxNiPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)


if __name__ == "__main__":
    unittest.main()
