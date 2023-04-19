#!/usr/bin/env python3

"""
===================
test_dswx_s1_pge.py
===================
Unit tests for the pge/dswx_s1/dswx_s1_pge.py module.
"""

import glob
import os
import tempfile
import unittest
from io import StringIO
from os.path import abspath, exists, isdir, join

from pkg_resources import resource_filename

import yaml

from opera.pge import RunConfig
from opera.pge.dswx_s1.dswx_s1_pge import DSWxS1Executor
from opera.util import PgeLogger


class DswxS1PgeTestCase(unittest.TestCase):
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
            prefix="test_dswx_s1_pge_", suffix="_temp", dir=os.curdir
        )

        # Create the input directories expected by the test Runconfig file
        input_dir = join(self.working_dir.name, "dswx_s1_pge_test/input_dir")
        os.makedirs(input_dir, exist_ok=True)

        ancillary_data_dir = join(self.working_dir.name, "dswx_s1_pge_test/input_dir/ancillary_data")
        os.makedirs(ancillary_data_dir, exist_ok=True)

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
        self.assertEqual(runconfig['name'], 'dswx_s1_workflow_algorithm')
        self.assertEqual(runconfig['processing']['dswx_workflow'], 'opera_dswx_s1')
        self.assertListEqual(runconfig['processing']['polarizations'], ['VV', 'VH'])
        self.assertEqual(runconfig['processing']['reference_water']['max_value'], 100)
        self.assertEqual(runconfig['processing']['reference_water']['no_data_value'], 255)
        self.assertEqual(runconfig['processing']['mosaic']['mosaic_prefix'], 'mosaic')
        self.assertEqual(runconfig['processing']['mosaic']['mosaic_cog_enable'], True)
        self.assertEqual(runconfig['processing']['filter']['enabled'], True)
        self.assertEqual(runconfig['processing']['filter']['window_size'], 5)
        self.assertEqual(runconfig['processing']['initial_threshold']['maximum_tile_size']['x'], 400)
        self.assertEqual(runconfig['processing']['initial_threshold']['maximum_tile_size']['y'], 400)
        self.assertEqual(runconfig['processing']['initial_threshold']['minimum_tile_size']['x'], 40)
        self.assertEqual(runconfig['processing']['initial_threshold']['minimum_tile_size']['y'], 40)
        self.assertEqual(runconfig['processing']['initial_threshold']['selection_method'], 'combined')
        self.assertEqual(runconfig['processing']['initial_threshold']['interpolation_method'], 'smoothed')
        self.assertEqual(runconfig['processing']['initial_threshold']['threshold_method'], 'ki')
        self.assertEqual(runconfig['processing']['initial_threshold']['multi_threshold'], True)
        self.assertEqual(runconfig['processing']['region_growing']['seed'], 0.83)
        self.assertEqual(runconfig['processing']['region_growing']['tolerance'], 0.51)
        self.assertEqual(runconfig['processing']['region_growing']['line_per_block'], 400)
        self.assertEqual(runconfig['processing']['inundated_vegetation']['enabled'], False)
        self.assertEqual(runconfig['processing']['inundated_vegetation']['mode'], 'static_layer')
        self.assertEqual(runconfig['processing']['inundated_vegetation']['temporal_avg_path'], None)
        self.assertEqual(runconfig['processing']['inundated_vegetation']['initial_class_path'], None)
        self.assertEqual(runconfig['processing']['inundated_vegetation']['line_per_block'], 300)
        self.assertEqual(runconfig['processing']['debug_mode'], False)

    def test_dswx_s1_pge_execution(self):
        """
        Test execution of the DswxS1Executor class and its associated mixins
        using a test RunConfig that creates dummy expected output files and logs
        a message to be captured by PgeLogger.
        """
        runconfig_path = join(self.data_dir, 'test_dswx_s1_config.yaml')

        pge = DSWxS1Executor(pge_name="DswxS1PgeTest", runconfig_path=runconfig_path)

        # Check that basic attributes were initialized
        self.assertEqual(pge.name, "DSWx")
        self.assertEqual(pge.pge_name, "DswxS1PgeTest")
        self.assertEqual(pge.runconfig_path, runconfig_path)

        # Check that other objects have not been instantiated yet
        self.assertIsNone(pge.runconfig)
        self.assertIsNone(pge.logger)

        # Kickoff execution of DSWX-S1 PGE
        pge.run()

        # Check that the runconfig and logger were instantiated
        self.assertIsInstance(pge.runconfig, RunConfig)
        self.assertIsInstance(pge.logger, PgeLogger)

        # Check that directories were created according to RunConfig
        self.assertTrue(isdir(pge.runconfig.output_product_path))
        self.assertTrue(isdir(pge.runconfig.scratch_path))

        # Check that an in-memory log was created
        stream = pge.logger.get_stream_object()
        self.assertIsInstance(stream, StringIO)

        # Check that a RunConfig for the SAS was isolated within the scratch directory
        expected_sas_config_file = join(pge.runconfig.scratch_path, 'test_dswx_s1_config_sas.yaml')
        self.assertTrue(exists(expected_sas_config_file))

        # Check that the log file was created and moved into the output directory
        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(exists(expected_log_file))

        # Lastly, check that the dummy output products were created
        slc_files = glob.glob(join(pge.runconfig.output_product_path, "*.txt"))
        self.assertEqual(len(slc_files), 1)

        # Open and read the log
        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn(f"DSWx-S1 invoked with RunConfig {expected_sas_config_file}", log_contents)

    def test_dswx_s1_pge_validate_algorithm_parameters_config(self):
        """Test basic parsing and validation of an algorithm parameters RunConfig file"""
        runconfig_path = join(self.data_dir, 'test_dswx_s1_config.yaml')

        self.runconfig = RunConfig(runconfig_path)

        algorithm_parameters_runconfig = self.runconfig.algorithm_parameters_config_path

        pge = DSWxS1Executor(pge_name="DswxS1PgeTest", runconfig_path=runconfig_path)

        # Kickoff execution of DSWX-S1 PGE
        pge.run()

        self.assertEqual(algorithm_parameters_runconfig, pge.algorithm_parameters_runconfig)
        # parse the run config file
        runconfig_dict = self.runconfig._parse_algorithm_parameters_run_config_file(pge.algorithm_parameters_runconfig)
        # Check the properties of the algorithm parameters RunConfig to ensure they match as expected
        self._compare_algorithm_parameters_runconfig_to_expected(runconfig_dict)

    def test_dswx_s1_pge_bad_algorithm_parameters_schema_path(self):
        """
        Test for invalid path in 'AlgorithmParametersSchemaPath' in the PGE
        section of the runconfig file
        """
        runconfig_path = join(self.data_dir, 'test_dswx_s1_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_dswx_s1_config.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)

        runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']['AlgorithmParametersSchemaPath'] = \
                       'test/data/test_algorithm_parameters_non_existent.yaml'  # noqa E211

        with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        try:
            pge = DSWxS1Executor(pge_name="DswxS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

        finally:
            if exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

    def test_dswx_s1_pge_bad_algorithm_parameters_path(self):
        """Test for invalid path to 'algorithm_parameters' in SAS runconfig file"""
        runconfig_path = join(self.data_dir, 'test_dswx_s1_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_dswx_s1_config.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)

        runconfig_dict['RunConfig']['Groups']['SAS']['runconfig']['groups']['dynamic_ancillary_file_group']\
                      ['algorithm_parameters'] = 'test/data/test_algorithm_parameters_non_existent.yaml'

        with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        try:
            pge = DSWxS1Executor(pge_name="DswxS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

        finally:
            if exists(test_runconfig_path):
                os.unlink(test_runconfig_path)


if __name__ == "__main__":
    unittest.main()
