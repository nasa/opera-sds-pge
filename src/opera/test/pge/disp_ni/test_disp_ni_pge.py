#!/usr/bin/env python3

"""
===================
test_disp_ni_pge.py
===================
Unit tests for the pge/disp_ni/disp_ni_pge.py module.
"""

import os
import shutil
import tempfile
import unittest
from io import StringIO
from os.path import abspath, join, exists

from pkg_resources import resource_filename

import yaml

from opera.pge import RunConfig
from opera.pge.disp_ni.disp_ni_pge import DispNIExecutor
from opera.util import PgeLogger
from opera.util.input_validation import validate_disp_inputs
from opera.util.h5_utils import create_test_disp_ni_metadata_product
from opera.util.render_jinja2 import UNDEFINED_ERROR


class DispNIPgeTestCase(unittest.TestCase):
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
            prefix="test_disp_ni_pge_", suffix="_temp", dir=os.curdir
        )

        # Create the input dir expected by the test RunConfig and add a
        # dummy input file
        input_dir = join(self.working_dir.name, "disp_ni_pge_test/input_dir")
        os.makedirs(input_dir, exist_ok=True)

        # Copy the algorithm_parameters config file into the test input directory.
        shutil.copy(join(self.data_dir, 'test_disp_ni_algorithm_parameters.yaml'), input_dir)

        # Create non-empty dummy input files expected by test runconfig
        dummy_input_files = ['NISAR_L2_GSLC_NI_F150_20070703T062138Z_20240528T200959Z_NI_HH_v0.1.h5',
                             'NISAR_L2_GSLC_NI_F150_20070818T062132Z_20240528T200952Z_NI_HH_v0.1.h5',
                             'dem.tif', 'water_mask.tif',
                             'NISAR_L2_PR_GUNW_001_005_A_219_220_4020_SH_20060630T000000_20060630T000000_20060815T000000_20060815T000000_P01101_M_F_J_001.h5',
                             'NISAR_L2_PR_GUNW_001_005_A_219_220_4020_SH_20060815T000000_20060815T000000_20060930T000000_20060930T000000_P01101_M_F_J_001.h5',
                             'Frame_to_bounds_DISP-NI_v0.1.json',
                             'opera-disp-nisar-reference-dates-dummy.json',]
        for dummy_input_file in dummy_input_files:
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
        self.assertEqual(runconfig['algorithm_parameters_overrides_json'], "opera-disp-s1-algorithm-parameters-overrides-2025-01-09.json")
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
        self.assertEqual(runconfig['spatial_wavelength_cutoff'], 40000.0)
        self.assertListEqual(runconfig['browse_image_vmin_vmax'], [-0.1, 0.1])
        self.assertEqual(runconfig['recommended_temporal_coherence_threshold'], 0.5)
        self.assertEqual(runconfig['recommended_similarity_threshold'], 0.30)
        self.assertEqual(runconfig['num_parallel_products'], 3)
        # self.assertFalse(runconfig['recommended_use_conncomp'])

    def test_disp_ni_pge_execution(self):
        """
        Test execution of the DispNIExecutor class and its associated mixins
        using a test RunConfig that creates dummy expected output files and logs
        a message to be captured by PgeLogger.
        """
        runconfig_path = join(self.data_dir, 'test_disp_ni_config.yaml')

        pge = DispNIExecutor(pge_name="DispNIPgeTest", runconfig_path=runconfig_path)

        # Check that basic attributes were initialized
        self.assertEqual(pge.name, "DISP-NI")
        self.assertEqual(pge.pge_name, "DispNIPgeTest")
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
        expected_sas_config_file = join(pge.runconfig.scratch_path, 'test_disp_ni_config_sas.yaml')
        self.assertTrue(os.path.exists(expected_sas_config_file))

        # Check that the catalog metadata file was created in the output directory
        expected_catalog_metadata_file = join(
            pge.runconfig.output_product_path, pge._catalog_metadata_filename())
        self.assertTrue(os.path.exists(expected_catalog_metadata_file))

        expected_inter_filename = abspath("disp_ni_pge_test/output_dir/20060630_20060930.nc")
        expected_browse_filename = abspath("disp_ni_pge_test/output_dir/20060630_20060930.displacement.png")

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

        for compressed_gslc in ['compressed_20060630_20060630_20071118.h5',]:
            expected_compressed_gslc_product = join(
                pge.runconfig.output_product_path,
                pge._compressed_gslc_filename(compressed_gslc)
            )
            self.assertTrue(os.path.exists(expected_compressed_gslc_product))

        # Open and read the log
        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn(f"DISP-NI invoked with RunConfig {expected_sas_config_file}", log_contents)

    def test_disp_ni_pge_validate_inputs(self):
        """
        Test that the validate_disp_inputs function is able to detect non-existent files,
        zero-size files, and invalid extensions in filenames. Also check that
        valid files pass validation.
        """
        # Test non-existent file detection

        test_filename = 'non_existent_input_file'
        sas_config = {
            'input_file_group': {
                'gslc_file_list': [
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
            validate_disp_inputs(runconfig, logger, "DISP-NI")

        # Check to see that the RuntimeError is as expected
        logger.close_log_stream()
        log_file = logger.get_file_name()
        self.assertTrue(exists(log_file))
        with open(log_file, 'r', encoding='utf-8') as lfile:
            log = lfile.read()
        self.assertIn(f'Could not locate specified input {test_filename}.', log)

        # Test invalid file extension

        logger = PgeLogger()
        test_filename = "NISAR_L2_GSLC_NI_F150_20070703T062138Z_20240528T200959Z_NI_HH_v0.1.inv"
        with open(test_filename, 'w') as ief:
            ief.write("\n")
        sas_config['input_file_group']['gslc_file_list'] = [test_filename]
        runconfig = MockRunConfig(sas_config)
        with self.assertRaises(RuntimeError):
            validate_disp_inputs(runconfig, logger, "DISP-NI")

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
        test_filename = "NISAR_L2_GSLC_NI_F150_20070703T062138Z_20240528T200959Z_NI_HH_v0.1_zero_size_file.h5"
        open(test_filename, 'w').close()
        self.assertTrue(exists(test_filename))
        sas_config['input_file_group']['gslc_file_list'] = [test_filename]
        runconfig = MockRunConfig(sas_config)
        with self.assertRaises(RuntimeError):
            validate_disp_inputs(runconfig, logger, "DISP-NI")

        # Check to see that the RuntimeError is as expected
        logger.close_log_stream()
        log_file = logger.get_file_name()
        self.assertTrue(exists(log_file))
        with open(log_file, 'r', encoding='utf-8') as lfile:
            log = lfile.read()
        self.assertIn(f'Input file {test_filename} size is 0. Size must be greater than 0.', log)
        os.remove(test_filename)

        # Test all input files with valid files
        test_filenames = [
            "NISAR_L2_GSLC_NI_F150_20070703T062138Z_20240528T200959Z_NI_HH_v0.1.h5",
            "NISAR_L2_GSLC_NI_F150_20070818T062132Z_20240528T200952Z_NI_HH_v0.1.h5"
        ]
        test_gunw_filenames = [
            "NISAR_L2_PR_GUNW_001_005_A_219_220_4020_SH_20060630T000000_20060630T000000_20060815T000000_20060815T000000_P01101_M_F_J_001.h5",
            "NISAR_L2_PR_GUNW_001_005_A_219_220_4020_SH_20060815T000000_20060815T000000_20060930T000000_20060930T000000_P01101_M_F_J_001.h5"
        ]
        for test_f in test_filenames + test_gunw_filenames:
            with open(test_f, 'w') as ief:
                ief.write("\n")
            self.assertTrue(exists(test_f))

        logger = PgeLogger()
        sas_config['input_file_group']['gslc_file_list'] = test_filenames
        runconfig = MockRunConfig(sas_config)
        validate_disp_inputs(runconfig, logger, "DISP-NI")

        logger = PgeLogger()
        sas_config['dynamic_ancillary_file_group']['gunw_files'] = test_gunw_filenames
        runconfig = MockRunConfig(sas_config)
        validate_disp_inputs(runconfig, logger, "DISP-NI")

        logger = PgeLogger()
        sas_config['dynamic_ancillary_file_group']['gunw_files'] = test_gunw_filenames[:1]
        runconfig = MockRunConfig(sas_config)
        with self.assertRaises(RuntimeError):
            validate_disp_inputs(runconfig, logger, "DISP-NI")

        log_file = logger.get_file_name()
        self.assertTrue(exists(log_file))
        with open(log_file, 'r', encoding='utf-8') as lfile:
            log = lfile.read()
        self.assertIn('Differing numbers of GSLC files and GUNW files', log)

        for test_f in test_filenames + test_gunw_filenames:
            os.remove(test_f)

    def test_disp_ni_pge_validate_product_output(self):
        """Test off-nominal output conditions"""
        runconfig_path = join(self.data_dir, 'test_disp_ni_config.yaml')
        test_runconfig_path = join(self.data_dir, 'test_off_nominal_output.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)

        try:
            # No .nc files
            runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']['ProgramOptions'] = \
                ['-p disp_ni_pge_test/output_dir/compressed_slcs; echo ']

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = DispNIExecutor(pge_name="DispNIPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("The SAS did not create any output file(s) with the expected '.nc' extension", log_contents)
            shutil.rmtree(pge.runconfig.output_product_path)

        finally:
            if exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

            # Too many .nc files
            runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']['ProgramOptions'] = \
                ['-p disp_ni_pge_test/output_dir/compressed_slcs;',
                 'dd if=/dev/urandom of=disp_ni_pge_test/output_dir/20180101_20180330.nc bs=1M count=1;',
                 'dd if=/dev/urandom of=disp_ni_pge_test/output_dir/20180101_20180331.nc bs=1M count=1; echo ']

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = DispNIExecutor(pge_name="DispNIPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("The SAS created too many files with the expected '.nc' extension:", log_contents)
            shutil.rmtree(pge.runconfig.output_product_path)

            # Empty product file
            runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']['ProgramOptions'] = \
                ['-p disp_ni_pge_test/output_dir/compressed_slcs;',
                 'touch disp_ni_pge_test/output_dir/20180101_20180330.nc; echo ']

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = DispNIExecutor(pge_name="DispNIPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("SAS output file 20180101_20180330.nc exists, but is empty", log_contents)
            shutil.rmtree(pge.runconfig.output_product_path)

            # PNG file is missing
            runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']['ProgramOptions'] = \
                ['-p disp_ni_pge_test/output_dir/compressed_slcs;',
                 'dd if=/dev/urandom of=disp_ni_pge_test/output_dir/20180101_20180330.nc bs=1M count=1;',
                 '/bin/echo DISP-S1 invoked with RunConfig']

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = DispNIExecutor(pge_name="DispNIPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("SAS output file 20180101_20180330.short_wavelength_displacement.png does not exist", log_contents)
            shutil.rmtree(pge.runconfig.output_product_path)

            # PNG is zero sized
            runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']['ProgramOptions'] = \
                ['-p disp_ni_pge_test/output_dir/compressed_slcs;',
                 'dd if=/dev/urandom of=disp_ni_pge_test/output_dir/20180101_20180330.nc bs=1M count=1;',
                 'touch disp_ni_pge_test/output_dir/20180101_20180330.short_wavelength_displacement.png;',
                 '/bin/echo DISP-S1 invoked with RunConfig']

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = DispNIExecutor(pge_name="DispNIPgeTest", runconfig_path=test_runconfig_path)

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
                ['-p disp_ni_pge_test/output_dir/not_compressed_slcs;',
                 'dd if=/dev/urandom of=disp_ni_pge_test/output_dir/20180101_20180330.nc bs=1M count=1;',
                 'dd if=/dev/urandom of=disp_ni_pge_test/output_dir/20180101_20180330.displacement.png bs=1M count=1;',
                 'dd if=/dev/urandom of=disp_ni_pge_test/output_dir/20180101_20180330.short_wavelength_displacement.png'
                 ' bs=1M count=1;', 'bs=1M count=1;', '/bin/echo DISP-S1 invoked with RunConfig']

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = DispNIExecutor(pge_name="DispNIPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("SAS output directory 'compressed_slcs' does not exist", log_contents)
            shutil.rmtree(pge.runconfig.output_product_path)

            # compressed_slc directory exists but is empty
            runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']['ProgramOptions'] = \
                ['-p disp_ni_pge_test/output_dir/compressed_slcs;',
                 'dd if=/dev/urandom of=disp_ni_pge_test/output_dir/20180101_20180330.nc bs=1M count=1;',
                 'dd if=/dev/urandom of=disp_ni_pge_test/output_dir/20180101_20180330.displacement.png bs=1M count=1;',
                 'dd if=/dev/urandom of=disp_ni_pge_test/output_dir/20180101_20180330.'
                 'short_wavelength_displacement.png bs=1M count=1;',
                 'bs=1M count=1;', '/bin/echo DISP-S1 invoked with RunConfig']

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = DispNIExecutor(pge_name="DispNIPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("SAS output directory 'compressed_slcs' exists, but is empty", log_contents)
            shutil.rmtree(pge.runconfig.output_product_path)

            # File in compressed_slc directory is zero sized
            runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']['ProgramOptions'] = \
                ['-p disp_ni_pge_test/output_dir/compressed_slcs;',
                 'dd if=/dev/urandom of=disp_ni_pge_test/output_dir/20180101_20180330.nc bs=1M count=1;',
                 'dd if=/dev/urandom of=disp_ni_pge_test/output_dir/20180101_20180330.displacement.png bs=1M count=1;',
                 'dd if=/dev/urandom of=disp_ni_pge_test/output_dir/20180101_20180330.short_wavelength_displacement.'
                 'png bs=1M count=1;',
                 'touch disp_ni_pge_test/output_dir/compressed_slcs/'
                 'compressed_slc_t087_185684_iw2_20180222_20180330.h5;',
                 # noqa E501
                 '/bin/echo DISP-S1 invoked with RunConfig']

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = DispNIExecutor(pge_name="DispNIPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(
                "Compressed CSLC file 'compressed_slc_t087_185684_iw2_20180222_20180330.h5' exists, but is empty",
                log_contents)
            shutil.rmtree(pge.runconfig.output_product_path)

    def test_iso_metadata_creation(self):
        """
        Test that the ISO metadata template is fully filled out when realistic
        DISP-NI product metadata is available.
        """
        runconfig_path = join(self.data_dir, 'test_disp_ni_config.yaml')

        pge = DispNIExecutor(pge_name="DispNIPgeTest", runconfig_path=runconfig_path)

        # Run only the pre-processor steps to ingest the runconfig and set
        # up directories
        pge.run_preprocessor()

        # Create a sample metadata file within the output directory of the PGE
        output_dir = join(os.curdir, "disp_ni_pge_test/output_dir")

        disp_metadata_path = abspath(join(output_dir, '20170217_20170430.nc'))

        create_test_disp_ni_metadata_product(disp_metadata_path)

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


class MockRunConfig:
    """Mock runconfig for testing"""

    pge_name = "DISP_NI_PGE"

    def __init__(self, sas_config):
        self._sas_config_dict = sas_config

    @property
    def sas_config(self):
        """Return a simple test runconfig dictionary"""
        return self._sas_config_dict


if __name__ == "__main__":
    unittest.main()
