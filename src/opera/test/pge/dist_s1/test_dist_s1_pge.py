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
from datetime import datetime
from io import StringIO
from os.path import abspath, basename, dirname, join
from pathlib import Path
from unittest.mock import patch

import yaml
from opera.test import path
from yamale.yamale_error import YamaleError

import opera.util.tiff_utils
from opera.pge import RunConfig
from opera.pge.dist_s1.dist_s1_pge import DistS1Executor
from opera.util import PgeLogger
from opera.util.mock_utils import MockGdal
from opera.util.render_jinja2 import UNDEFINED_ERROR
from opera.util.time import get_time_for_filename


class DistS1PgeTestCase(unittest.TestCase):
    """Base test class using unittest"""

    starting_dir = None
    working_dir = None
    test_dir = None

    @classmethod
    def setUpClass(cls) -> None:
        """Set up directories and files for testing"""
        cls.starting_dir = abspath(os.curdir)
        with path('opera.test.pge', 'dist_s1') as test_dir_path:
            cls.test_dir = str(test_dir_path)
        cls.data_dir = join(cls.test_dir, os.pardir, os.pardir, "data")

        os.chdir(cls.test_dir)

    @classmethod
    def tearDownClass(cls) -> None:
        """At completion re-establish starting directory"""
        os.chdir(cls.starting_dir)

    def setUp(self) -> None:
        """Use the temporary directory as the working directory"""
        self.working_dir = tempfile.TemporaryDirectory(
            prefix="test_dist_s1_pge_", suffix="_temp", dir=abspath(os.curdir)
        )

        # Create the input dir expected by the test RunConfig and add a
        # dummy input file
        self.input_dir = abspath(join(self.working_dir.name, "dist_s1_pge_test/input_dir"))
        os.makedirs(self.input_dir, exist_ok=True)

        # Copy the algorithm_parameters config file into the test input directory.
        shutil.copy(join(self.data_dir, 'test_dist_s1_algorithm_parameters.yaml'), self.input_dir)

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

    def _compare_algorithm_parameters_runconfig_to_expected(self, runconfig):
        self.assertEqual(runconfig['interpolation_method'], 'bilinear')
        self.assertEqual(runconfig['low_confidence_alert_threshold'], 3.8)
        self.assertEqual(runconfig['high_confidence_alert_threshold'], 6.2)
        self.assertEqual(runconfig['device'], 'cpu')
        self.assertFalse(runconfig['apply_despeckling'])
        self.assertTrue(runconfig['apply_logit_to_inputs'])
        self.assertEqual(runconfig['memory_strategy'], 'high')
        self.assertEqual(runconfig['batch_size_for_norm_param_estimation'], 1)
        self.assertEqual(runconfig['stride_for_norm_param_estimation'], 8)
        self.assertEqual(runconfig['n_workers_for_despeckling'], 4)
        self.assertEqual(runconfig['n_workers_for_norm_param_estimation'], 1)
        self.assertFalse(runconfig['tqdm_enabled'])
        self.assertFalse(runconfig['model_compilation'])

    def generate_band_data_output(self, product_id, band_data, directory=None, empty_file=False, clear=True):
        """
        Add files to the output directory.

        Parameters
        ----------
        product_id: str
            Product ID to create the output files for.
        band_data: tuple of str
            Files to add to the output directory.
        directory: str (optional)
            Directory to create the test files in. If not provided, the test case output directory is used.
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

        if directory is None:
            directory = self.test_output_dir

        dir_path = join(directory, product_id)

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
        self.assertEqual(len(tif_files), 10)

        # Open and read the log
        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn(f"DIST-S1 invoked with RunConfig {expected_sas_config_file}", log_contents)

    def test_dist_s1_pge_input_basic_validations(self):
        """Test the input validation checks made by DistS1PreProcessorMixin."""
        runconfig_path = join(self.data_dir, 'test_dist_s1_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_dist_s1_runconfig.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as stream:
            runconfig_dict = yaml.safe_load(stream)

        input_files_group = runconfig_dict['RunConfig']['Groups']['PGE']['InputFilesGroup']

        # Test that a non-existent file path is detected by pre-processor
        input_files_group['InputFilePaths'] = [os.path.join(self.input_dir, 'non_existent_file.tif')]

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
            input_files_group['InputFilePaths'] = [os.path.join(self.input_dir, 'wrong_input_type.h5')]

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
            input_files_group['InputFilePaths'] = [os.path.join(self.input_dir, 'empty.tif')]

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

    def test_dist_s1_pge_input_rtc_validations(self):
        """Test the input RTC validation checks made by DistS1PreProcessorMixin."""
        runconfig_path = join(self.data_dir, 'test_dist_s1_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_dist_s1_runconfig.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as stream:
            runconfig_dict = yaml.safe_load(stream)

        backup_runconfig = deepcopy(runconfig_dict)

        try:
            # Test 1: Detect co/crosspol length mismatch

            s1_file = os.path.join(
                self.input_dir,
                'OPERA_L2_RTC-S1_T137-292325-IW1_20241022T015921Z_20241022T180523Z_S1A_30_v1.0_VV.tif'
            )

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

            self.assertIn(
                f"RunConfig SAS group RTC file lists do not make a subset of PGE group Input File list",
                log_contents
            )

            # Test 3: Detect if input RTC sensors are heterogeneous

            runconfig_dict = deepcopy(backup_runconfig)

            s1c_file = os.path.join(
                self.input_dir,
                'OPERA_L2_RTC-S1_T137-292324-IW1_20241103T015918Z_20241103T071409Z_S1C_30_v1.0_VV.tif'
            )

            pre_rtc_copol = runconfig_dict['RunConfig']['Groups']['SAS']['run_config']['pre_rtc_copol']
            pre_rtc_crosspol = runconfig_dict['RunConfig']['Groups']['SAS']['run_config']['pre_rtc_crosspol']

            pge_input_index = len(pre_rtc_copol) + len(pre_rtc_crosspol)

            runconfig_dict['RunConfig']['Groups']['PGE']['InputFilesGroup']['InputFilePaths'][pge_input_index] = s1c_file
            runconfig_dict['RunConfig']['Groups']['SAS']['run_config']['post_rtc_copol'][0] = s1c_file

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

            s1c_file = os.path.join(self.input_dir, 'non_standard_rtc_name.tif')

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

            self.assertIn(f"Invalid RTC filenames in RunConfig", log_contents)

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

            self.assertIn(
                "One or more of the RunConfig SAS group RTC lists is badly ordered. Attempting to sort them",
                log_contents
            )

            # Test 5b: Badly ordered RTCs - Unfixable - Date mismatch

            runconfig_dict = deepcopy(backup_runconfig)

            s1_file = os.path.join(
                self.input_dir,
                'OPERA_L2_RTC-S1_T137-292318-IW1_20240904T015859Z_20240904T150822Z_S1A_30_v1.0_VV.tif'
            )

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

            s1_file = os.path.join(
                self.input_dir,
                'OPERA_L2_RTC-S1_T137-292317-IW1_20250102T015857Z_20250102T190143Z_S1A_30_v1.0_VV.tif'
            )

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

            # Test 7: duplicate RTCs

            runconfig_dict = deepcopy(backup_runconfig)

            sample_input_rtc = runconfig_dict['RunConfig']['Groups']['SAS']['run_config']['pre_rtc_copol'][-1]
            sample_input_rtc_dir = dirname(sample_input_rtc)
            sample_input_rtc = str(basename(sample_input_rtc))

            duplicate_input_rtc_fields = sample_input_rtc.split('_')
            duplicate_input_rtc_fields[5] = f'{get_time_for_filename(datetime.now())}Z'
            duplicate_copol_rtc = '_'.join(duplicate_input_rtc_fields)

            duplicate_input_rtc_fields[9] = 'VH.tif'
            duplicate_crosspol_rtc = '_'.join(duplicate_input_rtc_fields)

            runconfig_dict['RunConfig']['Groups']['SAS']['run_config']['pre_rtc_copol'].append(
                join(sample_input_rtc_dir, duplicate_copol_rtc)
            )
            runconfig_dict['RunConfig']['Groups']['SAS']['run_config']['pre_rtc_crosspol'].append(
                join(sample_input_rtc_dir, duplicate_crosspol_rtc)
            )

            runconfig_dict['RunConfig']['Groups']['PGE']['InputFilesGroup']['InputFilePaths'].extend([
                join(sample_input_rtc_dir, duplicate_copol_rtc),
                join(sample_input_rtc_dir, duplicate_crosspol_rtc),
            ])

            with open(test_runconfig_path, 'w', encoding='utf-8') as input_path:
                yaml.safe_dump(runconfig_dict, input_path, sort_keys=False)

            self._create_dummy_input_files(test_runconfig_path)

            pge = DistS1Executor(pge_name="DistS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            # Open the log file, and check that the validation error details were captured
            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("Found duplicate RTC product(s) with the following burst ID - acquisition "
                          "time pairs: ", log_contents)
        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

    def test_dist_s1_pge_input_prev_product_validations(self):
        """Test the input previous product validation checks made by DistS1PreProcessorMixin."""
        runconfig_path = join(self.data_dir, 'test_dist_s1_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_dist_s1_runconfig.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as stream:
            runconfig_dict = yaml.safe_load(stream)

        backup_runconfig = deepcopy(runconfig_dict)

        sample_bands = [
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1_GEN-DIST-STATUS.tif',
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1_GEN-DIST-CONF.tif',
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1_GEN-DIST-COUNT.tif',
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1_GEN-DIST-DATE.tif',
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1_GEN-DIST-DUR.tif',
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1_GEN-DIST-LAST-DATE.tif',
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1_GEN-DIST-PERC.tif',
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1_GEN-METRIC-MAX.tif',
        ]

        sample_png = 'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1.png'
        sample_duplicate = 'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20250703T175000Z_S1_30_v0.1_GEN-DIST-DUR.tif'

        sample_product_id = 'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1'

        prev_product_dir = os.path.join(
            self.input_dir,
            sample_product_id
        )

        try:
            # Test 1: Bad or non-existent previous product dir

            runconfig_dict = deepcopy(backup_runconfig)

            bad_product_id = 'previous_dist_product'

            runconfig_dict['RunConfig']['Groups']['SAS']['run_config']['pre_dist_s1_product'] = join(
                self.input_dir,
                bad_product_id
            )

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

            self.assertIn("is not a valid product ID", log_contents)

            runconfig_dict = deepcopy(backup_runconfig)

            runconfig_dict['RunConfig']['Groups']['SAS']['run_config']['pre_dist_s1_product'] = prev_product_dir

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

            self.assertIn(f"Previous product directory {prev_product_dir} does not exist", log_contents)

            # Test 2: Empty files

            self.generate_band_data_output(
                sample_product_id,
                tuple(sample_bands),
                directory=self.input_dir,
                empty_file=True
            )

            pge = DistS1Executor(pge_name="DistS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            # Open the log file, and check that the validation error details were captured
            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("Size must be greater than 0", log_contents)

            # Test 3: Bad extensions

            self.generate_band_data_output(
                sample_product_id,
                tuple(sample_bands + [sample_png]),
                directory=self.input_dir,
                clear=True
            )

            pge = DistS1Executor(pge_name="DistS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            # Open the log file, and check that the validation error details were captured
            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("does not have an expected file extension", log_contents)

            # Test 4: Bad filenames

            invalid_sample_bands = deepcopy(sample_bands)
            invalid_sample_bands[0] = 'gen-dist-status-acq.tif'

            self.generate_band_data_output(
                sample_product_id,
                tuple(invalid_sample_bands),
                directory=self.input_dir,
                clear=True
            )

            pge = DistS1Executor(pge_name="DistS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            # Open the log file, and check that the validation error details were captured
            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("One or more previous-product inputs has an invalid filename", log_contents)

            # Test 5: Wrong number

            invalid_sample_bands = sample_bands[1:]

            self.generate_band_data_output(
                sample_product_id,
                tuple(invalid_sample_bands),
                directory=self.input_dir,
                clear=True
            )

            pge = DistS1Executor(pge_name="DistS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            # Open the log file, and check that the validation error details were captured
            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("Unexpected number of files in previous product", log_contents)

            # Test 6: Incorrect set of layers

            invalid_sample_bands = deepcopy(sample_bands)
            invalid_sample_bands[0] = sample_duplicate

            self.generate_band_data_output(
                sample_product_id,
                tuple(invalid_sample_bands),
                directory=self.input_dir,
                clear=True
            )

            pge = DistS1Executor(pge_name="DistS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            # Open the log file, and check that the validation error details were captured
            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("Incomplete input product provided", log_contents)
        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

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
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1_GEN-DIST-STATUS-ACQ.tif',
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1_GEN-DIST-STATUS.tif',
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1_GEN-METRIC.tif',
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1.png',

            # These bands depend on the conf db
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1_GEN-DIST-CONF.tif',
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1_GEN-DIST-COUNT.tif',
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1_GEN-DIST-DATE.tif',
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1_GEN-DIST-DUR.tif',
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1_GEN-DIST-LAST-DATE.tif',
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1_GEN-DIST-PERC.tif',
            'OPERA_L3_DIST-ALERT-S1_T10SGD_20241103T015902Z_20241204T175000Z_S1_30_v0.1_GEN-METRIC-MAX.tif',
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

            self.assertIn("Some required output bands are missing: [\'GEN-DIST-STATUS-ACQ\']", log_contents)

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

    def test_dist_s1_algorithm_parameters(self):
        """Test basic parsing and validation of an algorithm parameters RunConfig file"""
        runconfig_path = join(self.data_dir, 'test_dist_s1_config.yaml')

        runconfig = RunConfig(runconfig_path)

        algorithm_parameters_runconfig_file = runconfig.sas_config["run_config"].get("algo_config_path", None)

        self.assertIsNotNone(algorithm_parameters_runconfig_file)

        # parse the run config file
        runconfig_dict = runconfig._parse_algorithm_parameters_run_config_file(algorithm_parameters_runconfig_file)

        # Check the properties of the algorithm parameters RunConfig to ensure they match as expected
        self._compare_algorithm_parameters_runconfig_to_expected(runconfig_dict)

    def test_dist_s1_bad_algorithm_parameters(self):
        """Test validation for invalid algorithm parameters files"""
        runconfig_path = join(self.data_dir, 'test_dist_s1_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_ap_dist_s1_runconfig.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as stream:
            runconfig_dict = yaml.safe_load(stream)

        ap_path = join(self.data_dir, 'test_dist_s1_algorithm_parameters.yaml')
        test_ap_path = join(self.data_dir, 'invalid_dist_s1_algorithm_parameters.yaml')

        runconfig_dict['RunConfig']['Groups']['SAS']['run_config']['algo_config_path'] = test_ap_path

        with open(test_runconfig_path, 'w', encoding='utf-8') as stream:
            yaml.safe_dump(runconfig_dict, stream)

        with open(ap_path, 'r', encoding='utf-8') as stream:
            ap_dict = yaml.safe_load(stream)

        backup_ap = deepcopy(ap_dict)

        try:
            ap_dict['unexpected_option'] = 42

            with open(test_ap_path, 'w', encoding='utf-8') as input_path:
                yaml.safe_dump(ap_dict, input_path, sort_keys=False)

            pge = DistS1Executor(pge_name="DistS1PgeTest", runconfig_path=test_runconfig_path)

            err: YamaleError = None

            with self.assertRaises(YamaleError):
                try:
                    pge.run()
                except YamaleError as e:
                    err = e
                    raise

            self.assertIsNotNone(err)
            self.assertIn('unexpected_option: Unexpected element', err.message)

            ap_dict = deepcopy(backup_ap)

            ap_dict['high_confidence_alert_threshold'] = 16.2

            with open(test_ap_path, 'w', encoding='utf-8') as input_path:
                yaml.safe_dump(ap_dict, input_path, sort_keys=False)

            pge = DistS1Executor(pge_name="DistS1PgeTest", runconfig_path=test_runconfig_path)

            err: YamaleError = None

            with self.assertRaises(YamaleError):
                try:
                    pge.run()
                except YamaleError as e:
                    err = e
                    raise

            self.assertIsNotNone(err)
            self.assertIn('high_confidence_alert_threshold: 16.2 is greater than 15.0', err.message)

            ap_dict = deepcopy(backup_ap)

            ap_dict['interpolation_method'] = 'unsupported'

            with open(test_ap_path, 'w', encoding='utf-8') as input_path:
                yaml.safe_dump(ap_dict, input_path, sort_keys=False)

            pge = DistS1Executor(pge_name="DistS1PgeTest", runconfig_path=test_runconfig_path)

            err: YamaleError = None

            with self.assertRaises(YamaleError):
                try:
                    pge.run()
                except YamaleError as e:
                    err = e
                    raise

            self.assertIsNotNone(err)
            self.assertIn("interpolation_method: 'unsupported' not in ('nearest', 'bilinear', 'none')", err.message)

            ap_dict = deepcopy(backup_ap)

            ap_dict['tqdm_enabled'] = 'wrong type'

            with open(test_ap_path, 'w', encoding='utf-8') as input_path:
                yaml.safe_dump(ap_dict, input_path, sort_keys=False)

            pge = DistS1Executor(pge_name="DistS1PgeTest", runconfig_path=test_runconfig_path)

            err: YamaleError = None

            with self.assertRaises(YamaleError):
                try:
                    pge.run()
                except YamaleError as e:
                    err = e
                    raise

            self.assertIsNotNone(err)
            self.assertIn("tqdm_enabled: 'wrong type' is not a bool.", err.message)
        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

            if os.path.exists(test_ap_path):
                os.unlink(test_ap_path)


if __name__ == "__main__":
    unittest.main()
