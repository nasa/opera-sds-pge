#!/usr/bin/env python3

"""
===================
test_disp_s1_pge.py
===================
Unit tests for the pge/disp_s1/disp_s1_pge.py module.
"""

import glob
import os
import shutil
import tempfile
import unittest
from io import StringIO
from os.path import abspath, exists, join
from subprocess import CompletedProcess, Popen
from unittest.mock import patch

from pkg_resources import resource_filename

import pytest

import yaml

import opera.pge.disp_s1.disp_s1_pge
from opera.pge import RunConfig
from opera.pge.disp_s1.disp_s1_pge import DispS1Executor
from opera.util import PgeLogger
from opera.util.h5_utils import create_test_cslc_metadata_product
from opera.util.h5_utils import create_test_disp_metadata_product
from opera.util.h5_utils import get_disp_s1_product_metadata
from opera.util.input_validation import validate_disp_inputs
from opera.util.render_jinja2 import UNDEFINED_ERROR


def mock_grib_to_netcdf(*popenargs, input=None, capture_output=False, timeout=None, check=False, **kwargs):
    """
    Mack grit_to_netcdf function.
    We are mocking the implementation of subprocess.run(), the function
    arguments are therefore those of the subprocess.run() command.
    The 'else' statement is added because the 'time_and_execute' function
    in run_utils.py uses the actual subprocess.run() command, so when it gets
    here we do not want this mocked version to run.

    """
    if popenargs[0][0].endswith("grib_to_netcdf"):
        output_path = popenargs[0][4]
        open(output_path, 'w').close()
    else:
        with Popen(*popenargs, **kwargs) as process:
            try:
                stdout, stderr = process.communicate(input, timeout=timeout)
            except:  # Including KeyboardInterrupt, communicate handled that.
                process.kill()
                # We don't call process.wait() as .__exit__ does that for us.
                raise

            retcode = process.poll()
            return CompletedProcess(process.args, retcode, stdout, stderr)


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

        # Copy the algorithm_parameters config file into the test input directory.
        shutil.copy(join(self.data_dir, 'test_disp_s1_algorithm_parameters.yaml'), input_dir)

        # Create non-empty dummy input files expected by test runconfig
        dummy_input_files = ['compressed_slc_t087_185678_iw2_20180101_20180210.h5',
                             'dem.tif', 'water_mask.tif',
                             't087_185678_iw2_topo.h5',
                             'jplg0410.18i.Z',
                             'GMAO_tropo_20180210T000000_ztd.nc',
                             'ERA5_N30_N40_W120_W110_20221119_14.grb',
                             'ERA5_N30_N40_W120_W110_20221201_14.grb',
                             'opera-s1-disp-frame-to-burst.json',
                             'opera-disp-s1-reference-dates.json',
                             'opera-disp-s1-algorithm-parameters-overrides.json']
        for dummy_input_file in dummy_input_files:
            os.system(
                f"echo \"non-empty file\" > {join(input_dir, dummy_input_file)}"
            )

        # Create a dummy input CSLC product with realistic metadata
        create_test_cslc_metadata_product(join(input_dir, 't087_185678_iw2_20180222.h5'))

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
        self.assertEqual(runconfig['algorithm_parameters_overrides_json'], "opera-disp-s1-algorithm-parameters-overrides-2024-10-14.json")
        self.assertEqual(runconfig['ps_options']['amp_dispersion_threshold'], 0.25)
        self.assertEqual(runconfig['phase_linking']['ministack_size'], 1000)
        self.assertEqual(runconfig['phase_linking']['max_num_compressed'], 5)
        self.assertEqual(runconfig['phase_linking']['output_reference_idx'], 0)
        self.assertEqual(runconfig['phase_linking']['half_window']['x'], 11)
        self.assertEqual(runconfig['phase_linking']['half_window']['y'], 5)
        self.assertEqual(runconfig['phase_linking']['use_evd'], False)
        self.assertEqual(runconfig['phase_linking']['beta'], 0.0)
        self.assertEqual(runconfig['phase_linking']['zero_correlation_threshold'], 0.0)
        self.assertEqual(runconfig['phase_linking']['shp_method'], 'glrt')
        self.assertEqual(runconfig['phase_linking']['shp_alpha'], 0.005)
        self.assertEqual(runconfig['phase_linking']['mask_input_ps'], False)
        self.assertEqual(runconfig['phase_linking']['baseline_lag'], None)
        self.assertEqual(runconfig['phase_linking']['compressed_slc_plan'], "always_first")
        self.assertEqual(runconfig['interferogram_network']['reference_idx'], None)
        self.assertEqual(runconfig['interferogram_network']['max_bandwidth'], None)
        self.assertEqual(runconfig['interferogram_network']['max_temporal_baseline'], None)
        self.assertListEqual(runconfig['interferogram_network']['indexes'], [[0, -1]])
        self.assertEqual(runconfig['unwrap_options']['run_unwrap'], True)
        self.assertEqual(runconfig['unwrap_options']['run_goldstein'], False)
        self.assertEqual(runconfig['unwrap_options']['run_interpolation'], False)
        self.assertEqual(runconfig['unwrap_options']['unwrap_method'], 'phass')
        self.assertEqual(runconfig['unwrap_options']['n_parallel_jobs'], 1)
        self.assertEqual(runconfig['unwrap_options']['zero_where_masked'], False)
        self.assertEqual(runconfig['unwrap_options']['preprocess_options']['alpha'], 0.5)
        self.assertEqual(runconfig['unwrap_options']['preprocess_options']['max_radius'], 51)
        self.assertEqual(runconfig['unwrap_options']['preprocess_options']['interpolation_cor_threshold'], 0.5)
        self.assertEqual(runconfig['unwrap_options']['preprocess_options']['interpolation_similarity_threshold'], 0.4)
        self.assertListEqual(runconfig['unwrap_options']['snaphu_options']['ntiles'], [5, 5])
        self.assertListEqual(runconfig['unwrap_options']['snaphu_options']['tile_overlap'], [0, 0])
        self.assertEqual(runconfig['unwrap_options']['snaphu_options']['n_parallel_tiles'], 1)
        self.assertEqual(runconfig['unwrap_options']['snaphu_options']['init_method'], 'mcf')
        self.assertEqual(runconfig['unwrap_options']['snaphu_options']['cost'], 'smooth')
        self.assertEqual(runconfig['unwrap_options']['snaphu_options']['single_tile_reoptimize'], False)
        self.assertListEqual(runconfig['unwrap_options']['tophu_options']['ntiles'], [5, 5])
        self.assertListEqual(runconfig['unwrap_options']['tophu_options']['downsample_factor'], [5, 5])
        self.assertEqual(runconfig['unwrap_options']['tophu_options']['init_method'], 'mcf')
        self.assertEqual(runconfig['unwrap_options']['tophu_options']['cost'], 'smooth')
        self.assertEqual(runconfig['unwrap_options']['spurt_options']['temporal_coherence_threshold'], 0.6)
        self.assertEqual(runconfig['unwrap_options']['spurt_options']['similarity_threshold'], 0.5)
        self.assertEqual(runconfig['unwrap_options']['spurt_options']['general_settings']['use_tiles'], True)
        self.assertEqual(runconfig['unwrap_options']['spurt_options']['tiler_settings']['max_tiles'], 16)
        self.assertEqual(runconfig['unwrap_options']['spurt_options']['tiler_settings']['target_points_for_generation'],
                         120000)
        self.assertEqual(runconfig['unwrap_options']['spurt_options']['tiler_settings']['target_points_per_tile'],
                         800000)
        self.assertEqual(runconfig['unwrap_options']['spurt_options']['tiler_settings']['dilation_factor'], 0.05)
        self.assertEqual(runconfig['unwrap_options']['spurt_options']['solver_settings']['t_worker_count'], 1)
        self.assertEqual(runconfig['unwrap_options']['spurt_options']['solver_settings']['s_worker_count'], 1)
        self.assertEqual(runconfig['unwrap_options']['spurt_options']['solver_settings']['links_per_batch'], 50000)
        self.assertEqual(runconfig['unwrap_options']['spurt_options']['solver_settings']['t_cost_type'], 'constant')
        self.assertEqual(runconfig['unwrap_options']['spurt_options']['solver_settings']['t_cost_scale'], 100.0)
        self.assertEqual(runconfig['unwrap_options']['spurt_options']['solver_settings']['s_cost_type'], 'constant')
        self.assertEqual(runconfig['unwrap_options']['spurt_options']['solver_settings']['s_cost_scale'], 100.0)
        self.assertEqual(runconfig['unwrap_options']['spurt_options']['solver_settings']['num_parallel_tiles'], 1)
        self.assertEqual(runconfig['unwrap_options']['spurt_options']['merger_settings']['min_overlap_points'], 25)
        self.assertEqual(runconfig['unwrap_options']['spurt_options']['merger_settings']['method'], 'dirichlet')
        self.assertEqual(runconfig['unwrap_options']['spurt_options']['merger_settings']['bulk_method'], 'L2')
        self.assertEqual(runconfig['unwrap_options']['spurt_options']['merger_settings']['num_parallel_ifgs'], 13)
        self.assertEqual(runconfig['output_options']['output_resolution'], None)
        self.assertEqual(runconfig['output_options']['strides']['x'], 6)
        self.assertEqual(runconfig['output_options']['strides']['y'], 3)
        self.assertEqual(runconfig['output_options']['bounds'], None)
        self.assertEqual(runconfig['output_options']['bounds_wkt'], None)
        self.assertEqual(runconfig['output_options']['bounds_epsg'], 4326)
        self.assertListEqual(runconfig['output_options']['hdf5_creation_options']['chunks'], [128, 128])
        self.assertEqual(runconfig['output_options']['hdf5_creation_options']['compression'], 'gzip')
        self.assertEqual(runconfig['output_options']['hdf5_creation_options']['compression_opts'], 4)
        self.assertEqual(runconfig['output_options']['hdf5_creation_options']['shuffle'], True)
        self.assertListEqual(runconfig['output_options']['gtiff_creation_options'],
                             ['COMPRESS=lzw', 'ZLEVEL=4', 'BIGTIFF=yes',
                              'TILED=yes', 'INTERLEAVE=band', 'BLOCKXSIZE=128', 'BLOCKYSIZE=128'])
        self.assertEqual(runconfig['output_options']['add_overviews'], True)
        self.assertListEqual(runconfig['output_options']['overview_levels'], [4, 8, 16, 32, 64])
        self.assertEqual(runconfig['output_options']['extra_reference_date'], None)
        self.assertEqual(runconfig['subdataset'], '/data/VV')
        self.assertEqual(runconfig['spatial_wavelength_cutoff'], 25000.0)
        self.assertListEqual(runconfig['browse_image_vmin_vmax'], [-0.1, 0.1])

    @patch.object(opera.pge.disp_s1.disp_s1_pge.subprocess, "run", mock_grib_to_netcdf)
    def test_disp_s1_pge_execution(self):
        """
        Test execution of the DispS1Executor class and its associated mixins
        using a test RunConfig that creates dummy expected output files and logs
        a message to be captured by PgeLogger.
        """
        runconfig_path = join(self.data_dir, 'test_disp_s1_config.yaml')

        pge = DispS1Executor(pge_name="DispS1PgeTest", runconfig_path=runconfig_path)

        # Check that basic attributes were initialized
        self.assertEqual(pge.name, "DISP-S1")
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

        # Check that the catalog metadata file was created in the output directory
        expected_catalog_metadata_file = join(
            pge.runconfig.output_product_path, pge._catalog_metadata_filename())
        self.assertTrue(os.path.exists(expected_catalog_metadata_file))

        expected_inter_filename = abspath("disp_s1_pge_test/output_dir/20170217_20170430.nc")
        expected_browse_filename = abspath("disp_s1_pge_test/output_dir/20170217_20170430.displacement.png")

        # Check that the ISO metadata file was created and all placeholders were
        # filled in
        expected_iso_metadata_file = join(
            pge.runconfig.output_product_path, pge._iso_metadata_filename(expected_inter_filename))
        self.assertTrue(os.path.exists(expected_iso_metadata_file))

        # Check that the log file was created and moved into the output directory
        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        # Lastly, check that the dummy output products were created and renamed
        expected_disp_product = join(
            pge.runconfig.output_product_path,
            pge._netcdf_filename(
                inter_filename=expected_inter_filename
            )
        )
        self.assertTrue(os.path.exists(expected_disp_product))

        expected_browse_product = join(
            pge.runconfig.output_product_path,
            pge._browse_filename(
                inter_filename=expected_browse_filename
            )
        )
        self.assertTrue(os.path.exists(expected_browse_product))

        for compressed_cslc in ['compressed_t027_056725_iw1_20170217_20170217_20170430.h5',
                                'compressed_t027_056726_iw1_20170217_20170217_20170430.h5']:
            expected_compressed_cslc_product = join(
                pge.runconfig.output_product_path,
                pge._compressed_cslc_filename(compressed_cslc)
            )
            self.assertTrue(os.path.exists(expected_compressed_cslc_product))

        # Open and read the log
        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn(f"DISP-S1 invoked with RunConfig {expected_sas_config_file}", log_contents)

    @patch.object(opera.pge.disp_s1.disp_s1_pge.subprocess, "run", mock_grib_to_netcdf)
    def test_filename_application(self):
        """Test the filename convention applied to DISP output products"""
        runconfig_path = join(self.data_dir, 'test_disp_s1_config.yaml')

        pge = DispS1Executor(pge_name="DispS1PgeTest", runconfig_path=runconfig_path)

        pge.run()

        # Check that the file naming is correct
        output_dir = abspath(pge.runconfig.output_product_path)
        nc_files = glob.glob(join(output_dir, '*.nc'))
        nc_file = nc_files[0]

        expected_disp_filename = pge._netcdf_filename(
            inter_filename=abspath("disp_s1_pge_test/output_dir/20170217_20170430.nc")
        )

        self.assertEqual(os.path.basename(nc_file), expected_disp_filename)

        disp_metadata = get_disp_s1_product_metadata(nc_file)

        self.assertRegex(
            expected_disp_filename,
            rf'{pge.PROJECT}_{pge.LEVEL}_{pge.NAME}_'
            rf'IW_F{disp_metadata["identification"]["frame_id"]:05d}_VV_'
            rf'\d{{8}}T\d{{6}}Z_\d{{8}}T\d{{6}}Z_'
            rf'v{disp_metadata["identification"]["product_version"]}_'
            rf'\d{{8}}T\d{{6}}Z.nc'
        )

        expected_browse_filename = pge._browse_filename(
            inter_filename=abspath("disp_s1_pge_test/output_dir/20170217_20170430.displacement.png")
        )

        self.assertRegex(
            expected_browse_filename,
            rf'{pge.PROJECT}_{pge.LEVEL}_{pge.NAME}_'
            rf'IW_F{disp_metadata["identification"]["frame_id"]:05d}_VV_'
            rf'\d{{8}}T\d{{6}}Z_\d{{8}}T\d{{6}}Z_'
            rf'v{disp_metadata["identification"]["product_version"]}_'
            rf'\d{{8}}T\d{{6}}Z_BROWSE.png'
        )

        # Repeat tests for the Compressed CSLC product
        h5_files = glob.glob(join(output_dir, '*.h5'))
        h5_file = sorted(h5_files)[0]

        expected_ccslc_filename = pge._compressed_cslc_filename(
            inter_filename="disp_s1_pge_test/output_dir/compressed_slcs/"
                           "compressed_t027_056725_iw1_20170217_20170217_20170430.h5"
        )

        self.assertEqual(os.path.basename(h5_file), expected_ccslc_filename)

        self.assertRegex(
            expected_ccslc_filename,
            rf'{pge.PROJECT}_L2_COMPRESSED-CSLC-S1_'
            rf'\w{{4}}-\w{{6}}-\w{{3}}_'
            rf'\d{{8}}T\d{{6}}Z_\d{{8}}T\d{{6}}Z_'
            rf'\d{{8}}T\d{{6}}Z_\d{{8}}T\d{{6}}Z_'
            rf'VV_v1.0.h5'
        )

    @patch.object(opera.pge.disp_s1.disp_s1_pge.subprocess, "run", mock_grib_to_netcdf)
    def test_iso_metadata_creation(self):
        """
        Test that the ISO metadata template is fully filled out when realistic
        DISP-S1 product metadata is available.
        """
        runconfig_path = join(self.data_dir, 'test_disp_s1_config.yaml')

        pge = DispS1Executor(pge_name="DispS1PgeTest", runconfig_path=runconfig_path)

        # Run only the pre-processor steps to ingest the runconfig and set
        # up directories
        pge.run_preprocessor()

        # Create a sample metadata file within the output directory of the PGE
        output_dir = join(os.curdir, "disp_s1_pge_test/output_dir")

        disp_metadata_path = abspath(join(output_dir, '20170217_20170430.nc'))

        create_test_disp_metadata_product(disp_metadata_path)

        disp_metadata = pge._collect_disp_s1_product_metadata(disp_metadata_path)

        iso_metadata = pge._create_iso_metadata(disp_metadata_path, disp_metadata)

        self.assertNotIn(UNDEFINED_ERROR, iso_metadata)

        os.unlink(disp_metadata_path)

        # Test no file from which to extract data
        disp_metadata_path = join(output_dir, 'No_file.nc')

        with self.assertRaises(RuntimeError):
            pge._collect_disp_s1_product_metadata(disp_metadata_path)

        # Verify the proper Runtime error message
        log_file = pge.logger.get_file_name()
        self.assertTrue(exists(log_file))
        with open(log_file, 'r', encoding='utf-8') as l_file:
            log = l_file.read()
        self.assertIn(f'Failed to extract metadata from {disp_metadata_path}', log)

    def test_validate_algorithm_parameters_config(self):
        """Test basic parsing and validation of an algorithm parameters RunConfig file"""
        runconfig_path = join(self.data_dir, 'test_disp_s1_config.yaml')

        self.runconfig = RunConfig(runconfig_path)

        algorithm_parameters_runconfig_file = self.runconfig.algorithm_parameters_file_config_path

        # parse the run config file
        runconfig_dict = self.runconfig._parse_algorithm_parameters_run_config_file(algorithm_parameters_runconfig_file)

        # Check the properties of the algorithm parameters RunConfig to ensure they match as expected
        self._compare_algorithm_parameters_runconfig_to_expected(runconfig_dict)

    @patch.object(opera.pge.disp_s1.disp_s1_pge.subprocess, "run", mock_grib_to_netcdf)
    def test_bad_algorithm_parameters_schema_path(self):
        """
        Test for invalid path in the optional 'AlgorithmParametersSchemaPath'
        section of in the PGE runconfig file.

        Also test for no AlgorithmParametersSchemaPath
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

    def test_disp_s1_pge_validate_inputs(self):
        """
        Test that the validate_disp_inputs function is able to detect non-existent files,
        zero-size files, and invalid extensions in filenames. Also check that
        valid files pass validation.
        """
        # Test non-existent file detection
        test_filename = 't087_123456_iw2_non_existent_input_file'
        sas_config = {
            'input_file_group': {
                'cslc_file_list': [
                    test_filename
                ]
            },
            'dynamic_ancillary_file_group': {
            },
            'static_ancillary_file_group': {
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
        test_filename = "t087_123456_iw2_test_invalid_extension.inv"
        with open(test_filename, 'w') as ief:
            ief.write("\n")
        sas_config['input_file_group']['cslc_file_list'] = [test_filename]
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
        test_filename = "t087_123456_iw2_zero_size_file.h5"
        open(test_filename, 'w').close()
        self.assertTrue(exists(test_filename))
        sas_config['input_file_group']['cslc_file_list'] = [test_filename]
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
        sas_config['input_file_group']['cslc_file_list'] = cslc_file_list

        sas_config['dynamic_ancillary_file_group'] = {}
        amplitude_dispersion_files = ['t087_185678_iw2_amp_dispersion.tif', 't087_185687_iw1_amp_dispersion.tif']
        for f in amplitude_dispersion_files:
            with open(f, 'w') as wf:
                wf.write('\n')
        sas_config['dynamic_ancillary_file_group']['amplitude_dispersion_files'] = amplitude_dispersion_files

        amplitude_mean_files = ['t087_185678_iw2_amp_mean.tif', 't087_185687_iw1_amp_mean.tif']
        for f in amplitude_mean_files:
            with open(f, 'w') as wf:
                wf.write('\n')
        sas_config['dynamic_ancillary_file_group']['amplitude_mean_files'] = amplitude_mean_files

        static_layer_files = ['t087_185678_iw2_topo.h5', 't087_185687_iw1_topo.h5']
        for f in static_layer_files:
            with open(f, 'w') as wf:
                wf.write('\n')
        sas_config['dynamic_ancillary_file_group']['static_layers_files'] = static_layer_files

        mask_file = 'water_mask.tif'
        with open(mask_file, 'w') as wf:
            wf.write('\n')
        sas_config['dynamic_ancillary_file_group']['mask_file'] = mask_file

        dem_file = 'dem.tif'
        with open(dem_file, 'w') as wf:
            wf.write('\n')
        sas_config['dynamic_ancillary_file_group']['dem_file'] = dem_file

        ionosphere_files = ['jplg0410.18i.Z', 'jplg1970.18i.Z']
        for f in ionosphere_files:
            with open(f, 'w') as wf:
                wf.write('\n')
        sas_config['dynamic_ancillary_file_group']['ionosphere_files'] = ionosphere_files

        troposphere_files = ['GMAO_tropo_20180210T000000_ztd.nc', 'GMAO_tropo_20180716T000000_ztd.nc',
                             'ERA5_N30_N40_W120_W110_20221119_14.grb', 'ERA5_N30_N40_W120_W110_20221201_14.grb']
        for f in troposphere_files:
            with open(f, 'w') as wf:
                wf.write('\n')
        sas_config['dynamic_ancillary_file_group']['troposphere_files'] = troposphere_files

        frame_to_burst_file = 'opera-s1-disp-frame-to-burst.json'
        with open(frame_to_burst_file, 'w') as wf:
            wf.write('\n')
        sas_config['static_ancillary_file_group']['frame_to_burst_json'] = frame_to_burst_file

        logger = PgeLogger()
        runconfig = MockRunConfig(sas_config)
        validate_disp_inputs(runconfig, logger, "DISP-S1")

        logger.close_log_stream()
        log_file = logger.get_file_name()
        self.assertTrue(exists(log_file))
        with open(log_file, 'r', encoding='utf-8') as lfile:
            log = lfile.read()
        self.assertIn('overall.log_messages.debug: 0', log)
        self.assertIn('overall.log_messages.info: 0', log)
        self.assertIn('overall.log_messages.warning: 0', log)
        self.assertIn('overall.log_messages.critical: 0', log)

        files_to_remove = (cslc_file_list + amplitude_dispersion_files +
                           amplitude_mean_files + static_layer_files +
                           ionosphere_files + troposphere_files)
        files_to_remove.append(mask_file)
        files_to_remove.append(dem_file)
        files_to_remove.append(frame_to_burst_file)
        for f in files_to_remove:
            os.remove(f)

    def test_get_cslc_input_burst_id_set(self):
        """
        Set of tests to sanity check the burst ids associated with:
        cslc_input_files, amplitude_dispersion_files, amplitude_mean_files,
        and geometry_files.
        """

        def get_sample_input_files(file_type: str) -> list:
            """Helper function for test_get_cslc_input_burst_id_set()"""
            if file_type == 'compressed':
                return ['compressed_slc_t087_185683_iw2_220180101_20180210.h5',
                        'compressed_slc_t087_185684_iw2_20180101_20180210.h5']
            elif file_type == 'uncompressed':
                return ['t087_185683_iw2_20180222_VV.h5', 't087_185683_iw2_20180306_VV.h5',
                        't087_185684_iw2_20180222_VV.h5', 't087_185684_iw2_20180306_VV.h5']
            else:
                return []

        def add_text_to_file(file_list: list) -> list:
            """Helper function to add a bit of text to each empty file in a list"""
            for f in file_list:
                with open(f, 'w') as wf:
                    wf.write('Hello\n')
            return file_list

        sas_config = {
            'input_file_group': {
                'cslc_file_list': [

                ]
            },
            'dynamic_ancillary_file_group': {
            },
            'static_ancillary_file_group': {
            }
        }
        # Test uncompressed files only as input
        cslc_file_list = add_text_to_file(get_sample_input_files('uncompressed'))
        sas_config['input_file_group']['cslc_file_list'] = cslc_file_list
        runconfig = MockRunConfig(sas_config)
        logger = PgeLogger()
        validate_disp_inputs(runconfig, logger, "DISP-S1")

        # Test uncompressed and compressed files as input
        cslc_file_list = add_text_to_file(get_sample_input_files('compressed')
                                          + get_sample_input_files('uncompressed'))
        sas_config['input_file_group']['cslc_file_list'] = cslc_file_list
        runconfig = MockRunConfig(sas_config)
        logger = PgeLogger()
        validate_disp_inputs(runconfig, logger, "DISP-S1")

        # Test uncompressed burst_id set does not match compressed burst_id set (burst_id, '185685' below)
        cslc_file_list = add_text_to_file(get_sample_input_files('compressed') +
                                          ['t087_185683_iw2_20180222_VV.h5',
                                           't087_185683_iw2_20180306_VV.h5',
                                           't087_185684_iw2_20180222_VV.h5',
                                           't087_185685_iw2_20180306_VV.h5'])
        sas_config['input_file_group']['cslc_file_list'] = cslc_file_list
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

        self.assertIn("Set of input CSLC 'compressed' burst IDs do not match the set of 'uncompressed' burst IDs: ",
                      log)

        # Test an improperly formatted burst id ('_t087_185684_iw_' below
        cslc_file_list = add_text_to_file(['compressed_slc_t087_185683_iw2_220180101_20180210.h5',
                                           'compressed_slc_t087_185684_iw_220180101_20180210.h5']
                                          + get_sample_input_files('uncompressed'))
        sas_config['input_file_group']['cslc_file_list'] = cslc_file_list
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

        self.assertIn('Input file present without properly formatted burst_id: ', log)

        # Test an ancillary file group (nominal)
        cslc_file_list = add_text_to_file(get_sample_input_files('compressed')
                                          + get_sample_input_files('uncompressed'))
        sas_config['input_file_group']['cslc_file_list'] = cslc_file_list
        sas_config['dynamic_ancillary_file_group'] = {}

        # Acceptable burst ids
        amplitude_dispersion_files = add_text_to_file(['t087_185683_iw2_amp_dispersion.tif',
                                                       't087_185684_iw2_amp_dispersion.tif'])
        sas_config['dynamic_ancillary_file_group']['amplitude_dispersion_files'] = amplitude_dispersion_files
        runconfig = MockRunConfig(sas_config)
        logger = PgeLogger()
        validate_disp_inputs(runconfig, logger, "DISP-S1")

    @patch.object(opera.pge.disp_s1.disp_s1_pge.subprocess, "run", mock_grib_to_netcdf)
    def test_disp_s1_pge_validate_product_output(self):
        """Test off-nominal output conditions"""
        runconfig_path = join(self.data_dir, 'test_disp_s1_config.yaml')
        test_runconfig_path = join(self.data_dir, 'test_off_nominal_output.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)

        try:
            # No .nc files
            runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']['ProgramOptions'] = \
                ['-p disp_s1_pge_test/output_dir/compressed_slcs; echo ']

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = DispS1Executor(pge_name="DispS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("The SAS did not create any output file(s) with the expected '.nc' extension", log_contents)
            shutil.rmtree(pge.runconfig.output_product_path)

            # Too many .nc files
            runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']['ProgramOptions'] = \
                ['-p disp_s1_pge_test/output_dir/compressed_slcs;',
                 'dd if=/dev/urandom of=disp_s1_pge_test/output_dir/20180101_20180330.nc bs=1M count=1;',
                 'dd if=/dev/urandom of=disp_s1_pge_test/output_dir/20180101_20180331.nc bs=1M count=1; echo ']

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = DispS1Executor(pge_name="DispS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("The SAS created too many files with the expected '.nc' extension:", log_contents)
            shutil.rmtree(pge.runconfig.output_product_path)

            # Empty product file
            runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']['ProgramOptions'] = \
                ['-p disp_s1_pge_test/output_dir/compressed_slcs;',
                 'touch disp_s1_pge_test/output_dir/20180101_20180330.nc; echo ']

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = DispS1Executor(pge_name="DispS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("SAS output file 20180101_20180330.nc exists, but is empty", log_contents)
            shutil.rmtree(pge.runconfig.output_product_path)

            # PNG file is missing
            runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']['ProgramOptions'] = \
                ['-p disp_s1_pge_test/output_dir/compressed_slcs;',
                 'dd if=/dev/urandom of=disp_s1_pge_test/output_dir/20180101_20180330.nc bs=1M count=1;',
                 '/bin/echo DISP-S1 invoked with RunConfig']

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = DispS1Executor(pge_name="DispS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("SAS output file 20180101_20180330.short_wavelength_displacement.png does not exist", log_contents)
            shutil.rmtree(pge.runconfig.output_product_path)

            # PNG is zero sized
            runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']['ProgramOptions'] = \
                ['-p disp_s1_pge_test/output_dir/compressed_slcs;',
                 'dd if=/dev/urandom of=disp_s1_pge_test/output_dir/20180101_20180330.nc bs=1M count=1;',
                 'touch disp_s1_pge_test/output_dir/20180101_20180330.short_wavelength_displacement.png;',
                 '/bin/echo DISP-S1 invoked with RunConfig']

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = DispS1Executor(pge_name="DispS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("SAS output file 20180101_20180330.short_wavelength_displacement.png exists, but is empty",
                          log_contents)
            shutil.rmtree(pge.runconfig.output_product_path)

            # compressed_slc directory does not exist
            runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']['ProgramOptions'] = \
                ['-p disp_s1_pge_test/output_dir/not_compressed_slcs;',
                 'dd if=/dev/urandom of=disp_s1_pge_test/output_dir/20180101_20180330.nc bs=1M count=1;',
                 'dd if=/dev/urandom of=disp_s1_pge_test/output_dir/20180101_20180330.displacement.png bs=1M count=1;',
                 'dd if=/dev/urandom of=disp_s1_pge_test/output_dir/20180101_20180330.short_wavelength_displacement.png'
                 ' bs=1M count=1;', 'bs=1M count=1;', '/bin/echo DISP-S1 invoked with RunConfig']

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = DispS1Executor(pge_name="DispS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("SAS output directory 'compressed_slcs' does not exist", log_contents)
            shutil.rmtree(pge.runconfig.output_product_path)

            # compressed_slc directory exists but is empty
            runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']['ProgramOptions'] = \
                ['-p disp_s1_pge_test/output_dir/compressed_slcs;',
                 'dd if=/dev/urandom of=disp_s1_pge_test/output_dir/20180101_20180330.nc bs=1M count=1;',
                 'dd if=/dev/urandom of=disp_s1_pge_test/output_dir/20180101_20180330.displacement.png bs=1M count=1;',
                 'dd if=/dev/urandom of=disp_s1_pge_test/output_dir/20180101_20180330.'
                 'short_wavelength_displacement.png bs=1M count=1;',
                 'bs=1M count=1;', '/bin/echo DISP-S1 invoked with RunConfig']

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = DispS1Executor(pge_name="DispS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("SAS output directory 'compressed_slcs' exists, but is empty", log_contents)
            shutil.rmtree(pge.runconfig.output_product_path)

            # File in compressed_slc directory is zero sized
            runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']['ProgramOptions'] = \
                ['-p disp_s1_pge_test/output_dir/compressed_slcs;',
                 'dd if=/dev/urandom of=disp_s1_pge_test/output_dir/20180101_20180330.nc bs=1M count=1;',
                 'dd if=/dev/urandom of=disp_s1_pge_test/output_dir/20180101_20180330.displacement.png bs=1M count=1;',
                 'dd if=/dev/urandom of=disp_s1_pge_test/output_dir/20180101_20180330.short_wavelength_displacement.'
                 'png bs=1M count=1;',
                 'touch disp_s1_pge_test/output_dir/compressed_slcs/'
                 'compressed_slc_t087_185684_iw2_20180222_20180330.h5;',
                 # noqa E501
                 '/bin/echo DISP-S1 invoked with RunConfig']

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = DispS1Executor(pge_name="DispS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(
                "Compressed CSLC file 'compressed_slc_t087_185684_iw2_20180222_20180330.h5' exists, but is empty",
                log_contents)
            shutil.rmtree(pge.runconfig.output_product_path)

        finally:
            if exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

    # DISP-S1 will no longer use GRIB/NetCDF files directly, so this test is permanently disabled
    @pytest.mark.skip
    @patch.object(opera.pge.disp_s1.disp_s1_pge.subprocess, "run", mock_grib_to_netcdf)
    def test_scratch_sas_runconfig_for_grib_to_netcdf_files(self):
        """
        Test that the grib_to_netcdf files are in 'disp_s1_pge_test/scratch_dir'.

        Verify the file names of the .grb files found in
        ['SAS']['dynamic_ancillary_file_group']['troposphere_files']
        are the same as the converted files that are now .nc files and are
        residing in scratch_dir.
        """
        starting_grb_file_names = []
        ending_grb_file_names = []
        runconfig_path = join(self.data_dir, 'test_disp_s1_config.yaml')

        pge = DispS1Executor(pge_name="DispS1PgeTest", runconfig_path=runconfig_path)

        # Pull out the starting value of the troposphere_files
        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)
        starting_tropo_paths = \
            runconfig_dict['RunConfig']['Groups']['SAS']['dynamic_ancillary_file_group']['troposphere_files']

        # Strip the path and extension (.grb) in order to compare just the file names after
        # conversion and placement of the converted file into /scratch_dir/<fname>.nc
        for starting_path in starting_tropo_paths:
            if starting_path[-4:] == '.grb':
                starting_grb_file_names.append(starting_path.split('/')[-1][:-4])

        # Run only the preprocessor and the sas_executable, so the temporary directories are created and still alive.
        pge.run_preprocessor()
        pge.run_sas_executable()
        temp_sas_runconfig = 'disp_s1_pge_test/scratch_dir/' + pge.runconfig.filename.split('/')[-1][:-5] + '_sas.yaml'

        # open the yaml file
        with open(temp_sas_runconfig, 'r') as file:
            data = yaml.safe_load(file)

        ending_tropo_paths = data['dynamic_ancillary_file_group']['troposphere_files']

        # Verify the converted .grb files are in /scratch_dir
        # Strip the path and extension (changed to .nc in this case) to allow comparison of file name only.
        for ending_path in ending_tropo_paths:
            ending_file_name = os.path.splitext(os.path.basename(ending_path))[0]
            if ending_file_name in starting_grb_file_names:
                self.assertIn('scratch_dir', ending_path)
                self.assertTrue(exists(ending_path))  # verify the files exist on disk
                ending_grb_file_names.append(ending_file_name)

        self.assertEqual(starting_grb_file_names, ending_grb_file_names)


class MockRunConfig:
    """Mock runconfig for testing"""

    def __init__(self, sas_config):
        self._sas_config_dict = sas_config

    @property
    def sas_config(self):
        """Return a simple test runconfig dictionary"""
        return self._sas_config_dict


if __name__ == "__main__":
    unittest.main()
