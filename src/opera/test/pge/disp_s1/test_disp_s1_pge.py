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
from opera.util.input_validation import validate_disp_inputs
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

        os.system(
            f"echo \"non-empty file\" > {join(input_dir, 'compressed_slc_t087_185678_iw2_20180101_20180210.h5')}"
        )

        os.system(
            f"echo \"non-empty file\" > {join(input_dir, 't087_185678_iw2_amp_dispersion.tif')}"
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


    def test_validate_disp_inputs(self):
        """
        Test that the validate_disp_inputs function is able to detect non-existent files,
        zero-size files, and invalid extensions in filenames. Also check that
        valid files pass validation.
        """

        # Test non-existent file detection
        test_filename = 'non_existent_input_file'
        sas_config = {
            'runconfig' : {
                'groups' : {
                    'input_file_group' : {
                        'cslc_file_list' : [
                            test_filename
                        ]
                    },
                    'dynamic_ancillary_file_group' : {
                    }
                }
            }
        }
        runconfig = MockRunConfig(sas_config)
        logger = PgeLogger()
        with self.assertRaises(RuntimeError):
            validate_disp_inputs(runconfig, logger, "DISP-S1")

        # Check to see that the RuntimeError is as expected
        logger.close_log_stream()
        log_file = logger.get_file_name()
        self.assertTrue(exists(log_file))
        with open(log_file, 'r', encoding='utf-8') as lfile:
            log = lfile.read()
        self.assertIn(f'Could not locate specified input {test_filename}.', log)

        # Test invalid file extension
        logger = PgeLogger()
        test_filename = "test invalid extension.inv"
        with open(test_filename, 'w') as ief:
            ief.write("\n")
        sas_config['runconfig']['groups']['input_file_group']['cslc_file_list'] = [test_filename]
        runconfig = MockRunConfig(sas_config)
        with self.assertRaises(RuntimeError):
            validate_disp_inputs(runconfig, logger, "DISP-S1")

        # Check to see that the RuntimeError is as expected
        logger.close_log_stream()
        log_file = logger.get_file_name()
        self.assertTrue(exists(log_file))
        with open(log_file, 'r', encoding='utf-8') as lfile:
            log = lfile.read()
        self.assertIn(f'Input file {test_filename} does not have an expected file extension', log)
        os.remove(test_filename)

        # Test for non-zero file size
        logger = PgeLogger()
        test_filename = "zero size file.h5"
        open(test_filename, 'w').close()
        self.assertTrue(exists(test_filename))
        sas_config['runconfig']['groups']['input_file_group']['cslc_file_list'] = [test_filename]
        runconfig = MockRunConfig(sas_config)
        with self.assertRaises(RuntimeError):
            validate_disp_inputs(runconfig, logger, "DISP-S1")

        # Check to see that the RuntimeError is as expected
        logger.close_log_stream()
        log_file = logger.get_file_name()
        self.assertTrue(exists(log_file))
        with open(log_file, 'r', encoding='utf-8') as lfile:
            log = lfile.read()
        self.assertIn(f'Input file {test_filename} size is 0. Size must be greater than 0.', log)
        os.remove(test_filename)

        # Test all input files with valid files
        cslc_file_list = ['t087_185678_iw2_20180222_VV.h5', 't087_185687_iw1_20180716_VV.h5']
        for f in cslc_file_list:
            with open(f, 'w') as wf:
                wf.write('\n')
        sas_config['runconfig']['groups']['input_file_group']['cslc_file_list'] = cslc_file_list

        sas_config['runconfig']['groups']['dynamic_ancillary_file_group'] = {}
        amplitude_dispersion_files = ['t087_185678_iw2_amp_dispersion.tif', 't087_185687_iw1_amp_dispersion.tif']
        for f in amplitude_dispersion_files:
            with open(f, 'w') as wf:
                wf.write('\n')
        sas_config['runconfig']['groups']['dynamic_ancillary_file_group']['amplitude_dispersion_files'] = amplitude_dispersion_files

        amplitude_mean_files = ['t087_185678_iw2_amp_mean.tif', 't087_185687_iw1_amp_mean.tif']
        for f in amplitude_mean_files:
            with open(f, 'w') as wf:
                wf.write('\n')
        sas_config['runconfig']['groups']['dynamic_ancillary_file_group']['amplitude_mean_files'] = amplitude_mean_files

        geometry_files = ['t087_185678_iw2_topo.h5', 't087_185687_iw1_topo.h5']
        for f in geometry_files:
            with open(f, 'w') as wf:
                wf.write('\n')
        sas_config['runconfig']['groups']['dynamic_ancillary_file_group']['geometry_files'] = geometry_files

        mask_files = ['water_mask.tif']
        for f in mask_files:
            with open(f, 'w') as wf:
                wf.write('\n')
        sas_config['runconfig']['groups']['dynamic_ancillary_file_group']['mask_file'] = mask_files

        dem_file = 'dem.tif'
        with open(dem_file, 'w') as wf:
            wf.write('\n')
        sas_config['runconfig']['groups']['dynamic_ancillary_file_group']['dem_file'] = dem_file

        tec_files = ['jplg0410.18i.Z', 'jplg1970.18i.Z']
        for f in tec_files:
            with open(f, 'w') as wf:
                wf.write('\n')
        sas_config['runconfig']['groups']['dynamic_ancillary_file_group']['tec_files'] = tec_files

        weather_model_files = ['GMAO_tropo_20180210T000000_ztd.nc', 'GMAO_tropo_20180716T000000_ztd.nc']
        for f in weather_model_files:
            with open(f, 'w') as wf:
                wf.write('\n')
        sas_config['runconfig']['groups']['dynamic_ancillary_file_group']['weather_model_files'] = weather_model_files

        logger = PgeLogger()
        runconfig = MockRunConfig(sas_config)
        validate_disp_inputs(runconfig, logger, "DISP-S1")

        logger.close_log_stream()
        log_file = logger.get_file_name()
        self.assertTrue(exists(log_file))
        with open(log_file, 'r', encoding='utf-8') as lfile:
            log = lfile.read()
        print("begin log contents")
        print(log)
        print("end log contents")
        self.assertIn('overall.log_messages.debug: 0', log)
        self.assertIn('overall.log_messages.info: 0', log)
        self.assertIn('overall.log_messages.warning: 0', log)
        self.assertIn('overall.log_messages.critical: 0', log)

        files_to_remove = (cslc_file_list + amplitude_dispersion_files +
                          amplitude_mean_files + geometry_files + mask_files +
                          tec_files + weather_model_files)
        files_to_remove.append(dem_file)
        for f in files_to_remove:
            os.remove(f)


class MockRunConfig:
    """Mock runconfig for testing"""

    def __init__(self, sas_config):
        self._sas_config_dict = sas_config

    @property
    def sas_config(self):
        return self._sas_config_dict


if __name__ == "__main__":
    unittest.main()
