#!/usr/bin/env python3

"""
===================
test_dist_s1_pge.py
===================
Unit tests for the pge/dist_s1/dist_s1_pge.py module.
"""

import os
import random
import shutil
import tempfile
import unittest
from io import StringIO
from os.path import abspath, join
from pathlib import Path

import yaml
from pkg_resources import resource_filename

from opera.pge import RunConfig
from opera.pge.dist_s1.dist_s1_pge import DistS1Executor
from opera.util import PgeLogger


class DistS1PgeTestCase(unittest.TestCase):
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
            prefix="test_dist_s1_pge_", suffix="_temp", dir=os.curdir
        )

        # Create the input dir expected by the test RunConfig and add a
        # dummy input file
        input_dir = join(self.working_dir.name, "dist_s1_pge_test/input_dir")
        os.makedirs(input_dir, exist_ok=True)

        self.input_file = tempfile.NamedTemporaryFile(
            dir=input_dir, prefix="test_input_", suffix=".tif"
        )

        os.chdir(self.working_dir.name)

    def tearDown(self) -> None:
        """Return to starting directory"""
        os.chdir(self.test_dir)
        self.input_file.close()
        self.working_dir.cleanup()

    @staticmethod
    def _create_dummy_input_files(run_config_path):
        """
        Create dummy input files in the working directory based on the inputs
        section of a RunConfig
        """
        rc = RunConfig(run_config_path)

        for file in rc.input_files:
            Path(file).parent.mkdir(parents=True, exist_ok=True)
            with open(file, "wb") as f:
                f.write(random.randbytes(1024))

    def test_dist_s1_pge_execution(self):
        """
        Test execution of the DistS1Executor class and its associated mixins
        using a test RunConfig that creates dummy expected output files and logs
        a message to be captured by PgeLogger.
        """
        runconfig_path = join(self.data_dir, 'test_dist_s1_config.yaml')

        DistS1PgeTestCase._create_dummy_input_files(runconfig_path)

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

        # Check that the log file was created and moved into the output directory
        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

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


if __name__ == "__main__":
    unittest.main()
