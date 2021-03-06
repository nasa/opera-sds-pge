#!/usr/bin/env python3

"""
================
test_dswx_pge.py
================

Unit tests for the pge/dswx_pge.py module.
"""
import glob
import os
import re
import tempfile
import unittest
from io import StringIO
from os.path import abspath, join
from unittest.mock import patch

from pkg_resources import resource_filename

import yaml

import opera.util.img_utils
from opera.pge import DSWxExecutor, RunConfig
from opera.util import PgeLogger
from opera.util.img_utils import MockGdal


class DSWxPgeTestCase(unittest.TestCase):
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
        cls.data_dir = join(cls.test_dir, os.pardir, "data")

        os.chdir(cls.test_dir)

    @classmethod
    def tearDownClass(cls) -> None:
        """At completion re-establish starting directory"""
        os.chdir(cls.starting_dir)

    def setUp(self) -> None:
        """Use the temporary directory as the working directory"""
        self.working_dir = tempfile.TemporaryDirectory(
            prefix="test_dswx_pge_", suffix='_temp', dir=os.curdir
        )

        # Create the input dir expected by the test RunConfig and add a dummy
        # input file for validation
        input_dir = join(self.working_dir.name, "dswx_pge_test/input_dir")
        os.makedirs(input_dir, exist_ok=True)

        self.input_file = tempfile.NamedTemporaryFile(
            dir=input_dir, prefix="test_input", suffix=".tif"
        )
        os.chdir(self.working_dir.name)

    def tearDown(self) -> None:
        """Return to starting directory"""
        os.chdir(self.test_dir)
        self.input_file.close()
        self.working_dir.cleanup()

    @patch.object(opera.util.img_utils, "gdal", MockGdal)
    def test_dswx_pge_execution(self):
        """
        Test execution of the DSWxExecutor class and its associated mixins using
        a test RunConfig that creates a dummy expected output file and logs a
        message to be captured by PgeLogger.

        """
        runconfig_path = join(self.data_dir, 'test_dswx_hls_config.yaml')

        pge = DSWxExecutor(pge_name="DSWxPgeTest", runconfig_path=runconfig_path)

        # Check that basic attributes were initialized
        self.assertEqual(pge.name, "DSWx")
        self.assertEqual(pge.pge_name, "DSWxPgeTest")
        self.assertEqual(pge.runconfig_path, runconfig_path)

        # Check that other objects have not been instantiated yet
        self.assertIsNone(pge.runconfig)
        self.assertIsNone(pge.logger)

        # Kickoff execution of DSWx PGE
        pge.run()

        # Check that the runconfig and logger were instantiated
        self.assertIsInstance(pge.runconfig, RunConfig)
        self.assertIsInstance(pge.logger, PgeLogger)

        # Check that directories were created according to RunConfig
        self.assertTrue(os.path.isdir(pge.runconfig.output_product_path))
        self.assertTrue(os.path.isdir(pge.runconfig.scratch_path))

        # Check that an in-memory log was created
        stream = pge.logger.get_stream_object()
        self.assertTrue(isinstance(stream, StringIO))

        # Check that a RunConfig for the SAS was isolated within the scratch directory
        expected_sas_config_file = join(pge.runconfig.scratch_path, 'test_dswx_hls_config_sas.yaml')
        self.assertTrue(os.path.exists(expected_sas_config_file))

        # Check that the catalog metadata file was created in the output directory
        expected_metadata_file = join(
            pge.runconfig.output_product_path, pge._catalog_metadata_filename())
        self.assertTrue(os.path.exists(expected_metadata_file))

        # Check that the ISO metadata file was created and all placeholders were
        # filled in
        expected_iso_metadata_file = join(
            pge.runconfig.output_product_path, pge._iso_metadata_filename())
        self.assertTrue(os.path.exists(expected_iso_metadata_file))

        with open(expected_iso_metadata_file, 'r', encoding='utf-8') as infile:
            iso_contents = infile.read()

        self.assertNotIn('!Not found!', iso_contents)

        # Check that the log file was created and moved into the output directory
        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        # Lastly, check that at least one "image" file was created
        image_files = glob.glob(join(pge.runconfig.output_product_path, "*.tiff"))
        self.assertGreater(len(image_files), 0)

        # Open and read the log
        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn(f"DSWx-HLS invoked with RunConfig {expected_sas_config_file}", log_contents)

    def test_dswx_pge_input_validation(self):
        """Test the input validation checks made by DSWxPreProcessorMixin."""
        runconfig_path = join(self.data_dir, 'test_dswx_hls_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_dswx_runconfig.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as stream:
            runconfig_dict = yaml.safe_load(stream)

        input_files_group = runconfig_dict['RunConfig']['Groups']['PGE']['InputFilesGroup']

        # Test that a non-existent file is detected by pre-processor
        input_files_group['InputFilePaths'] = ['non_existent_file.tif']

        with open(test_runconfig_path, 'w', encoding='utf-8') as input_path:
            yaml.safe_dump(runconfig_dict, input_path, sort_keys=False)

        try:
            pge = DSWxExecutor(pge_name="DSWxPgeTest", runconfig_path=test_runconfig_path)

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
                          f"{abspath('non_existent_file.tif')}", log_contents)

            # Test that an input directory with no .tif files is caught
            input_files_group['InputFilePaths'] = ['dswx_pge_test/scratch_dir']

            with open(test_runconfig_path, 'w', encoding='utf-8') as out_file:
                yaml.safe_dump(runconfig_dict, out_file, sort_keys=False)

            pge = DSWxExecutor(pge_name="DSWxPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f"Input directory {abspath('dswx_pge_test/scratch_dir')} "
                          f"does not contain any tif files", log_contents)

            # Lastly, check that a file that exists but is not a tif is caught
            input_files_group['InputFilePaths'] = [runconfig_path]

            with open(test_runconfig_path, 'w', encoding='utf-8') as runconfig_fh:
                yaml.safe_dump(runconfig_dict, runconfig_fh, sort_keys=False)

            pge = DSWxExecutor(pge_name="DSWxPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f"Input file {abspath(runconfig_path)} does not have "
                          f".tif extension", log_contents)
        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

    def test_dswx_pge_output_validation(self):
        """Test the output validation checks made by DSWxPostProcessorMixin."""
        runconfig_path = join(self.data_dir, 'test_dswx_hls_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_dswx_runconfig.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as stream:
            runconfig_dict = yaml.safe_load(stream)

        primary_executable_group = runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']

        # Test with a SAS command that does not produce any output file,
        # post-processor should detect that expected output is missing
        primary_executable_group['ProgramPath'] = 'echo'
        primary_executable_group['ProgramOptions'] = ['hello world']

        with open(test_runconfig_path, 'w', encoding='utf-8') as config_fh:
            yaml.safe_dump(runconfig_dict, config_fh, sort_keys=False)

        try:
            pge = DSWxExecutor(pge_name="DSWxPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_output_file = 'dswx_pge_test/output_dir/missing_dswx_hls.tif'
            self.assertFalse(os.path.exists(expected_output_file))

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("No SAS output file(s) containing product ID dswx_hls",
                          log_contents)

            # Test with a SAS command that produces the expected output file, but
            # one that is empty (size 0 bytes). Post-processor should detect this
            # and flag an error
            primary_executable_group['ProgramPath'] = 'touch'
            primary_executable_group['ProgramOptions'] = ['dswx_pge_test/output_dir/empty_dswx_hls.tif']

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = DSWxExecutor(pge_name="DSWxPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_output_file = 'dswx_pge_test/output_dir/empty_dswx_hls.tif'
            self.assertTrue(os.path.exists(expected_output_file))

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f"SAS output file {abspath(expected_output_file)} was "
                          f"created, but is empty", log_contents)
        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

    @patch.object(opera.util.img_utils, "gdal", MockGdal)
    def test_geotiff_filename(self):
        """Test _geotiff_filename() method"""
        runconfig_path = join(self.data_dir, 'test_dswx_hls_config.yaml')

        pge = DSWxExecutor(pge_name="DSWxPgeTest", runconfig_path=runconfig_path)

        pge.run()

        image_files = glob.glob(join(pge.runconfig.output_product_path, "*.tif"))

        for i in range(len(image_files)):
            file_name = pge._geotiff_filename(image_files[i])
            md = MockGdal.MockGdalDataset().GetMetadata()
            file_name_regex = rf"{pge.PROJECT}_{pge.LEVEL}_{md['PRODUCT_TYPE']}_{md['PRODUCT_SOURCE']}_" \
                              rf"{md['SPACECRAFT_NAME']}_{md['HLS_DATASET'].split('.')[2]}_\d{{8}}T\d{{6}}_" \
                              rf"{'.'.join(md['HLS_DATASET'].split('.')[-2:])}_\d{{3}}_B\d{{2}}_\w+.tif?"
            self.assertEqual(re.match(file_name_regex, file_name).group(), file_name)


if __name__ == "__main__":
    unittest.main()
