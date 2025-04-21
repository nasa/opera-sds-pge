#!/usr/bin/env python3

"""
===================
test_tropo_pge.py
===================
Unit tests for the pge/tropo/tropo_pge.py module.
"""

import glob
import os
from pathlib import Path
import random
import tempfile
import unittest
from io import StringIO
from os.path import abspath, join

from pkg_resources import resource_filename
import yaml

from opera.pge import RunConfig
from opera.pge.tropo.tropo_pge import TROPOExecutor
from opera.util import PgeLogger


class TROPOPgeTestCase(unittest.TestCase):
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
            prefix="test_tropo_pge_", suffix="_temp", dir=os.curdir
        )

        # Create the input dir expected by the test RunConfig and add a
        # dummy input file
        self.input_dir = join(self.working_dir.name, "tropo_pge_test/input_dir")
        os.makedirs(self.input_dir, exist_ok=True)

        self.input_file = tempfile.NamedTemporaryFile(
            dir=self.input_dir, prefix="test_input_", suffix=".nc"
        )
        
        rc = RunConfig(join(self.data_dir, 'test_tropo_config.yaml'))

        for file in rc.sas_config["input_file"]["input_file_path"]:
            dummy_file_path = join(self.working_dir.name, file)

            Path(dummy_file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(dummy_file_path, "wb") as f:
                f.write(random.randbytes(1024))
                
        # Create the output directories expected by the test Runconfig file
        self.test_output_dir = abspath(join(self.working_dir.name, "tropo_pge_test/output_dir"))
        os.makedirs(self.test_output_dir, exist_ok=True)

        os.chdir(self.working_dir.name)

    def tearDown(self) -> None:
        """Return to starting directory"""
        os.chdir(self.test_dir)
        self.input_file.close()
        self.working_dir.cleanup()

    def test_tropo_pge_execution(self):
        """
        Test execution of the TROPOExecutor class and its associated mixins
        using a test RunConfig that creates dummy expected output files and logs
        a message to be captured by PgeLogger.
        """
        runconfig_path = join(self.data_dir, 'test_tropo_config.yaml')

        pge = TROPOExecutor(pge_name="TROPOPgeTest", runconfig_path=runconfig_path)

        # Check that basic attributes were initialized
        self.assertEqual(pge.name, "TROPO")
        self.assertEqual(pge.pge_name, "TROPOPgeTest")
        self.assertEqual(pge.runconfig_path, runconfig_path)

        # Check that other objects have not been instantiated yet
        self.assertIsNone(pge.runconfig)
        self.assertIsNone(pge.logger)

        # Kickoff execution of TROPO PGE
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
        expected_sas_config_file = join(pge.runconfig.scratch_path, 'test_tropo_config_sas.yaml')
        self.assertTrue(os.path.exists(expected_sas_config_file))

        # Check that the log file was created and moved into the output directory
        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        # Lastly, check that the dummy output products were created
        slc_files = glob.glob(join(pge.runconfig.output_product_path, "*.nc"))
        self.assertEqual(len(slc_files), 1)

        # Open and read the log
        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn(f"TROPO invoked with RunConfig {expected_sas_config_file}", log_contents)

    def _run_and_check_error(self, runconfig: dict, test_runconfig_path: str, expected_log_message: str):
        """
        Helper to:
            - write the test runconfig,
            - execute PGE with test runconfig,
            - assert expected error is in log message.
            
        Paramaters
        ----------
        runconfig: dict
            Runconfig yaml contents containing the input file path relative to the case being tested
        test_runconfig_path: str
            Path to location where testing runconfig yaml will be written
        expected_log_message: str
            The string expected to be found in the log for the given case being tested. 
            Comes from input_validation.py        
        """

        with open(test_runconfig_path, 'w', encoding='utf-8') as input_path:
            yaml.safe_dump(runconfig, input_path, sort_keys=False)

        pge = TROPOExecutor(pge_name="TropoPgeTest", runconfig_path=test_runconfig_path)

        with self.assertRaises(RuntimeError):
            pge.run()

        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn(expected_log_message, log_contents)

    def test_tropo_pge_input_validation(self):
        """
        Test the input validation checks made by TropoPreProcessorMixin:
        - Nonexistent file
        - File of size 0
        - File with incorrect extension
        """
        runconfig_path = join(self.data_dir, 'test_tropo_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_tropo_runconfig.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as stream:
            runconfig = yaml.safe_load(stream)

        try:           
            # Test: Nonexistent file
            missing_file = os.path.join(self.input_dir, 'non_existent_file.nc')
            runconfig['RunConfig']['Groups']['PGE']['InputFilesGroup']['InputFilePaths'] = [missing_file]
            self._run_and_check_error(
                runconfig, 
                test_runconfig_path, 
                f"Could not locate specified input {missing_file}"
            )

            # Test: Empty file
            empty_file = os.path.join(self.input_dir, 'empty.nc')
            runconfig['RunConfig']['Groups']['PGE']['InputFilesGroup']['InputFilePaths'] = [empty_file]
            os.system(f"touch {empty_file}")
            self._run_and_check_error(
                runconfig, 
                test_runconfig_path, 
                f"Input file {empty_file} size is 0. Size must be greater than 0."
            )
            
            # Test: Wrong file extension
            wrong_type_file = os.path.join(self.input_dir, 'wrong_input_type.png')
            runconfig['RunConfig']['Groups']['PGE']['InputFilesGroup']['InputFilePaths'] = [wrong_type_file]
            with open(wrong_type_file, 'wb') as fp:
                fp.write(random.randbytes(1024))
            self._run_and_check_error(
                runconfig, 
                test_runconfig_path, 
                f"Input file {wrong_type_file} does not have an expected file extension."
            )

        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)
    
    def test_tropo_pge_output_validation(self):
        """Test the output validation checks made by TropoPostProcessorMixin:
        - Missing expected file
        - > 1 expected file
        - File of size 0
        - File with incorrect extension
        - Ensure output products satisfy naming convention check
        """
        runconfig_path = join(self.data_dir, 'test_tropo_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_tropo_runconfig.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as stream:
            runconfig = yaml.safe_load(stream)
        
        try:
            # Test: Missing .nc file
            for filepath in self.test_output_dir:
                if os.path.isfile(filepath):
                    os.remove(filepath)
            png_file = os.path.join(self.input_dir, 'png_output.png')
            os.system(f"touch {png_file}")
            self._run_and_check_error(
                runconfig, 
                test_runconfig_path, 
                "Could not locate specified input .nc file."
            )
            
            # Test: >1 .png file
            nc_file = os.path.join(self.input_dir, 'nc_output.nc')
            os.system(f"touch {nc_file}")
            png_file = os.path.join(self.input_dir, 'png_output.png')
            os.system(f"touch {png_file}")
            self._run_and_check_error(
                runconfig, 
                test_runconfig_path, 
                "Found incorrect number of .png files."
            )
            
            for filepath in self.test_output_dir:
                if os.path.isfile(filepath):
                    os.remove(filepath)
            
            # Check for empty nc file
            empty_nc_file = os.path.join(self.test_output_dir, 'empty.nc')
            os.system(f"touch {empty_nc_file}")
            png_file = os.path.join(self.test_output_dir, 'dummy_file.png')
            with open(png_file, "wb") as f:
                f.write(random.randbytes(1024))
            self._run_and_check_error(
                runconfig, 
                test_runconfig_path, 
                f"Output file {empty_nc_file} size is 0. Size must be greater than 0."
            )
            
            for filepath in self.test_output_dir:
                if os.path.isfile(filepath):
                    os.remove(filepath)
            
            # Check for nc filename convention matching
            dummy_file_path = os.path.join(self.test_output_dir, 'dummy_file.nc')
            with open(dummy_file_path, "wb") as f:
                f.write(random.randbytes(1024))
            png_file = os.path.join(self.test_output_dir, f'OPERA_L4_TROPO-ZENITH_20250101T010101Z_20250101T010101Z_HRES_{TROPOExecutor.SAS_VERSION}.png')
            with open(png_file, "wb") as f:
                f.write(random.randbytes(1024))
            self._run_and_check_error(
                runconfig, 
                test_runconfig_path, 
                f"Invalid product filename dummy_file.nc"
            )            
            
        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

if __name__ == "__main__":
    unittest.main()