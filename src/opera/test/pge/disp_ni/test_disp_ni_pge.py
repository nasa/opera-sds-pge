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
from os.path import abspath, join

from pkg_resources import resource_filename

from opera.pge import RunConfig
from opera.pge.disp_ni.disp_ni_pge import DispNIExecutor
from opera.util import PgeLogger


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

    def test_disp_s1_pge_execution(self):
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

        # Check that the log file was created and moved into the output directory
        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        # Lastly, check that the dummy output products were created and renamed
        self.assertTrue(os.path.exists(join(pge.runconfig.output_product_path, '20060630_20060930.nc')))
        self.assertTrue(os.path.exists(join(pge.runconfig.output_product_path,
                                            '20060630_20060930.short_wavelength_displacement.png')))
        self.assertTrue(os.path.exists(join(pge.runconfig.output_product_path, 'compressed_slcs',
                                            'compressed_20060630_20060630_20071118.h5')))

        # Open and read the log
        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn(f"DISP-NI invoked with RunConfig {expected_sas_config_file}", log_contents)


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
