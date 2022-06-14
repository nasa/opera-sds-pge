#!/usr/bin/env python3

"""
=================
test_base_pge.py
=================

Unit tests for the pge/base_pge.py module.
"""
import json
import os
import re
import tempfile
import unittest
from io import StringIO
from os.path import abspath, join
from pathlib import Path
from unittest.mock import patch

from pkg_resources import resource_filename

import yaml

import opera
from opera.pge import PgeExecutor, RunConfig
from opera.util import PgeLogger


class BasePgeTestCase(unittest.TestCase):
    """Base test class using unittest"""

    test_dir = None
    starting_dir = None

    @classmethod
    def setUpClass(cls) -> None:
        """Set up class method: set up directories for testing"""
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
            prefix="test_base_pge_", suffix='temp', dir=os.curdir
        )
        os.chdir(self.working_dir.name)

        # Create dummy input files expected by test RunConfigs
        os.mkdir('input')
        Path('input/input_file01.h5').touch()
        Path('input/input_file02.h5').touch()

    def tearDown(self) -> None:
        """Return to starting directory"""
        os.chdir(self.test_dir)
        self.working_dir.cleanup()

    def test_base_pge_execution(self):
        """
        Test execution of the PgeExecutor class and its associated mixins using
        a test RunConfig that invokes "echo hello world" as its configured
        SAS executable.

        """
        runconfig_path = join(self.data_dir, 'test_base_pge_config.yaml')

        pge = PgeExecutor(pge_name='BasePgeTest', runconfig_path=runconfig_path)

        # Check that basic attributes were initialized
        self.assertEqual(pge.name, "BasePge")
        self.assertEqual(pge.pge_name, "BasePgeTest")
        self.assertEqual(pge.runconfig_path, runconfig_path)

        # Check that other objects have not been instantiated yet
        self.assertIsNone(pge.runconfig)
        self.assertIsNone(pge.logger)

        # Kickoff execution of base PGE
        pge.run()

        # Check that runconfig and logger were instantiated as expected
        self.assertIsInstance(pge.runconfig, RunConfig)
        self.assertIsInstance(pge.logger, PgeLogger)

        # Check that directories were created according to RunConfig
        self.assertTrue(os.path.isdir(pge.runconfig.output_product_path))
        self.assertTrue(os.path.isdir(pge.runconfig.scratch_path))

        # Check that an in-memory log was created
        stream_obj = pge.logger.get_stream_object()
        self.assertTrue(isinstance(stream_obj, StringIO))

        # Check that a RunConfig for the SAS was isolated within the scratch directory
        expected_sas_config_file = join(pge.runconfig.scratch_path, 'test_base_pge_config_sas.yaml')
        self.assertTrue(os.path.exists(expected_sas_config_file))

        # Check that the catalog metadata file was created in the output directory
        expected_metadata_file = join(pge.runconfig.output_product_path, pge._catalog_metadata_filename())
        self.assertTrue(os.path.exists(expected_metadata_file))

        # Check that the log file was created into the output directory
        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        # Open the log file, and check that "SAS" output was captured
        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn('hello world', log_contents)

        # Make sure the run time metric was captured as well
        self.assertIn('sas.elapsed_seconds:', log_contents)

    def test_base_pge_w_invalid_runconfig(self):
        """
        Test execution of the PgeExecutor using a RunConfig that will fail
        validation against the base PGE schema.

        """
        runconfig_path = join(self.data_dir, 'invalid_runconfig.yaml')

        pge = PgeExecutor(pge_name='InvalidConfigPgeTest', runconfig_path=runconfig_path)

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

        self.assertIn("RunConfig.Groups.PGE.InputFilesGroup.InputFilePaths: 'None' is not a list.", log_contents)
        self.assertIn("RunConfig.Groups.PGE.ProductPathGroup.ProductCounter: -1 is less than 1", log_contents)
        self.assertIn("RunConfig.Groups.PGE.PrimaryExecutable.ProgramPath: Required field missing", log_contents)
        self.assertIn("RunConfig.Groups.PGE.PrimaryExecutable.ProgramOptions: '--debug --restart' is not a list.",
                      log_contents)
        self.assertIn("RunConfig.Groups.PGE.QAExecutable.ProgramOptions: '--debug' is not a list.", log_contents)

    def test_base_pge_w_failing_sas(self):
        """
        Test execution of the PgeExecutor class using a RunConfig that defines
        a SAS execution path which is guaranteed to fail (return a non-zero exit
        code).
        """
        runconfig_path = join(self.data_dir, 'test_sas_error_config.yaml')

        pge = PgeExecutor(pge_name='FailedSasPgeTest', runconfig_path=runconfig_path)

        with self.assertRaises(RuntimeError):
            pge.run()

        # Log should be fully initialized before SAS execution, so make sure it was
        # moved where we expect.
        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        # Open the log file, and check that the execution error details were captured
        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        expected_error_code = 123

        self.assertIn(f"failed with exit code {expected_error_code}", log_contents)

    def test_sas_qa_execution(self):
        """
        Test execution of the PgeExecutor class using a test RunConfig that invokes
        a Quality Assurance (QA) application, in addition to the configured SAS
        executable.

        For this test, both the SAS an QA exes are configured to be just echo
        statements by the test RunConfig.

        """
        runconfig_path = join(self.data_dir, 'test_sas_qa_config.yaml')

        pge = PgeExecutor(pge_name='PgeQATest', runconfig_path=runconfig_path)

        # Kickoff execution of the PGE
        pge.run()

        # Check that the log file was created and moved into the output directory
        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        # Open the log file, and check that we got expected output for the SAS exe
        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn('hello from primary executable', log_contents)
        self.assertIn('sas.elapsed_seconds:', log_contents)

        # Check that a separate log file was created to capture the output from
        # the QA application
        expected_qa_log_file = pge.qa_logger.get_file_name()
        self.assertTrue(os.path.exists(expected_qa_log_file))

        with open(expected_qa_log_file, 'r', encoding='utf-8') as infile:
            qa_log_contents = infile.read()

        self.assertIn('hello from qa executable', qa_log_contents)
        self.assertIn('sas.qa.elapsed_seconds:', qa_log_contents)

    def test_input_files(self):
        """
        Test checking input files from the config.yaml file.
        Must be able to distinguish between a file path and a directory.
        If it finds a directory it must add the files in the directory to the input_file list.

        """
        # Create some additional input files within a subdirectory, as expected
        # by the RunConfig
        os.mkdir('new_input')
        Path('new_input/input_file03.h5').touch()
        Path('new_input/input_file04.h5').touch()

        runconfig_path = join(self.data_dir, 'test_base_pge_input_files_config.yaml')
        pge = PgeExecutor(pge_name='BasePgeTest', runconfig_path=runconfig_path)
        pge.run()
        log_file = pge.logger.get_file_name()
        output_dir = None
        expected_input_files = ['input/input_file01.h5', 'input/input_file02.h5',
                                'new_input/input_file03.h5', 'new_input/input_file04.h5']

        # find the output directory in the log file
        with open(log_file, 'r') as infile:
            for line in infile.readlines():
                if 'Creating output' in line:
                    output_dir = line.split('directory ')[1].strip()[:-1]
                    break

        # Find the catalog.json file and extract the 'Input_Files' field.
        if output_dir is not None:
            for filename in os.listdir(output_dir):
                if re.match(r"OPERA_L0_BasePge_\d{8}T\d{6}.catalog.json", filename):
                    output_file = "/".join((output_dir, filename))

                    with open(output_file) as outfile:
                        data = json.load(outfile)

                    for i in expected_input_files:
                        self.assertIn(i, data["Input_Files"])

    def test_geotiff_filename(self):
        """Test _geotiff_filename() method"""
        runconfig_path = join(self.data_dir, 'test_sas_qa_config.yaml')
        pge = PgeExecutor(pge_name='BasePgeFilenameTest', runconfig_path=runconfig_path)
        pge._initialize_logger()
        pge._load_runconfig()
        name = "TestName.tif"
        file_name = pge._geotiff_filename(name)
        file_name_regex = rf'{pge.PROJECT}_{pge.LEVEL}_BasePge_\d{{8}}T\d{{6}}_\d{{3}}_{name}{{1,2}}?'
        self.assertEqual(re.match(file_name_regex, file_name).group(), file_name)

    def _makedirs_mock(self, mode=511, exist_ok=False):
        """Mock function for os.makedirs that always raises OSError"""
        raise OSError("Mock OSError from os.makedirs")

    @patch.object(os, 'makedirs', _makedirs_mock)
    def test_setup_directories_exception(self):
        """Test IOError exception in _setup_directories()"""
        runconfig_path = join(self.data_dir, 'test_sas_qa_config.yaml')
        pge = PgeExecutor(pge_name='BasePgeFilenameTest', runconfig_path=runconfig_path)
        pge._initialize_logger()
        pge._load_runconfig()

        with self.assertRaises(RuntimeError):
            pge._setup_directories()

        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        # Open the log file, and check that we got expected error message
        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn(
            'Could not create one or more working directories. reason: \n'
            'Mock OSError from os.makedirs',
            log_contents
        )

    def create_sas_command_line_mock(self, sas_program_path='', sas_runconfig_filepath='',
                                     sas_program_options=None):
        """Mock run_util.create_qa_command_line()"""
        raise OSError("Mock OSError from run_utils.create_sas_command_line")

    @patch.object(opera.pge.base.base_pge, 'create_sas_command_line', create_sas_command_line_mock)
    def test_run_sas_executable_exception(self):
        """Test IOError exception in _run_sas_executable()"""
        runconfig_path = join(self.data_dir, 'test_sas_qa_config.yaml')
        pge = PgeExecutor(pge_name='PgeQATest', runconfig_path=runconfig_path)

        with self.assertRaises(RuntimeError):
            pge.run()

        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        # Open the log file, and check that we got expected error message
        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn(
            'Failed to create SAS command line, reason: '
            'Mock OSError from run_utils.create_sas_command_line',
            log_contents
        )

    def create_qa_command_line_mock(self, qa_program_path='./', qa_program_options=None):
        """Mock function for run_utils.create_qa_command_line that always raises OSError"""
        raise OSError("Mock OSError from run_utils.create_qa_command_line")

    @patch.object(opera.pge.base.base_pge, 'create_qa_command_line', create_qa_command_line_mock)
    def test_run_sas_qa_executable_exception(self):
        """Test OSError in _run_sas_qa_executable()"""
        runconfig_path = join(self.data_dir, 'test_sas_qa_config.yaml')
        pge = PgeExecutor(pge_name='PgeQATest', runconfig_path=runconfig_path)
        pge.run_preprocessor()
        pge.run_sas_executable()

        with self.assertRaises(RuntimeError):
            pge._run_sas_qa_executable()

        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        # Open the log file, and check that we got expected error message
        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn(
            'Failed to create QA command line, reason: '
            'Mock OSError from run_utils.create_qa_command_line',
            log_contents
        )

    def test_assign_filename_with_unknown_extension(self):
        """
        Test _assign_filename against an output file with an unknown extension.
        File renaming should be skipped.
        """
        runconfig_path = join(self.data_dir, 'test_sas_qa_bad_extension_config.yaml')
        pge = PgeExecutor(pge_name='PgeQATest', runconfig_path=runconfig_path)
        pge.run_preprocessor()
        pge.run_sas_executable()
        pge._stage_output_files()

        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        # Open the log file, and check that we got expected error message
        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn(
            'No rename function configured for file "output_file.abc", skipping assignment',
            log_contents
        )

    def _os_rename_mock(self, input_filepath='./', final_filepath='./'):
        """Mock function for os.rename that always raises OSError"""
        raise OSError("Mock OSError from os.rename")

    @patch.object(os, 'rename', _os_rename_mock)
    def test_assign_filename_exception(self):
        """Test IOError exception in _assign_filename()"""
        runconfig_path = join(self.data_dir, 'test_base_pge_config.yaml')
        pge = PgeExecutor(pge_name='PgeQATest', runconfig_path=runconfig_path)

        with self.assertRaises(RuntimeError):
            pge.run()

        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        # Open the log file, and check that we got expected error message
        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn(
            "Failed to rename output file dswx_hls.tif, reason: "
            "Mock OSError from os.rename",
            log_contents
        )

    def safe_dump_mock(self, sas_config='./', outfile='./', sort_keys=False):
        """Mock function for yaml.safe_dump() that always raises OSError"""
        raise OSError("Mock OSError from yaml.safe_dump")

    @patch.object(yaml, 'safe_dump', safe_dump_mock)
    def test_isolate_sas_runconfig_exception(self):
        """Test IOError exception in _isolate_sas_runconfig()"""
        runconfig_path = join(self.data_dir, 'test_sas_qa_config.yaml')
        pge = PgeExecutor(pge_name='PgeQATest', runconfig_path=runconfig_path)

        with self.assertRaises(RuntimeError):
            pge.run()

        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        # Open the log file, and check that we got expected error message
        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn(
            'Failed to create SAS config file base_pge_test/scratch/test_sas_qa_config_sas.yaml, '
            'reason: Mock OSError from yaml.safe_dump',
            log_contents
        )


if __name__ == "__main__":
    unittest.main()
