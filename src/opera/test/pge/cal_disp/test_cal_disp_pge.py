#!/usr/bin/env python3

"""
====================
test_cal_disp_pge.py
====================
Unit tests for the pge/cal_disp/cal_disp_pge.py module.
"""

import os
import shutil
import tempfile
import unittest
from io import StringIO
from os.path import abspath, dirname, exists, join

from pkg_resources import resource_filename

from opera.pge import RunConfig
from opera.pge.cal_disp.cal_disp_pge import CalDispExecutor
from opera.util import PgeLogger
from opera.util.input_validation import validate_cal_inputs


class CalDispPgeTestCase(unittest.TestCase):
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
            prefix="test_cal_disp_pge_", suffix="_temp", dir=os.curdir
        )

        # Create the input dir expected by the test RunConfig and add a
        # dummy input file
        input_dir = join(self.working_dir.name, "cal_disp_pge_test/input_dir")
        os.makedirs(input_dir, exist_ok=True)

        # Copy the algorithm_parameters config file into the test input directory.
        shutil.copy(join(self.data_dir, 'test_cal_disp_algorithm_parameters.yaml'), input_dir)

        # Create non-empty dummy input files expected by test runconfig
        dummy_input_files = [
            'OPERA_L3_DISP-S1_IW_F08882_VV_20220111T002651Z_20220722T002657Z_v1.0_20251027T005420Z.nc',
            'OPERA_L3_DISP-S1-STATIC_F08882_20140403_S1A_v1.0_dem.tif',
            'OPERA_L3_DISP-S1-STATIC_F08882_20140403_S1A_v1.0_line_of_sight_enu.tif',
            'OPERA_L4_TROPO-ZENITH_20220111T000000Z_20250923T224940Z_HRES_v1.0.nc',
            'OPERA_L4_TROPO-ZENITH_20220722T000000Z_20250923T233421Z_HRES_v1.0.nc', 'unr/004420_IGS20.tenv8',
            'unr/004421_IGS20.tenv8', 'unr/004492_IGS20.tenv8', 'unr/grid_latlon_lookup_v0.2.txt',
        ]
        for dummy_input_file in dummy_input_files:
            if dirname(dummy_input_file) != '':
                os.makedirs(join(input_dir, dirname(dummy_input_file)), exist_ok=True)
            os.system(
                f"echo \"non-empty file\" > {join(input_dir, dummy_input_file)}"
            )

        os.chdir(self.working_dir.name)

    def tearDown(self) -> None:
        """Return to starting directory"""
        os.chdir(self.test_dir)
        self.working_dir.cleanup()

    def _compare_algorithm_parameters_runconfig_to_expected(self, runconfig):
        """
        Helper method to check the properties of a parsed algorithm parameters runconfig against the
        expected values as defined by the "valid" sample algorithm parameters runconfig files.
        """
        self.assertTrue(runconfig['unwrap_correction']['run_unwrap_correction'])
        self.assertEqual(runconfig['calibration_options']['cal_method'], 'savitsky_goley')
        self.assertTrue(runconfig['calibration_options']['run_interpolation'])
        self.assertTrue(runconfig['calibration_options']['run_interpolation'])
        self.assertEqual(runconfig['calibration_options']['downsample_factor'], 10)
        self.assertIsNone(runconfig['savitsky_goley_options']['window_x_size'])
        self.assertIsNone(runconfig['savitsky_goley_options']['window_y_size'])
        self.assertIsNone(runconfig['savitsky_goley_options']['window_overlap_x_size'])
        self.assertIsNone(runconfig['savitsky_goley_options']['window_overlap_y_size'])
        self.assertIsNone(runconfig['savitsky_goley_options']['window_extend_x_size'])
        self.assertIsNone(runconfig['savitsky_goley_options']['window_extend_y_size'])

    def test_cal_disp_pge_execution(self):
        """
        Test execution of the CalDispExecutor class and its associated mixins
        using a test RunConfig that creates dummy expected output files and logs
        a message to be captured by PgeLogger.
        """
        runconfig_path = join(self.data_dir, 'test_cal_disp_config.yaml')

        pge = CalDispExecutor(pge_name="CalDispPgeTest", runconfig_path=runconfig_path)

        # Check that basic attributes were initialized
        self.assertEqual(pge.name, "CAL-DISP")
        self.assertEqual(pge.pge_name, "CalDispPgeTest")
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
        expected_sas_config_file = join(pge.runconfig.scratch_path, 'test_cal_disp_config_sas.yaml')
        self.assertTrue(os.path.exists(expected_sas_config_file))

        # Check that the log file was created and moved into the output directory
        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        # Lastly, check that the dummy output products were created and renamed
        self.assertTrue(os.path.exists(join(pge.runconfig.output_product_path,
                                            'OPERA_L4_CAL-DISP-S1_IW_F08882_VV_20220111T002651Z_20220722T002657Z_v0.1_'
                                            '20260122T203124Z.nc')))
        self.assertTrue(os.path.exists(join(pge.runconfig.output_product_path,
                                            'OPERA_L4_CAL-DISP-S1_IW_F08882_VV_20220111T002651Z_20220722T002657Z_v0.1_'
                                            '20260122T203124Z.png')))

        # Open and read the log
        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn(f"CAL-DISP invoked with RunConfig {expected_sas_config_file}", log_contents)

    def test_cal_disp_algorithm_parameters(self):
        """Test basic parsing and validation of an algorithm parameters RunConfig file"""
        runconfig_path = join(self.data_dir, 'test_cal_disp_config.yaml')

        runconfig = RunConfig(runconfig_path)

        dynamic_ancillary_group = runconfig.sas_config['cal_disp_workflow']['dynamic_ancillary_group']
        algorithm_parameters_runconfig_file = dynamic_ancillary_group['algorithm_parameters_file']

        self.assertIsNotNone(algorithm_parameters_runconfig_file)

        # parse the run config file
        runconfig_dict = runconfig._parse_algorithm_parameters_run_config_file(algorithm_parameters_runconfig_file)

        # Check the properties of the algorithm parameters RunConfig to ensure they match as expected
        self._compare_algorithm_parameters_runconfig_to_expected(runconfig_dict)

    def test_cal_disp_pge_validate_inputs(self):
        """
        Test that the CAL-DISP PGE Preprocessor is able to detect invalid input files: non-existent files,
        empty files, invalid extensions.
        """

        # Test non-existent file detection

        test_filename = 'non_existent_disp_file.nc'
        sas_config = {
            'cal_disp_workflow': {
                'input_file_group': {
                    'disp_file': test_filename,
                },
                'dynamic_ancillary_group': {},
                'static_ancillary_group': {},
            }
        }
        runconfig = MockRunConfig(sas_config)
        logger = PgeLogger()
        with self.assertRaises(RuntimeError):
            validate_cal_inputs(runconfig, logger, 'CAL-DISP')

        # Check to see that the RuntimeError is as expected
        logger.close_log_stream()
        log_file = logger.get_file_name()
        self.assertTrue(exists(log_file))
        with open(log_file, 'r', encoding='utf-8') as lfile:
            log = lfile.read()
        self.assertIn(f'Could not locate specified input {test_filename}.', log)

        # Test invalid extensions

        with tempfile.TemporaryDirectory(dir=self.test_dir) as tmp_dir:
            logger = PgeLogger()
            test_filename = join(
                tmp_dir, 'OPERA_L3_DISP-S1_IW_F08882_VV_20220111T002651Z_20220722T002657Z_v1.0_20251027T005420Z.h5'
            )
            with open(test_filename, 'w') as ief:
                ief.write('\n')
            sas_config['cal_disp_workflow']['input_file_group']['disp_file'] = test_filename

            runconfig = MockRunConfig(sas_config)
            with self.assertRaises(RuntimeError):
                validate_cal_inputs(runconfig, logger, "CAL-DISP")

            # Check to see that the RuntimeError is as expected
            logger.close_log_stream()
            log_file = logger.get_file_name()
            self.assertTrue(exists(log_file))
            with open(log_file, 'r', encoding='utf-8') as lfile:
                log = lfile.read()
            self.assertIn(f'Input file {test_filename} does not have an expected file extension', log)
            os.remove(test_filename)

            # Test for empty files

            logger = PgeLogger()
            test_filename = join(
                tmp_dir, 'OPERA_L3_DISP-S1_IW_F08882_VV_20220111T002651Z_20220722T002657Z_v1.0_20251027T005420Z.nc'
            )
            open(test_filename, 'w').close()
            sas_config['cal_disp_workflow']['input_file_group']['disp_file'] = test_filename

            runconfig = MockRunConfig(sas_config)
            with self.assertRaises(RuntimeError):
                validate_cal_inputs(runconfig, logger, "CAL-DISP")

            # Check to see that the RuntimeError is as expected
            logger.close_log_stream()
            log_file = logger.get_file_name()
            self.assertTrue(exists(log_file))
            with open(log_file, 'r', encoding='utf-8') as lfile:
                log = lfile.read()
            self.assertIn(f'Input file {test_filename} size is 0. Size must be greater than 0.', log)
            os.remove(test_filename)

            # Test all files

            test_disp_file = test_filename
            test_dem_file = join(tmp_dir, 'OPERA_L3_DISP-S1-STATIC_F08882_20140403_S1A_v1.0_dem.tif')
            test_los_file = join(tmp_dir, 'OPERA_L3_DISP-S1-STATIC_F08882_20140403_S1A_v1.0_line_of_sight_enu.tif')
            test_tropo_files = [
                join(tmp_dir, 'OPERA_L4_TROPO-ZENITH_20220111T000000Z_20250923T224940Z_HRES_v1.0.nc'),
                join(tmp_dir, 'OPERA_L4_TROPO-ZENITH_20220722T000000Z_20250923T233421Z_HRES_v1.0.nc'),
            ]

            unr_dir = join(tmp_dir, 'unr')
            os.makedirs(unr_dir, exist_ok=True)

            test_unr_files = [
                join(unr_dir, '004420_IGS20.tenv8'),
                join(unr_dir, '004421_IGS20.tenv8'),
                join(unr_dir, '004492_IGS20.tenv8'),
            ]
            test_unr_ref_file = join(unr_dir, 'grid_latlon_lookup_v0.2.txt')

            test_files = ([test_disp_file, test_dem_file, test_los_file, test_unr_ref_file] +
                          test_tropo_files + test_unr_files)

            for test_f in test_files:
                with open(test_f, 'w') as ief:
                    ief.write('\n')
                self.assertTrue(exists(test_f))

            sas_config = {
                'cal_disp_workflow': {
                    'input_file_group': {
                        'disp_file': test_filename,
                        'unr_grid_latlon_file': test_unr_ref_file,
                        'unr_timeseries_dir': unr_dir
                    },
                    'dynamic_ancillary_group': {
                        'static_los_file': test_los_file,
                        'static_dem_file': test_dem_file,
                        'ref_tropo_files': [test_tropo_files[0]],
                        'sec_tropo_files': [test_tropo_files[1]],
                    },
                    'static_ancillary_group': {},
                }
            }

            runconfig = MockRunConfig(sas_config)
            logger = PgeLogger()

            validate_cal_inputs(runconfig, logger, "CAL-DISP")

            for test_f in test_files:
                os.remove(test_f)


class MockRunConfig:
    """Mock runconfig for testing"""

    def __init__(self, sas_config):
        self._sas_config_dict = sas_config

    @property
    def sas_config(self):
        """Return a simple test runconfig dictionary"""
        return self._sas_config_dict
