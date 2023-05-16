#!/usr/bin/env python3

"""
===================
test_disp_s1_pge.py
===================
Unit tests for the pge/disp_s1/disp_s1_pge.py module.
"""

import glob
import os
import tempfile
import unittest
import yaml
from io import StringIO
from os.path import abspath, join, exists

from pkg_resources import resource_filename

from opera.pge import RunConfig
from opera.pge.disp_s1.disp_s1_pge import DispS1Executor
from opera.util import PgeLogger


class DispS1PgeTestCase(unittest.TestCase):
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
            prefix="test_disp_s1_pge_", suffix="_temp", dir=os.curdir
        )

        # Create the input dir expected by the test RunConfig and add a
        # dummy input file
        input_dir = join(self.working_dir.name, "disp_s1_pge_test/input_dir")
        os.makedirs(input_dir, exist_ok=True)

        self.input_file = tempfile.NamedTemporaryFile(
            dir=input_dir, prefix="test_input_", suffix=".tiff"
        )

        os.chdir(self.working_dir.name)

    def tearDown(self) -> None:
        """Return to starting directory"""
        os.chdir(self.test_dir)
        self.input_file.close()
        self.working_dir.cleanup()

    def _compare_algorithm_parameters_runconfig_to_expected(self, runconfig):
        """
        Helper method to check the properties of a parsed algorithm parameters runconfig against the
        expected values as defined by the "valid" sample algorithm parameters runconfig files.
        """
        self.assertEqual(runconfig['name'], 'disp_s1_workflow_algorithm')
        self.assertEqual(runconfig['processing']['ps_options']['amp_dispersion_threshold'], 0.25)
        self.assertEqual(runconfig['processing']['phase_linking']['ministack_size'], 1000)
        self.assertEqual(runconfig['processing']['phase_linking']['beta'], 0.01)
        self.assertEqual(runconfig['processing']['phase_linking']['half_window']['x'], 11)
        self.assertEqual(runconfig['processing']['phase_linking']['half_window']['y'], 5)
        self.assertEqual(runconfig['processing']['interferogram_network']['reference_idx'], 0)
        self.assertEqual(runconfig['processing']['interferogram_network']['max_bandwidth'], None)
        self.assertEqual(runconfig['processing']['interferogram_network']['max_temporal_baseline'], None)
        self.assertEqual(runconfig['processing']['interferogram_network']['indexes'], [[0, -1]])
        self.assertEqual(runconfig['processing']['interferogram_network']['network_type'], 'single-reference')
        self.assertEqual(runconfig['processing']['unwrap_options']['run_unwrap'], True)
        self.assertEqual(runconfig['processing']['unwrap_options']['unwrap_method'], 'icu')
        self.assertEqual(runconfig['processing']['unwrap_options']['tiles'], [1, 1])
        self.assertEqual(runconfig['processing']['unwrap_options']['init_method'], 'mcf')
        self.assertEqual(runconfig['processing']['output_options']['output_resolution'], None)
        self.assertEqual(runconfig['processing']['output_options']['strides']['x'], 6)
        self.assertEqual(runconfig['processing']['output_options']['strides']['y'], 3)
        self.assertEqual(runconfig['processing']['output_options']['hdf5_creation_options']['chunks'], [128, 128])
        self.assertEqual(runconfig['processing']['output_options']['hdf5_creation_options']['compression'], 'gzip')
        self.assertEqual(runconfig['processing']['output_options']['hdf5_creation_options']['compression_opts'], 4)
        self.assertEqual(runconfig['processing']['output_options']['hdf5_creation_options']['shuffle'], True)
        self.assertEqual(runconfig['processing']['output_options']['gtiff_creation_options'],
                         ['COMPRESS=DEFLATE', 'ZLEVEL=4', 'TILED=YES', 'BLOCKXSIZE=128', 'BLOCKYSIZE=128'])
        self.assertEqual(runconfig['processing']['subdataset'], 'science/SENTINEL1/CSLC/grids/VV')

    def test_disp_s1_pge_execution(self):
        """
        Test execution of the DispS1Executor class and its associated mixins
        using a test RunConfig that creates dummy expected output files and logs
        a message to be captured by PgeLogger.
        """
        runconfig_path = join(self.data_dir, 'test_disp_s1_config.yaml')

        pge = DispS1Executor(pge_name="DispS1PgeTest", runconfig_path=runconfig_path)

        # Check that basic attributes were initialized
        self.assertEqual(pge.name, "DISP")
        self.assertEqual(pge.pge_name, "DispS1PgeTest")
        self.assertEqual(pge.runconfig_path, runconfig_path)

        # Check that other objects have not been instantiated yet
        self.assertIsNone(pge.runconfig)
        self.assertIsNone(pge.logger)

        # Kickoff execution of DISP-S1 PGE
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
        expected_sas_config_file = join(pge.runconfig.scratch_path, 'test_disp_s1_config_sas.yaml')
        self.assertTrue(os.path.exists(expected_sas_config_file))

        # Check that the log file was created and moved into the output directory
        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        # Lastly, check that the dummy output products were created
        slc_files = glob.glob(join(pge.runconfig.output_product_path, "*.txt"))
        self.assertEqual(len(slc_files), 1)

        # Open and read the log
        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn(f"DISP-S1 invoked with RunConfig {expected_sas_config_file}", log_contents)

    def test_disp_s1_pge_validate_algorithm_parameters_config(self):
        """Test basic parsing and validation of an algorithm parameters RunConfig file"""
        runconfig_path = join(self.data_dir, 'test_disp_s1_config.yaml')

        self.runconfig = RunConfig(runconfig_path)

        algorithm_parameters_runconfig_file = self.runconfig.algorithm_parameters_file_config_path

        pge = DispS1Executor(pge_name="DispS1PgeTest", runconfig_path=runconfig_path)

        # Kickoff execution of DISP-S1 PGE
        pge.run()

        self.assertEqual(algorithm_parameters_runconfig_file, pge.algorithm_parameters_runconfig)
        # parse the run config file
        runconfig_dict = self.runconfig._parse_algorithm_parameters_run_config_file(pge.algorithm_parameters_runconfig)
        # Check the properties of the algorithm parameters RunConfig to ensure they match as expected
        self._compare_algorithm_parameters_runconfig_to_expected(runconfig_dict)

    def test_disp_s1_pge_bad_algorithm_parameters_schema_path(self):
        """
        Test for invalid path in the optional 'AlgorithmParametersSchemaPath'
        section of in the PGE runconfig file.
        section of the runconfig file.  Also test for no AlgorithmParametersSchemaPath
        """
        runconfig_path = join(self.data_dir, 'test_disp_s1_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_disp_s1_config.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)

        runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']['AlgorithmParametersSchemaPath'] = \
                       'test/data/test_algorithm_parameters_non_existent.yaml'  # noqa E211

        with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        try:
            pge = DispS1Executor(pge_name="DispS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

        finally:
            if exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

        # Verify that None is returned if 'AlgorithmParametersSchemaPath' is None
        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)

        runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']['AlgorithmParametersSchemaPath'] = None

        with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        try:
            pge = DispS1Executor(pge_name="DispS1PgeTest", runconfig_path=test_runconfig_path)

            pge.run()

            # Check that the log file was created and moved into the output directory
            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(exists(expected_log_file))

            # Open and read the log
            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("No algorithm_parameters_schema_path provided in runconfig file", log_contents)

        finally:
            if exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

    def test_disp_s1_pge_bad_algorithm_parameters_path(self):
        """Test for invalid path to 'algorithm_parameters_file' in SAS runconfig file"""
        runconfig_path = join(self.data_dir, 'test_disp_s1_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_disp_s1_config.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)

        runconfig_dict['RunConfig']['Groups']['SAS']['runconfig']['groups']['dynamic_ancillary_file_group']\
                      ['algorithm_parameters_file'] = 'test/data/test_algorithm_parameters_non_existent.yaml' # noqa E211

        with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        try:
            pge = DispS1Executor(pge_name="DispS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

        finally:
            if exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

if __name__ == "__main__":
    unittest.main()
