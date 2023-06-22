#!/usr/bin/env python3

"""
===================
test_dswx_s1_pge.py
===================
Unit tests for the pge/dswx_s1/dswx_s1_pge.py module.
"""

import glob
import os
import shutil
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
    input_tif_file = None
    input_h5_file = None
    input_dir = "dswx_s1_pge_test/input_dir"

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
        test_input_dir = join(self.working_dir.name, "dswx_s1_pge_test/input_dir")
        os.makedirs(test_input_dir, exist_ok=True)

        self.input_file = tempfile.NamedTemporaryFile(
            dir=test_input_dir, prefix="test_h5_", suffix=".h5"
        )

        # Copy the algorithm_parameters config file into the test input directory.
        shutil.copy(join(self.data_dir, 'test_algorithm_parameters_s1.yaml'), test_input_dir)
        # these path variables are use to update the main runconfig file, then to reset it
        self.test_algorithm_parameters_path = abspath(join(test_input_dir, 'test_algorithm_parameters_s1.yaml'))
        self.restore_test_algorithm_param_path = 'dswx_s1_pge_test/input_dir/test_algorithm_parameters_s1.yaml'

        self.input_file = tempfile.NamedTemporaryFile(
            dir=test_input_dir, prefix="test_h5_", suffix=".h5"
        )

        # Create dummy versions of the expected ancillary inputs
        for ancillary_file in ('dem.tif', 'worldcover.tif',
                               'reference_water.tif', 'shoreline.shp', 'shoreline.dbf', 'shoreline.prj',
                               'shoreline.shx', 'hand.tif'):
            os.system(
                f"touch {join(test_input_dir, ancillary_file)}"
            )

        # Create the output directories expected by the test Runconfig file
        self.test_output_dir = abspath(join(self.working_dir.name, "dswx_s1_pge_test/output_dir"))
        os.makedirs(self.test_output_dir, exist_ok=True)
        # Add some band data to the output directory:
        band_data = ('OPERA_L3_DSWx-S1_b1_B01_WTR.tif', 'OPERA_L3_DSWx-S1_b1_B02_BWTR.tif',
                     'OPERA_L3_DSWx-S1_b1_B03_CONF.tif', 'OPERA_L3_DSWx-S1_b2_B01_WTR.tif',
                     'OPERA_L3_DSWx-S1_b2_B02_BWTR.tif', 'OPERA_L3_DSWx-S1_b2_B03_CONF.tif')
        self.generate_band_data_output(band_data, clear=False)

        os.chdir(self.working_dir.name)

    def tearDown(self) -> None:
        """Return to starting directory"""
        os.chdir(self.test_dir)
        self.input_file.close()
        self.working_dir.cleanup()

    def _set_algorithm_parameters_path(self, runconfig, path):
        """
        Set the path in the main runconfig file to the algorithm parameters
        runconfig file.  For each test this path is set to the algorithm
        parameters runconfig in the test data directory.  At the end of each
        test it is set back to the original value.

        Parameters
        ----------
        runconfig:  str
            runconfig file to modify
        path:  str
            path to the algorithm parameters runconfig file

        """
        runconfig_path = join(self.data_dir, runconfig)

        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)

        runconfig_dict['RunConfig']['Groups']['SAS']['runconfig']['groups']['dynamic_ancillary_file_group'] \
            ['algorithm_parameters'] = path  # noqa E211

        with open(runconfig_path, 'w', encoding='utf-8') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

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

    def generate_band_data_output(self, band_data, empty_file=False, clear=True):
        """
        Add files to the output directory.

        Parameters
        ----------
        band_data: tuple of str
            Files to add to the output directory.
        empty_file: bool
            if 'True' do not add text to the file (leave empty)
            if 'False' (default) add 'Test data string' to the file
        clear : bool
            Clear the output directory before writing new files (default=True)

        """
        # example of band data passed to method:
        # band_data = ('OPERA_L3_DSWx-S1_band_1_B01_WTR.tif', 'OPERA_L3_DSWx-S1_band_1_B02_BWTR.tif',
        #              'OPERA_L3_DSWx-S1_band_1_B03_CONF.tif', 'OPERA_L3_DSWx-S1_band_2_B01_WTR.tif',
        #              'OPERA_L3_DSWx-S1_band_2_B02_BWTR.tif', 'OPERA_L3_DSWx-S1_band_2_B03_CONF.tif')

        if clear:
            path = self.test_output_dir
            cmd = f"rm {path}/*.tif"
            os.system(cmd)
        # Add files to the output directory
        for band_output_file in band_data:
            if not empty_file:
                os.system(f"echo 'Test data string' >> {join(self.test_output_dir, band_output_file)}")
            else:
                os.system(f"touch {join(self.test_output_dir, band_output_file)}")

    def test_dswx_s1_pge_execution(self):
        """
        Test execution of the DswxS1Executor class and its associated mixins
        using a test RunConfig that creates dummy expected output files and logs
        a message to be captured by PgeLogger.
        """
        runconfig_path = join(self.data_dir, 'test_dswx_s1_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_dswx_s1_config.yaml')

        self._set_algorithm_parameters_path(runconfig_path, self.test_algorithm_parameters_path)

        pge = DSWxS1Executor(pge_name="DswxS1PgeTest", runconfig_path=runconfig_path)

        # Check that basic attributes were initialized
        self.assertEqual(pge.name, "DSWx")
        self.assertEqual(pge.pge_name, "DswxS1PgeTest")
        self.assertEqual(pge.runconfig_path, runconfig_path)

        # Check that other objects have not been instantiated yet
        self.assertIsNone(pge.runconfig)
        self.assertIsNone(pge.logger)

        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)

        runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']['AlgorithmParametersSchemaPath'] = None

        with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        try:
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

        finally:
            if exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

        self._set_algorithm_parameters_path(runconfig_path, self.restore_test_algorithm_param_path)

    def test_dswx_s1_pge_validate_algorithm_parameters_config(self):
        """Test basic parsing and validation of an algorithm parameters RunConfig file"""
        runconfig_path = join(self.data_dir, 'test_dswx_s1_config.yaml')

        self._set_algorithm_parameters_path(runconfig_path, self.test_algorithm_parameters_path)

        self.runconfig = RunConfig(runconfig_path)

        algorithm_parameters_runconfig = self.runconfig.algorithm_parameters_file_config_path

        pge = DSWxS1Executor(pge_name="DswxS1PgeTest", runconfig_path=runconfig_path)

        # Kickoff execution of DSWX-S1 PGE
        pge.run()

        self.assertEqual(algorithm_parameters_runconfig, pge.runconfig.algorithm_parameters_file_config_path)
        # parse the run config file
        runconfig_dict = self.runconfig._parse_algorithm_parameters_run_config_file \
            (pge.runconfig.algorithm_parameters_file_config_path)       # noqa 211
        # Check the properties of the algorithm parameters RunConfig to ensure they match as expected
        self._compare_algorithm_parameters_runconfig_to_expected(runconfig_dict)

        self._set_algorithm_parameters_path(runconfig_path, self.restore_test_algorithm_param_path)

    def test_dswx_s1_pge_bad_algorithm_parameters_schema_path(self):
        """
        Test for invalid path in the optional 'AlgorithmParametersSchemaPath'
        section of in the PGE runconfig file.
        section of the runconfig file.  Also test for no AlgorithmParametersSchemaPath
        """
        runconfig_path = join(self.data_dir, 'test_dswx_s1_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_dswx_s1_config.yaml')

        self._set_algorithm_parameters_path(runconfig_path, self.test_algorithm_parameters_path)

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

        # Verify that None is returned when 'AlgorithmParametersSchemaPath' is set to None
        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)

        runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']['AlgorithmParametersSchemaPath'] = None

        with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        try:
            pge = DSWxS1Executor(pge_name="DswxS1PgeTest", runconfig_path=test_runconfig_path)

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

        self._set_algorithm_parameters_path(runconfig_path, self.restore_test_algorithm_param_path)

    def test_dswx_s1_pge_bad_algorithm_parameters_path(self):
        """Test for invalid path to 'algorithm_parameters' in SAS runconfig file"""
        runconfig_path = join(self.data_dir, 'test_dswx_s1_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_dswx_s1_config.yaml')

        self._set_algorithm_parameters_path(runconfig_path, self.test_algorithm_parameters_path)

        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)

        runconfig_dict['RunConfig']['Groups']['SAS']['runconfig']['groups']['dynamic_ancillary_file_group'] \
            ['algorithm_parameters'] = 'test/data/test_algorithm_parameters_non_existent.yaml'  # noqa E211

        with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        try:
            pge = DSWxS1Executor(pge_name="DswxS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

        finally:
            if exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

        self._set_algorithm_parameters_path(runconfig_path, self.restore_test_algorithm_param_path)

    def test_dswx_s1_pge_ancillary_input_validation(self):
        """Test validation checks made on the set of ancillary input files"""
        runconfig_path = join(self.data_dir, 'test_dswx_s1_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_dswx_s1_runconfig.yaml')

        self._set_algorithm_parameters_path(runconfig_path, self.test_algorithm_parameters_path)

        with open(runconfig_path, 'r', encoding='utf-8') as stream:
            runconfig_dict = yaml.safe_load(stream)

        ancillary_file_group_dict = \
            runconfig_dict['RunConfig']['Groups']['SAS']['runconfig']['groups']['dynamic_ancillary_file_group']

        # Test an invalid (missing) ancillary file
        ancillary_file_group_dict['dem_file'] = 'non_existent_dem.tif'

        with open(test_runconfig_path, 'w', encoding='utf-8') as input_path:
            yaml.safe_dump(runconfig_dict, input_path, sort_keys=False)

        try:
            pge = DSWxS1Executor(pge_name="DSWxS1PgeTest", runconfig_path=test_runconfig_path)

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

            self.assertIn("Could not locate specified input non_existent_dem.tif.", log_contents)

            # Reset to valid dem path
            ancillary_file_group_dict['dem_file'] = 'dswx_s1_pge_test/input_dir/dem.tif'

            # Test with an unexpected file extension
            os.system("touch dswx_s1_pge_test/input_dir/worldcover.vrt")
            ancillary_file_group_dict['worldcover_file'] = 'dswx_s1_pge_test/input_dir/worldcover.vrt'

            with open(test_runconfig_path, 'w', encoding='utf-8') as input_path:
                yaml.safe_dump(runconfig_dict, input_path, sort_keys=False)

            pge = DSWxS1Executor(pge_name="DSWxS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            # Open the log file, and check that the validation error details were captured
            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))
            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("Input file dswx_s1_pge_test/input_dir/worldcover.vrt "
                          "does not have an expected file extension.", log_contents)

            # Reset to valid worldcover_file path
            ancillary_file_group_dict['worldcover_file'] = 'dswx_s1_pge_test/input_dir/worldcover.tif'

            # Test with incomplete shoreline shapefile set
            os.system("touch dswx_s1_pge_test/input_dir/missing_shoreline.shp")
            ancillary_file_group_dict['shoreline_shapefile'] = 'dswx_s1_pge_test/input_dir/missing_shoreline.shp'

            with open(test_runconfig_path, 'w', encoding='utf-8') as input_path:
                yaml.safe_dump(runconfig_dict, input_path, sort_keys=False)

            pge = DSWxS1Executor(pge_name="DSWxS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            # Open the log file, and check that the validation error details were captured
            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))
            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("Additional shapefile dswx_s1_pge_test/input_dir/missing_shoreline.dbf "
                          "could not be located", log_contents)
        finally:

            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

        self._set_algorithm_parameters_path(runconfig_path, self.restore_test_algorithm_param_path)

    def test_dswx_s1_pge_input_validation(self):
        """Test the input validation checks made by DSWxS1PreProcessorMixin."""
        runconfig_path = join(self.data_dir, 'test_dswx_s1_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_dswx_s1_runconfig.yaml')

        self._set_algorithm_parameters_path(runconfig_path, self.test_algorithm_parameters_path)

        with open(runconfig_path, 'r', encoding='utf-8') as stream:
            runconfig_dict = yaml.safe_load(stream)

        input_files_group = runconfig_dict['RunConfig']['Groups']['PGE']['InputFilesGroup']

        # Test that a non-existent file path is detected by pre-processor
        input_files_group['InputFilePaths'] = ['temp/non_existent_file.tif']

        with open(test_runconfig_path, 'w', encoding='utf-8') as input_path:
            yaml.safe_dump(runconfig_dict, input_path, sort_keys=False)

        try:
            pge = DSWxS1Executor(pge_name="DSWxS1PgeTest", runconfig_path=test_runconfig_path)

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
                          f"{abspath('temp/non_existent_file.tif')}", log_contents)

            # Test that an input directory with no .tif files is caught
            input_files_group['InputFilePaths'] = ['dswx_s1_pge_test/scratch_dir']

            with open(test_runconfig_path, 'w', encoding='utf-8') as out_file:
                yaml.safe_dump(runconfig_dict, out_file, sort_keys=False)

            pge = DSWxS1Executor(pge_name="DSWxS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f"Input directory {abspath('dswx_s1_pge_test/scratch_dir')} "
                          f"does not contain any .tif files", log_contents)

            # Test that an input directory with no .h5 files is caught
            input_files_group['InputFilePaths'] = ['dswx_s1_pge_test/scratch_dir']

            os.system(f"touch {abspath('dswx_s1_pge_test/scratch_dir/test.tif')}")

            with open(test_runconfig_path, 'w', encoding='utf-8') as out_file:
                yaml.safe_dump(runconfig_dict, out_file, sort_keys=False)

            pge = DSWxS1Executor(pge_name="DSWxS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f"Input directory {abspath('dswx_s1_pge_test/scratch_dir')} "
                          f"does not contain any .h5 files", log_contents)

            # Lastly, check that a file that exists but is not a tif or an h5 is caught
            input_files_group['InputFilePaths'] = [runconfig_path]

            with open(test_runconfig_path, 'w', encoding='utf-8') as runconfig_fh:
                yaml.safe_dump(runconfig_dict, runconfig_fh, sort_keys=False)

            pge = DSWxS1Executor(pge_name="DSWxS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f"Input file {abspath(runconfig_path)} does not have "
                          f"an expected extension", log_contents)

        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

        self._set_algorithm_parameters_path(runconfig_path, self.restore_test_algorithm_param_path)

    def test_dswx_s1_pge_output_validation(self):
        """Test the output validation checks made by DSWxS1PostProcessorMixin."""
        runconfig_path = join(self.data_dir, 'test_dswx_s1_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_dswx_s1_runconfig.yaml')

        self._set_algorithm_parameters_path(runconfig_path, self.test_algorithm_parameters_path)

        with open(runconfig_path, 'r', encoding='utf-8') as stream:
            runconfig_dict = yaml.safe_load(stream)

        primary_executable_group = runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']

        # Set up an input directory empty of .tif files
        band_data = ()
        self.generate_band_data_output(band_data, clear=True)

        # Test with a SAS command that does not produce any output file,
        # post-processor should detect that expected output is missing
        primary_executable_group['ProgramPath'] = 'echo'
        primary_executable_group['ProgramOptions'] = ['hello world']

        with open(test_runconfig_path, 'w', encoding='utf-8') as config_fh:
            yaml.safe_dump(runconfig_dict, config_fh, sort_keys=False)

        try:
            pge = DSWxS1Executor(pge_name="DSWxS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("No SAS output file(s) with '.tif' extension found",
                          log_contents)

            # Test with a SAS command that produces the expected output files, but
            # with empty files (size 0 bytes). Post-processor should detect this
            # and flag an error
            band_data = ('OPERA_L3_DSWx-S1_b1_B01_WTR.tif',)
            self.generate_band_data_output(band_data, empty_file=True, clear=False)

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = DSWxS1Executor(pge_name="DSWxS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_output_file = 'dswx_s1_pge_test/output_dir/OPERA_L3_DSWx-S1_b1_B01_WTR.tif'
            self.assertTrue(os.path.exists(expected_output_file))

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f"SAS output file {abspath(expected_output_file)} was "
                          f"created, but is empty", log_contents)

            # Test a misnamed band file.  Post-processor should detect this and flag an error'
            band_data = ('OPERA_L3_DSWx-S1_b1_B01_WTR.tif', 'OPERA_L3_DSWx-S1_b1_B02_BWTR.tif',
                         'OPERA_L3_DSWx-S1_b1_B03_CONF.tif', 'OPERA_L3_DSWx-S1_b2_B01_WTR.tif',
                         'OPERA_L3_DSWx-S1_b2_B02_BWTR.tif', 'OPERA_L3_DSWx-S1_b2_B03_CON.tif')
            self.generate_band_data_output(band_data, clear=True)

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = DSWxS1Executor(pge_name="DSWxS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("Invalid SAS output file, too many band types:",
                          log_contents)

            # Test for missing or extra band files
            # Test a misnamed band file.  Post-processor should detect this and flag an error'
            band_data = ('OPERA_L3_DSWx-S1_b1_B01_WTR.tif', 'OPERA_L3_DSWx-S1_b1_B02_BWTR.tif',
                         'OPERA_L3_DSWx-S1_b1_B03_CONF.tif', 'OPERA_L3_DSWx-S1_b2_B01_WTR.tif',
                         'OPERA_L3_DSWx-S1_b2_B02_BWTR.tif')
            self.generate_band_data_output(band_data, clear=True)

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = DSWxS1Executor(pge_name="DSWxS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("Missing or extra band files: number of band files per band:",
                          log_contents)

        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

        self._set_algorithm_parameters_path(runconfig_path, self.restore_test_algorithm_param_path)


if __name__ == "__main__":
    unittest.main()
