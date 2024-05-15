#!/usr/bin/env python3

"""
===================
test_dswx_ni_pge.py
===================
Unit tests for the pge/dswx_ni/dswx_ni_pge.py module.
"""

import glob
import os
import shutil
import tempfile
import unittest
from io import StringIO
from os.path import abspath, join

from pkg_resources import resource_filename

import yaml

from opera.pge import RunConfig
from opera.pge.dswx_ni.dswx_ni_pge import DSWxNIExecutor
from opera.util import PgeLogger


class DswxNIPgeTestCase(unittest.TestCase):
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
            prefix="test_dswx_ni_pge_", suffix="_temp", dir=os.curdir
        )

        # Create the input dir expected by the test RunConfig and add a
        # dummy input file
        input_dir = join(self.working_dir.name, "dswx_ni_pge_test/input_dir")
        os.makedirs(input_dir, exist_ok=True)

        # Copy the algorithm_parameters config file into the test input directory.
        shutil.copy(join(self.data_dir, 'test_dswx_ni_algorithm_parameters.yaml'), input_dir)

        # Create the input dir expected by the test RunConfig and add a
        # dummy input file
        self.input_file = tempfile.NamedTemporaryFile(
            dir=input_dir, prefix="test_input_", suffix=".h5"
        )

        # Create dummy versions of the expected ancillary inputs
        for ancillary_file in ('dem.tif', 'worldcover.tif',
                               'reference_water.tif', 'shoreline.shp',
                               'shoreline.dbf', 'shoreline.prj',
                               'shoreline.shx', 'hand.tif',
                               'MGRS_tile.sqlite', 'MGRS_tile_collection.sqlite'):
            os.system(
                f"touch {join(input_dir, ancillary_file)}"
            )

        # Create the output directories expected by the test Runconfig file
        self.test_output_dir = abspath(join(self.working_dir.name, "dswx_ni_pge_test/output_dir"))
        os.makedirs(self.test_output_dir, exist_ok=True)
        os.chdir(self.working_dir.name)

    def tearDown(self) -> None:
        """Return to starting directory"""
        os.chdir(self.test_dir)
        self.input_file.close()
        self.working_dir.cleanup()

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
        # band_data = ('OPERA_L3_DSWx-NI_band_1_B01_WTR.tif', 'OPERA_L3_DSWx-NI_band_1_B02_BWTR.tif',
        #              'OPERA_L3_DSWx-NI_band_1_B03_CONF.tif', 'OPERA_L3_DSWx-NI_band_2_B01_WTR.tif',
        #              'OPERA_L3_DSWx-NI_band_2_B02_BWTR.tif', 'OPERA_L3_DSWx-NI_band_2_B03_CONF.tif')

        if clear:
            path = self.test_output_dir
            for file_path in glob.glob(f"{path}/*.tif"):
                os.unlink(file_path)

        # Add files to the output directory
        for band_output_file in band_data:
            if not empty_file:
                os.system(f"echo 'Test data string' >> {join(self.test_output_dir, band_output_file)}")
            else:
                os.system(f"touch {join(self.test_output_dir, band_output_file)}")

    def test_dswx_ni_pge_execution(self):
        """
        Test execution of the DswxNIExecutor class and its associated mixins
        using a test RunConfig that creates dummy expected output files and logs
        a message to be captured by PgeLogger.
        """
        runconfig_path = join(self.data_dir, 'test_dswx_ni_config.yaml')

        pge = DSWxNIExecutor(pge_name="DswxNIPgeTest", runconfig_path=runconfig_path)

        # Check that basic attributes were initialized
        self.assertEqual(pge.name, "DSWx-NI")
        self.assertEqual(pge.pge_name, "DswxNIPgeTest")
        self.assertEqual(pge.runconfig_path, runconfig_path)

        # Check that other objects have not been instantiated yet
        self.assertIsNone(pge.runconfig)
        self.assertIsNone(pge.logger)

        # Kickoff execution of DSWx-NI PGE
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
        expected_sas_config_file = join(pge.runconfig.scratch_path, 'test_dswx_ni_config_sas.yaml')
        self.assertTrue(os.path.exists(expected_sas_config_file))

        # Check that the log file was created and moved into the output directory
        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        # Lastly, check that the dummy output products were created
        slc_files = glob.glob(join(pge.runconfig.output_product_path, "*.tif"))
        self.assertEqual(len(slc_files), 5)

        output_browse_files = glob.glob(join(pge.runconfig.output_product_path, "*.png"))
        self.assertEqual(len(output_browse_files), 1)

        # Open and read the log
        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn(f"DSWx-NI invoked with RunConfig {expected_sas_config_file}", log_contents)

    def test_dswx_ni_pge_output_validation(self):
        """Test the output validation checks made by DSWxNIPostProcessorMixin."""
        runconfig_path = join(self.data_dir, 'test_dswx_ni_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_dswx_ni_runconfig.yaml')

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
            pge = DSWxNIExecutor(pge_name="DSWxNIPgeTest", runconfig_path=test_runconfig_path)

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
            band_data = ('OPERA_L3_DSWx-NI_b1_B01_WTR.tif',)
            self.generate_band_data_output(band_data, empty_file=True, clear=False)

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = DSWxNIExecutor(pge_name="DSWxNIPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_output_file = 'dswx_ni_pge_test/output_dir/OPERA_L3_DSWx-NI_b1_B01_WTR.tif'
            self.assertTrue(os.path.exists(expected_output_file))

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f"SAS output file {abspath(expected_output_file)} was "
                          f"created, but is empty", log_contents)

            # Test a missing band type.  Post-processor should detect this and flag an error
            band_data = ('OPERA_L3_DSWx-NI_b1_B01_WTR.tif', 'OPERA_L3_DSWx-NI_b1_B02_BWTR.tif',
                         'OPERA_L3_DSWx-NI_b1_B03_CONF.tif')
            self.generate_band_data_output(band_data, clear=True)

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = DSWxNIExecutor(pge_name="DSWxNIPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("Invalid SAS output file, wrong number of bands,",
                          log_contents)

            # Test for missing or extra band files
            # Test a misnamed band file.  Post-processor should detect this and flag an error
            band_data = ('OPERA_L3_DSWx-NI_b1_B01_WTR.tif', 'OPERA_L3_DSWx-NI_b1_B02_BWTR.tif',
                         'OPERA_L3_DSWx-NI_b1_B03_CONF.tif', 'OPERA_L3_DSWx-NI_b1_B04_DIAG.tif',
                         'OPERA_L3_DSWx-NI_b1_BROWSE.tif', 'OPERA_L3_DSWx-NI_b2_B01_WTR.tif',
                         'OPERA_L3_DSWx-NI_b2_B02_BWTR.tif', 'OPERA_L3_DSWx-NI_b2_B04_DIAG.tif')
            self.generate_band_data_output(band_data, clear=True)

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = DSWxNIExecutor(pge_name="DSWxNIPgeTest", runconfig_path=test_runconfig_path)

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


if __name__ == "__main__":
    unittest.main()
