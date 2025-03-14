#!/usr/bin/env python3

"""
===================
test_dist_s1_pge.py
===================
Unit tests for the pge/dist_s1/dist_s1_pge.py module.
"""

import glob
import os
import random
import shutil
import tempfile
import unittest
from copy import deepcopy
from io import StringIO
from os.path import abspath, join
from pathlib import Path
from unittest.mock import patch

import yaml
from pkg_resources import resource_filename

import opera.util.tiff_utils
from opera.pge import RunConfig
from opera.pge.dist_s1.dist_s1_pge import DistS1Executor
from opera.util import PgeLogger
from opera.util.mock_utils import MockGdal
from opera.util.render_jinja2 import UNDEFINED_ERROR


class DistS1PgeTestCase(unittest.TestCase):
    """Base test class using unittest"""

    starting_dir = None
    working_dir = None
    test_dir = None

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
            prefix="test_dist_s1_pge_", suffix="_temp", dir=os.curdir
        )

        # Create the input dir expected by the test RunConfig and add a
        # dummy input file
        input_dir = join(self.working_dir.name, "dist_s1_pge_test/input_dir")
        os.makedirs(input_dir, exist_ok=True)

        # Create dummy input files based on the test run config
        runconfig_path = join(self.data_dir, 'test_dist_s1_config.yaml')
        self._create_dummy_input_files(runconfig_path)

        # Create the output directories expected by the test Runconfig file
        self.test_output_dir = abspath(join(self.working_dir.name, "dist_s1_pge_test/output_dir"))
        os.makedirs(self.test_output_dir, exist_ok=True)
        os.chdir(self.working_dir.name)

    def tearDown(self) -> None:
        """Return to starting directory"""
        os.chdir(self.test_dir)
        self.working_dir.cleanup()

    def _create_dummy_input_files(self, run_config_path):
        """
        Create dummy input files in the working directory based on the inputs
        section of a RunConfig
        """
        rc = RunConfig(run_config_path)

        for file in rc.input_files:
            dummy_file_path = join(self.working_dir.name, file)

            Path(dummy_file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(dummy_file_path, "wb") as f:
                f.write(random.randbytes(1024))

    def generate_band_data_output(self, product_id, band_data, empty_file=False, clear=True):
        """
        Add files to the output directory.

        Parameters
        ----------
        product_id: str
            Product ID to create the output files for.
        band_data: tuple of str
            Files to add to the output directory.
        empty_file: bool
            if 'True' do not add text to the file (leave empty)
            if 'False' (default) add 'Test data string' to the file
        clear : bool
            Clear the output directory before writing new files (default=True)

        """
        # example of band data passed to method:
        # band_data = ('OPERA_L3_DIST-S1_DATE-FIRST.tif', 'OPERA_L3_DIST-S1_DATE-LATEST.tif',
        #              'OPERA_L3_DIST-S1_DIST-STATUS-ACQ.tif', 'OPERA_L3_DIST-S1_DIST-STATUS.tif',
        #              'OPERA_L3_DIST-S1_GEN-METRIC.tif', 'OPERA_L3_DIST-S1_N-DIST.tif',
        #              'OPERA_L3_DIST-S1_N-OBS.tif')

        dir_path = join(self.test_output_dir, product_id)

        if clear:
            if os.path.exists(dir_path):
                shutil.rmtree(dir_path)

        # Add files to the output directory
        for band_output_file in band_data:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            if not empty_file:
                os.system(f"echo 'Test data string' >> {join(dir_path, band_output_file)}")
            else:
                os.system(f"touch {join(dir_path, band_output_file)}")

    @patch.object(opera.util.tiff_utils, "gdal", MockGdal)
    def test_dist_s1_pge_execution(self):
        """
        Test execution of the DistS1Executor class and its associated mixins
        using a test RunConfig that creates dummy expected output files and logs
        a message to be captured by PgeLogger.
        """
        runconfig_path = join(self.data_dir, 'test_dist_s1_config.yaml')

        pge = DistS1Executor(pge_name="DistS1PgeTest", runconfig_path=runconfig_path)

        # Check that basic attributes were initialized
        self.assertEqual(pge.name, "DIST-S1")
        self.assertEqual(pge.pge_name, "DistS1PgeTest")
        self.assertEqual(pge.runconfig_path, runconfig_path)

        # Check that other objects have not been instantiated yet
        self.assertIsNone(pge.runconfig)
        self.assertIsNone(pge.logger)

        # Kickoff execution of DIST-S1 PGE
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
        expected_sas_config_file = join(pge.runconfig.scratch_path, 'test_dist_s1_config_sas.yaml')
        self.assertTrue(os.path.exists(expected_sas_config_file))

        # Check that the catalog metadata file was created in the output directory
        expected_catalog_metadata_file = join(
            pge.runconfig.output_product_path, pge._catalog_metadata_filename())
        self.assertTrue(os.path.exists(expected_catalog_metadata_file))

        # # Check that the ISO metadata file was created and filled in as expected
        expected_iso_metadata_file = join(
            pge.runconfig.output_product_path, pge._iso_metadata_filename())
        self.assertTrue(os.path.exists(expected_iso_metadata_file))

        with open(expected_iso_metadata_file, 'r', encoding='utf-8') as infile:
            iso_contents = infile.read()

        self.assertNotIn(UNDEFINED_ERROR, iso_contents)

        # Check that the log file was created and moved into the output directory
        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        # Lastly, check that the dummy output products were created
        tif_files = glob.glob(join(pge.runconfig.output_product_path, "*.tif"))
        self.assertEqual(len(tif_files), 7)

        # Open and read the log
        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn(f"DIST-S1 invoked with RunConfig {expected_sas_config_file}", log_contents)

    def test_dist_s1_pge_input_validation(self):
        """Test the input validation checks made by DistS1PreProcessorMixin."""
        runconfig_path = join(self.data_dir, 'test_dist_s1_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_dist_s1_runconfig.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as stream:
            runconfig_dict = yaml.safe_load(stream)

        input_files_group = runconfig_dict['RunConfig']['Groups']['PGE']['InputFilesGroup']

        Path('temp').mkdir(parents=True, exist_ok=True)

        # Test that a non-existent file path is detected by pre-processor
        input_files_group['InputFilePaths'] = ['temp/non_existent_file.tif']

        try:
            with open(test_runconfig_path, 'w', encoding='utf-8') as input_path:
                yaml.safe_dump(runconfig_dict, input_path, sort_keys=False)

            pge = DistS1Executor(pge_name="DistS1PgeTest", runconfig_path=test_runconfig_path)

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

            self.assertIn(f"Could not locate specified input "
                          f"{input_files_group['InputFilePaths'][0]}", log_contents)

            # Test that invalid file types are detected by pre-processor
            input_files_group['InputFilePaths'] = ['temp/wrong_input_type.h5']

            with open(input_files_group['InputFilePaths'][0], 'wb') as fp:
                fp.write(random.randbytes(1024))

            with open(test_runconfig_path, 'w', encoding='utf-8') as input_path:
                yaml.safe_dump(runconfig_dict, input_path, sort_keys=False)

            pge = DistS1Executor(pge_name="DistS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f'Input file {input_files_group["InputFilePaths"][0]} does not have an expected file '
                          f'extension.', log_contents)

            # Test that empty files are detected by pre-processor
            input_files_group['InputFilePaths'] = ['temp/empty.tif']

            os.system(
                f"touch {input_files_group['InputFilePaths'][0]}"
            )

            with open(test_runconfig_path, 'w', encoding='utf-8') as input_path:
                yaml.safe_dump(runconfig_dict, input_path, sort_keys=False)

            pge = DistS1Executor(pge_name="DistS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f'Input file {input_files_group["InputFilePaths"][0]} size is 0. Size must be '
                          f'greater than 0.', log_contents)
        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

            if os.path.exists('temp'):
                shutil.rmtree('temp')

    def test_dist_s1_pge_input_rtc_validations(self):
        """Test the input RTC validation checks made by DistS1PreProcessorMixin."""
        runconfig_path = join(self.data_dir, 'test_dist_s1_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_dist_s1_runconfig.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as stream:
            runconfig_dict = yaml.safe_load(stream)

        backup_runconfig = deepcopy(runconfig_dict)

        try:
            Path('temp').mkdir(parents=True, exist_ok=True)

            # Test 1: Detect co/crosspol length mismatch

            s1_file = 'temp/OPERA_L2_RTC-S1_T137-292325-IW1_20241022T015921Z_20241022T180523Z_S1A_30_v1.0_VV.tif'

            runconfig_dict['RunConfig']['Groups']['PGE']['InputFilesGroup']['InputFilePaths'].append(s1_file)
            runconfig_dict['RunConfig']['Groups']['SAS']['run_config']['pre_rtc_copol'].append(s1_file)

            with open(s1_file, 'wb') as fp:
                fp.write(random.randbytes(1024))

            with open(test_runconfig_path, 'w', encoding='utf-8') as input_path:
                yaml.safe_dump(runconfig_dict, input_path, sort_keys=False)

            pge = DistS1Executor(pge_name="DistS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            # Open the log file, and check that the validation error details were captured
            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f"Lengths of input pre/post co/cross pol input RTC lists differ", log_contents)

            # Test 2: Detect SAS RTCs not subset of PGE RTCs

            runconfig_dict = deepcopy(backup_runconfig)

            runconfig_dict['RunConfig']['Groups']['PGE']['InputFilesGroup']['InputFilePaths'] = (
                runconfig_dict['RunConfig']['Groups']['PGE']['InputFilesGroup']['InputFilePaths'])[1:]

            with open(test_runconfig_path, 'w', encoding='utf-8') as input_path:
                yaml.safe_dump(runconfig_dict, input_path, sort_keys=False)

            pge = DistS1Executor(pge_name="DistS1PgeTest", runconfig_path=test_runconfig_path)

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

            self.assertIn(f"SAS RTC file groups do not make a subset of PGE Input Files", log_contents)

            # Test 3: Detect if input RTC sensors are heterogeneous

            runconfig_dict = deepcopy(backup_runconfig)

            s1c_file = 'temp/OPERA_L2_RTC-S1_T137-292325-IW1_20241022T015921Z_20241022T180523Z_S1C_30_v1.0_VV.tif'

            runconfig_dict['RunConfig']['Groups']['PGE']['InputFilesGroup']['InputFilePaths'][0] = s1c_file
            runconfig_dict['RunConfig']['Groups']['SAS']['run_config']['pre_rtc_copol'][0] = s1c_file

            with open(s1c_file, 'wb') as fp:
                fp.write(random.randbytes(1024))

            with open(test_runconfig_path, 'w', encoding='utf-8') as input_path:
                yaml.safe_dump(runconfig_dict, input_path, sort_keys=False)

            pge = DistS1Executor(pge_name="DistS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            # Open the log file, and check that the validation error details were captured
            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f"RunConfig contains RTCs from more than one S1 Sensor", log_contents)

            # Test 4: Incorrect RTC file names

            runconfig_dict = deepcopy(backup_runconfig)

            s1c_file = 'temp/non_standard_rtc_name.tif'

            runconfig_dict['RunConfig']['Groups']['PGE']['InputFilesGroup']['InputFilePaths'][0] = s1c_file
            runconfig_dict['RunConfig']['Groups']['SAS']['run_config']['pre_rtc_copol'][0] = s1c_file

            with open(s1c_file, 'wb') as fp:
                fp.write(random.randbytes(1024))

            with open(test_runconfig_path, 'w', encoding='utf-8') as input_path:
                yaml.safe_dump(runconfig_dict, input_path, sort_keys=False)

            pge = DistS1Executor(pge_name="DistS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            # Open the log file, and check that the validation error details were captured
            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f"Invalid RTC filenames in SAS input", log_contents)

            # Test 5a: Badly ordered RTCs - Fixable

            runconfig_dict = deepcopy(backup_runconfig)

            pre_rtc_copol = runconfig_dict['RunConfig']['Groups']['SAS']['run_config']['pre_rtc_copol']
            pre_rtc_copol[0], pre_rtc_copol[1] = pre_rtc_copol[1], pre_rtc_copol[0]

            with open(test_runconfig_path, 'w', encoding='utf-8') as input_path:
                yaml.safe_dump(runconfig_dict, input_path, sort_keys=False)

            pge = DistS1Executor(pge_name="DistS1PgeTest", runconfig_path=test_runconfig_path)
            pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            # Open the log file, and check that the validation error details were captured
            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("One or more of the SAS RTC lists is badly ordered. Attempting to sort them", log_contents)

            # Test 5b: Badly ordered RTCs - Unfixable - Date mismatch

            runconfig_dict = deepcopy(backup_runconfig)

            s1_file = 'temp/OPERA_L2_RTC-S1_T137-292318-IW1_20240904T015859Z_20240904T150822Z_S1A_30_v1.0_VV.tif'

            runconfig_dict['RunConfig']['Groups']['PGE']['InputFilesGroup']['InputFilePaths'][0] = s1_file
            runconfig_dict['RunConfig']['Groups']['SAS']['run_config']['pre_rtc_copol'][0] = s1_file

            with open(s1_file, 'wb') as fp:
                fp.write(random.randbytes(1024))

            with open(test_runconfig_path, 'w', encoding='utf-8') as input_path:
                yaml.safe_dump(runconfig_dict, input_path, sort_keys=False)

            pge = DistS1Executor(pge_name="DistS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            # Open the log file, and check that the validation error details were captured
            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f"Date or burst ID mismatch in pre_rtc copol and crosspol lists", log_contents)

            # Test 5c: Badly ordered RTCs - Unfixable - Burst mismatch

            runconfig_dict = deepcopy(backup_runconfig)

            s1_file = 'temp/OPERA_L2_RTC-S1_T137-292317-IW1_20250102T015857Z_20250102T190143Z_S1A_30_v1.0_VV.tif'

            pre_rtc_copol = runconfig_dict['RunConfig']['Groups']['SAS']['run_config']['pre_rtc_copol']
            pre_rtc_crosspol = runconfig_dict['RunConfig']['Groups']['SAS']['run_config']['pre_rtc_crosspol']

            pge_input_index = len(pre_rtc_copol) + len(pre_rtc_crosspol)

            runconfig_dict['RunConfig']['Groups']['PGE']['InputFilesGroup']['InputFilePaths'][pge_input_index] = s1_file
            runconfig_dict['RunConfig']['Groups']['SAS']['run_config']['post_rtc_copol'][0] = s1_file

            with open(s1_file, 'wb') as fp:
                fp.write(random.randbytes(1024))

            with open(test_runconfig_path, 'w', encoding='utf-8') as input_path:
                yaml.safe_dump(runconfig_dict, input_path, sort_keys=False)

            pge = DistS1Executor(pge_name="DistS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            # Open the log file, and check that the validation error details were captured
            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f"Date or burst ID mismatch in post_rtc copol and crosspol lists", log_contents)

            # Test 6a: crosspol in copol

            runconfig_dict = deepcopy(backup_runconfig)

            pre_rtc_copol = runconfig_dict['RunConfig']['Groups']['SAS']['run_config']['pre_rtc_copol']
            pre_rtc_crosspol = runconfig_dict['RunConfig']['Groups']['SAS']['run_config']['pre_rtc_crosspol']

            pre_rtc_copol[0] = pre_rtc_crosspol[0]

            with open(test_runconfig_path, 'w', encoding='utf-8') as input_path:
                yaml.safe_dump(runconfig_dict, input_path, sort_keys=False)

            pge = DistS1Executor(pge_name="DistS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            # Open the log file, and check that the validation error details were captured
            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f"Found non-copol RTC in copol input list", log_contents)

            # Test 6b: copol in crosspol

            runconfig_dict = deepcopy(backup_runconfig)

            pre_rtc_copol = runconfig_dict['RunConfig']['Groups']['SAS']['run_config']['pre_rtc_copol']
            pre_rtc_crosspol = runconfig_dict['RunConfig']['Groups']['SAS']['run_config']['pre_rtc_crosspol']

            pre_rtc_crosspol[0] = pre_rtc_copol[0]

            with open(test_runconfig_path, 'w', encoding='utf-8') as input_path:
                yaml.safe_dump(runconfig_dict, input_path, sort_keys=False)

            pge = DistS1Executor(pge_name="DistS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            # Open the log file, and check that the validation error details were captured
            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f"Found non-crosspol RTC in crosspol input list", log_contents)
        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

            if os.path.exists('temp'):
                shutil.rmtree('temp')

    @patch.object(opera.util.tiff_utils, "gdal", MockGdal)
    def test_dist_s1_pge_output_validation(self):
        """Test the output validation checks made by DistS1PreProcessorMixin."""
        runconfig_path = join(self.data_dir, 'test_dist_s1_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_dist_s1_runconfig.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as stream:
            runconfig_dict = yaml.safe_load(stream)

        # Test with a SAS command that does not produce any output file,
        # post-processor should detect that expected output is missing
        primary_executable_group = runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']
        primary_executable_group['ProgramPath'] = 'echo'
        primary_executable_group['ProgramOptions'] = ['hello world']

        product_id_1 = 'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1'
        product_id_2 = 'OPERA_L3_DIST-ALERT-S1_T10SGD_20241105T015902Z_20241204T175000Z_S1_30_v0.1'

        sample_bands = [
            # These bands are always created
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1_DIST-GEN-STATUS-ACQ.tif',
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1_DIST-GEN-STATUS.tif',
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1_GEN-METRIC.tif',
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1.png',

            # These bands depend on the conf db
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1_DATE-FIRST.tif',
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1_DATE-LATEST.tif',
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1_N-DIST.tif',
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1_N-OBS.tif',
        ]

        with open(test_runconfig_path, 'w', encoding='utf-8') as config_fh:
            yaml.safe_dump(runconfig_dict, config_fh, sort_keys=False)

        try:
            # Test: No output products
            pge = DistS1Executor(pge_name="DSWxNIPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("Incorrect number of output granules generated: 0",
                          log_contents)

            # Test: Extra output products

            band_data = tuple(sample_bands)

            self.generate_band_data_output(product_id_1, band_data)
            self.generate_band_data_output(product_id_2, band_data)

            pge = DistS1Executor(pge_name="DSWxNIPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("Incorrect number of output granules generated: 2",
                          log_contents)

            self.generate_band_data_output(product_id_2, tuple(), clear=True)

            # Test: Not enough bands

            band_data = tuple(sample_bands[1:])

            self.generate_band_data_output(product_id_1, band_data)

            pge = DistS1Executor(pge_name="DSWxNIPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("Some required output bands are missing: [\'DIST-GEN-STATUS-ACQ\']", log_contents)

            # Test: Invalid band name

            band_data = ('OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.0.1_INVALID.tif',)

            self.generate_band_data_output(product_id_1, band_data)

            pge = DistS1Executor(pge_name="DSWxNIPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f"Invalid product filename {band_data[0]}", log_contents)

            # Test: Invalid extension

            band_data = ('OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.0.1_N-DIST.nc',)

            self.generate_band_data_output(product_id_1, band_data)

            pge = DistS1Executor(pge_name="DSWxNIPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f"Invalid product filename {band_data[0]}", log_contents)

            # Test: Empty files

            band_data = tuple(sample_bands[:1])

            self.generate_band_data_output(product_id_1, band_data, empty_file=True)

            pge = DistS1Executor(pge_name="DSWxNIPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f"Output file {join(self.test_output_dir, product_id_1, band_data[0])} is empty",
                          log_contents)

            self.generate_band_data_output(product_id_2, tuple(), clear=True)
        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)


if __name__ == "__main__":
    unittest.main()
