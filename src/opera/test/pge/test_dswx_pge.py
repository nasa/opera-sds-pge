#!/usr/bin/env python

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
================
test_dswx_pge.py
================

Unit tests for the pge/dswx_pge.py module.
"""
import os
import tempfile
import unittest
import yaml
from os.path import abspath, join
from io import StringIO

from pkg_resources import resource_filename

from opera.pge import DSWxExecutor, RunConfig
from opera.util import PgeLogger


class DSWxPgeTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.starting_dir = abspath(os.curdir)
        cls.test_dir = resource_filename(__name__, "")
        cls.data_dir = join(cls.test_dir, "data")

        os.chdir(cls.test_dir)

        cls.working_dir = tempfile.TemporaryDirectory(
            prefix="test_dswx_pge_", suffix='_temp', dir=os.curdir
        )

        # Create the input dir expected by the test RunConfig and add a dummy
        # input file so they it be validated
        input_dir = join(cls.working_dir.name, "dswx_pge_test/input_dir")
        os.makedirs(input_dir, exist_ok=True)

        cls.input_file = tempfile.NamedTemporaryFile(
            dir=input_dir, prefix="test_input", suffix=".tif")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.input_file.close()
        cls.working_dir.cleanup()
        os.chdir(cls.starting_dir)

    def setUp(self) -> None:
        os.chdir(self.working_dir.name)

    def tearDown(self) -> None:
        os.chdir(self.test_dir)

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

        # Check that a in-memory log was created
        stream = pge.logger.get_stream_object()
        self.assertTrue(isinstance(stream, StringIO))

        # Check that a RunConfig for the SAS was isolated within the scratch directory
        expected_sas_config_file = join(pge.runconfig.scratch_path, 'test_dswx_hls_config_sas.yaml')
        self.assertTrue(os.path.exists(expected_sas_config_file))

        # Save the log stream to disk
        pge.logger.log_save_and_close()

        # Check that the log file was created and moved into the output directory
        expected_log_file = join(pge.runconfig.output_product_path, pge.logger.get_file_name())
        self.assertTrue(os.path.exists(expected_log_file))

        # Open the log file, and check that "SAS" output was captured
        with open(expected_log_file, 'r') as infile:
            log_contents = infile.read()

        # TODO - I had to add an extra space between 'RunConfig' and {expected_sas_....
        self.assertIn(f"DSWx-HLS invoked with RunConfig  {expected_sas_config_file}", log_contents)

    def test_dswx_pge_input_validation(self):
        """
        Test the input validation checks made by DSWxPreProcessorMixin.
        """
        runconfig_path = join(self.data_dir, 'test_dswx_hls_config.yaml')
        test_runconfig_path = 'invalid_dswx_runconfig.yaml'

        with open(runconfig_path, 'r') as stream:
            runconfig_dict = yaml.safe_load(stream)

        input_files_group = runconfig_dict['RunConfig']['Groups']['PGE']['InputFilesGroup']

        # Test that a non-existent file is detected by pre-processor
        input_files_group['InputFilePaths'] = ['non_existent_file.tif']

        with open(test_runconfig_path, 'w') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        pge = DSWxExecutor(pge_name="DSWxPgeTest", runconfig_path=test_runconfig_path)

        with self.assertRaises(RuntimeError):
            pge.run()

        # Config validation occurs before the log is fully initialized, but the
        # initial log file should still exist and contain details of the validation
        # error
        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        # Open the log file, and check that the validation error details were captured
        with open(expected_log_file, 'r') as infile:
            log_contents = infile.read()

        self.assertIn(f"Could not locate specified input file/directory "
                      f"{abspath('non_existent_file.tif')}", log_contents)

        # Test that an input directory with no .tif files is caught
        input_files_group['InputFilePaths'] = ['dswx_pge_test/scratch_dir']

        with open(test_runconfig_path, 'w') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        pge = DSWxExecutor(pge_name="DSWxPgeTest", runconfig_path=test_runconfig_path)

        with self.assertRaises(RuntimeError):
            pge.run()

        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        with open(expected_log_file, 'r') as infile:
            log_contents = infile.read()

        self.assertIn(f"Input directory {abspath('dswx_pge_test/scratch_dir')} "
                      f"does not contain any tif files", log_contents)

        # Lastly, check that a file that exists but is not a tif is caught
        input_files_group['InputFilePaths'] = [runconfig_path]

        with open(test_runconfig_path, 'w') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        pge = DSWxExecutor(pge_name="DSWxPgeTest", runconfig_path=test_runconfig_path)

        with self.assertRaises(RuntimeError):
            pge.run()

        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        with open(expected_log_file, 'r') as infile:
            log_contents = infile.read()

        self.assertIn(f"Input file {abspath(runconfig_path)} does not have "
                      f".tif extension", log_contents)

    def test_dswx_pge_output_validation(self):
        """
        Test the output validation checks made by DSWxPostProcessorMixin.
        """
        runconfig_path = join(self.data_dir, 'test_dswx_hls_config.yaml')
        test_runconfig_path = 'invalid_dswx_runconfig.yaml'

        with open(runconfig_path, 'r') as stream:
            runconfig_dict = yaml.safe_load(stream)

        product_path_group = runconfig_dict['RunConfig']['Groups']['PGE']['ProductPathGroup']
        primary_executable_group = runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']

        # Test with a SAS command that does not produce any output file,
        # post-processor should detect that expected output is missing
        product_path_group['SASOutputFile'] = 'missing_dswx_hls.tif'
        primary_executable_group['ProgramPath'] = 'echo'
        primary_executable_group['ProgramOptions'] = ['hello world']

        with open(test_runconfig_path, 'w') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        pge = DSWxExecutor(pge_name="DSWxPgeTest", runconfig_path=test_runconfig_path)

        with self.assertRaises(RuntimeError):
            pge.run()

        expected_output_file = 'dswx_pge_test/output_dir/missing_dswx_hls.tif'
        self.assertFalse(os.path.exists(expected_output_file))

        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        with open(expected_log_file, 'r') as infile:
            log_contents = infile.read()

        self.assertIn(f"Expected SAS output file {abspath(expected_output_file)} "
                      f"does not exist", log_contents)

        # Test with a SAS command that produces the expected output file, but
        # one that is empty (size 0 bytes). Post-processor should detect this
        # and flag an error
        product_path_group['SASOutputFile'] = 'empty_dswx_hls.tif'
        primary_executable_group['ProgramPath'] = 'touch'
        primary_executable_group['ProgramOptions'] = ['dswx_pge_test/output_dir/empty_dswx_hls.tif']

        with open(test_runconfig_path, 'w') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        pge = DSWxExecutor(pge_name="DSWxPgeTest", runconfig_path=test_runconfig_path)

        with self.assertRaises(RuntimeError):
            pge.run()

        expected_output_file = 'dswx_pge_test/output_dir/empty_dswx_hls.tif'
        self.assertTrue(os.path.exists(expected_output_file))

        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        with open(expected_log_file, 'r') as infile:
            log_contents = infile.read()

        self.assertIn(f"SAS output file {abspath(expected_output_file)} was "
                      f"created but is empty", log_contents)


if __name__ == "__main__":
    unittest.main()
