#!/usr/bin/env python3
#
# Copyright 2021, by the California Institute of Technology.
# ALL RIGHTS RESERVED.
# United States Government sponsorship acknowledged.
# Any commercial use must be negotiated with the Office of Technology Transfer
# at the California Institute of Technology.
# This software may be subject to U.S. export control laws and regulations.
# By accepting this document, the user agrees to comply with all applicable
# U.S. export laws and regulations. User has the responsibility to obtain
# export licenses, or other export authority as may be required, before
# exporting such information to foreign countries or providing access to
# foreign persons.
#

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
from pathlib import Path
from io import StringIO
from os.path import abspath, join

from pkg_resources import resource_filename

from opera.pge import PgeExecutor, RunConfig
from opera.util import PgeLogger


class BasePgeTestCase(unittest.TestCase):
    """Base test class using unittest"""

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
        # Set up temporary directories and files to match test config file
        os.mkdir('input')
        Path('input/input_file01.h5').touch()
        Path('input/input_file02.h5').touch()

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
        expected_log_file = join(pge.runconfig.output_product_path, pge.logger.get_file_name())
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

    def test_geotiff_filename(self):
        """Test _geotiff_filename() method"""
        runconfig_path = join(self.data_dir, 'test_sas_qa_config.yaml')
        pge = PgeExecutor(pge_name='PgeQATest', runconfig_path=runconfig_path)
        pge._geotiff_filename("TestName.ext")

    def test_sas_qa_execution(self):
        """
        Test execution of the PgeExecutor class using a test RunConfig that invokes
        a Quality Assurance (QA) application, in addition to the configured SAS
        executable.

        For this test, both the SAS an QA exes are configured to be just echo
        statements by the test RunConfig.

        """
        # Set up temporary directories and files to match test config file
        os.mkdir('input')
        Path('input/input_file01.h5').touch()
        Path('input/input_file02.h5').touch()

        runconfig_path = join(self.data_dir, 'test_sas_qa_config.yaml')

        pge = PgeExecutor(pge_name='PgeQATest', runconfig_path=runconfig_path)

        # Kickoff execution of the PGE
        pge.run()

        # Check that the log file was created and moved into the output directory
        expected_log_file = join(pge.runconfig.output_product_path, pge.logger.get_file_name())
        self.assertTrue(os.path.exists(expected_log_file))

        # Open the log file, and check that we got expected output for both the SAS exe and the QA exe
        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn('hello from primary executable', log_contents)
        self.assertIn('hello from qa executable', log_contents)

        # Make sure the run time metrics were captured for both applications
        self.assertIn('sas.elapsed_seconds:', log_contents)
        self.assertIn('sas.qa.elapsed_seconds:', log_contents)

    def test_input_files(self):
        """
        Test checking input files from the config.yaml file.
        Must be able to distinguish between a file path and a directory.
        If it finds a directory it must add the files in the directory to the input_file list.

        """

        # Set up temporary directories and files to match config file
        os.mkdir('input')
        os.mkdir('new_input')
        Path('input/file1.txt').touch()
        Path('input/file2.txt').touch()
        Path('new_input/file3.txt').touch()
        Path('new_input/file4.txt').touch()

        runconfig_path = join(self.data_dir, 'test_base_pge_input_files_config.yaml')
        pge = PgeExecutor(pge_name='BasePgeTest', runconfig_path=runconfig_path)
        pge.run()
        log_file = pge.logger.get_file_name()
        output_dir = None
        expected_input_files = ['input/file1.txt', 'input/file2.txt', 'new_input/file3.txt', 'new_input/file4.txt']
        # find the output directory in the log file
        with open(log_file, 'r') as f:
            for line in f:
                ln = f.readline()
                if 'Creating output' in ln:
                    output_dir = ln.split('directory ')[1].strip()[:-1]
                    break
        # Find the catalog.json file and extract the 'Input_Files' field.
        if output_dir is not None:
            for filename in os.listdir(output_dir):
                if re.match(r"OPERA_L0_BasePge_\d{8}T\d{6}.catalog.json", filename):
                    output_file = "/".join((output_dir, filename))
                    with open(output_file) as j_file:
                        data = json.load(j_file)
                    for i in expected_input_files:
                        self.assertIn(i, data["Input_Files"])


if __name__ == "__main__":
    unittest.main()
