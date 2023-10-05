#!/usr/bin/env python3

"""
==================
test_rtc_s1_pge.py
==================

Unit tests for the pge/rtc_s1/rtc_s1_pge.py module.
"""

import glob
import os
import re
import stat
import tempfile
import unittest
from io import StringIO
from os.path import abspath, join
from unittest.mock import patch

from pkg_resources import resource_filename

import yaml

import opera.util.img_utils
from opera.pge import RunConfig
from opera.pge.rtc_s1.rtc_s1_pge import RtcS1Executor
from opera.util import PgeLogger
from opera.util.img_utils import mock_gdal_edit
from opera.util.img_utils import mock_save_as_cog
from opera.util.metadata_utils import create_test_rtc_metadata_product
from opera.util.metadata_utils import get_rtc_s1_product_metadata
from opera.util.metadata_utils import get_sensor_from_spacecraft_name


class RtcS1PgeTestCase(unittest.TestCase):
    """Base test class using unittest"""

    starting_dir = None
    working_dir = None
    test_dir = None

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
            prefix="test_rtc_s1_pge_", suffix="_temp", dir=os.curdir
        )

        # Create the input dir expected by the test RunConfig and add
        # dummy input files with the names expected by the RunConfig
        input_dir = join(self.working_dir.name, "rtc_s1_test/input_dir")
        os.makedirs(input_dir, exist_ok=True)

        # Use empty files for testing the existence of required input files

        os.system(f"touch {join(input_dir, 'SAFE.zip')}")

        os.system(f"touch {join(input_dir, 'ORBIT.EOF')}")

        os.system(f"touch {join(input_dir, 'dem.tif')}")

        # 'db.sqlite3' simulates the burst_id database file
        os.system(f"touch {join(input_dir, 'db.sqlite3')}")

        # When the [QAExecutable] is enabled, a python script (specified in [QAExecutable][ProgramPath]) is executed.
        # The empty files below simulate a script with proper permissions, and a script with improper permissions.
        os.system(f"touch {join(input_dir, 'test_qa_rwx.py')}")  # rwx - read, write, execute

        os.chmod(f"{join(input_dir, 'test_qa_rwx.py')}", stat.S_IRWXU)  # Set to read, write, execute by owner

        os.system(f"touch {join(input_dir, 'test_qa_ro.py')}")  # r0 - read only

        os.chmod(f"{join(input_dir, 'test_qa_ro.py')}", stat.S_IREAD)  # Set to read by owner

        os.chdir(self.working_dir.name)

    def tearDown(self) -> None:
        """Return to test directory"""
        os.chdir(self.test_dir)
        self.working_dir.cleanup()

    @patch.object(opera.util.img_utils, "gdal_edit", mock_gdal_edit)
    @patch.object(opera.util.img_utils, "save_as_cog", mock_save_as_cog)
    def test_rtc_s1_pge_execution(self):
        """
        Test execution of the RtcS1Executor class and its associated mixins
        using a test RunConfig that creates dummy expected output files and
        logs a message to be captured by PgeLogger.

        """
        runconfig_path = join(self.data_dir, 'test_rtc_s1_config.yaml')

        pge = RtcS1Executor(pge_name="RtcS1PgeTest", runconfig_path=runconfig_path)

        # Check that basic attributes were initialized
        self.assertEqual(pge.name, "RTC")
        self.assertEqual(pge.pge_name, "RtcS1PgeTest")
        self.assertEqual(pge.runconfig_path, runconfig_path)

        # Check that other objects have not been instantiated yet
        self.assertIsNone(pge.runconfig)
        self.assertIsNone(pge.logger)

        # Kickoff execution of the RTC-S1 PGE
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
        expected_sas_config_file = join(pge.runconfig.scratch_path, 'test_rtc_s1_config_sas.yaml')
        self.assertTrue(os.path.exists(expected_sas_config_file))

        # Check that the catalog metadata file was created in the output directory
        expected_catalog_metadata_file = join(
            pge.runconfig.output_product_path, pge._catalog_metadata_filename()
        )
        self.assertTrue(os.path.exists(expected_catalog_metadata_file))

        # Check that the log file was created and moved into the output directory
        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        # Lastly, check that the dummy output product(s) were created and renamed
        expected_output_file = join(
            pge.runconfig.output_product_path, list(pge.renamed_files.values())[0]
        )
        self.assertTrue(os.path.exists(expected_output_file))

        # Open and read the log
        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn(f"RTC-S1 invoked with RunConfig {expected_sas_config_file}", log_contents)

    @patch.object(opera.util.img_utils, "save_as_cog", mock_save_as_cog)
    def test_static_layer_data_access_url_injection(self):
        """Test injection of static data access URL into the output HDF5 product(s)"""
        expected_url = 'https://search.asf.alaska.edu/#/?dataset=OPERA-S1&productTypes=RTC-STATIC&operaBurstID=T069-147170-IW1&end=2018-05-04'   # noqa E501

        runconfig_path = join(self.data_dir, 'test_rtc_s1_config.yaml')

        pge = RtcS1Executor(pge_name="RtcPgeTest", runconfig_path=runconfig_path)

        # Evaluate the arguments to the gdal_edit call since we cannot actually
        # update the dummy .tif files
        def _patched_gdal_edit(args):
            self.assertEqual(len(args), 4)
            self.assertEqual(args[0], 'gdal_edit.py')
            self.assertEqual(args[1], '-mo')
            self.assertTrue(args[2].startswith('STATIC_LAYERS_DATA_ACCESS='))
            self.assertTrue(args[2].endswith(expected_url))
            self.assertTrue(args[3].endswith('.tif'))
            return 0

        with patch.object(opera.util.img_utils, "gdal_edit", _patched_gdal_edit):
            pge.run()

        # Grab the metadata generated from the PGE run
        output_files = glob.glob(join(pge.runconfig.output_product_path, "*.h5"))

        self.assertEqual(len(output_files), 1)

        output_file = output_files[0]

        rtc_metadata = get_rtc_s1_product_metadata(output_file)

        self.assertIn('staticLayersDataAccess', rtc_metadata['identification'])
        self.assertEqual(rtc_metadata['identification']['staticLayersDataAccess'], expected_url)

    @patch.object(opera.util.img_utils, "gdal_edit", mock_gdal_edit)
    @patch.object(opera.util.img_utils, "save_as_cog", mock_save_as_cog)
    def test_filename_application(self):
        """Test the filename convention applied to RTC output products"""
        runconfig_path = join(self.data_dir, 'test_rtc_s1_config.yaml')

        pge = RtcS1Executor(pge_name="RtcPgeTest", runconfig_path=runconfig_path)

        pge.run()

        # Grab the metadata generated from the PGE run, as it is used to generate
        # the final filename for output products
        output_files = glob.glob(join(pge.runconfig.output_product_path, "*.h5"))

        self.assertEqual(len(output_files), 1)

        output_file = output_files[0]

        rtc_metadata = get_rtc_s1_product_metadata(output_file)
        sensor = get_sensor_from_spacecraft_name(rtc_metadata['identification']['platform'])

        file_name_regex = rf"{pge.PROJECT}_{pge.LEVEL}_{pge.NAME}-{pge.SOURCE}_" \
                          rf"\w{{4}}-\w{{6}}-\w{{3}}_" \
                          rf"\d{{8}}T\d{{6}}Z_\d{{8}}T\d{{6}}Z_" \
                          rf"{sensor}_" \
                          rf"{int(rtc_metadata['data']['xCoordinateSpacing'])}_" \
                          rf"v{pge.runconfig.product_version}.h5"

        result = re.match(file_name_regex, os.path.basename(output_file))

        self.assertIsNotNone(result)
        self.assertEqual(result.group(), os.path.basename(output_file))

        # Check that the output tif files also had the convention applied
        core_filename = os.path.splitext(os.path.basename(output_file))[0]

        output_files = glob.glob(join(pge.runconfig.output_product_path, f"{core_filename}*.tif"))

        self.assertEqual(len(output_files), 7)

        output_files = list(map(os.path.basename, output_files))

        self.assertIn(f"{core_filename}_VV.tif", output_files)
        self.assertIn(f"{core_filename}_VH.tif", output_files)
        self.assertIn(f"{core_filename}_HH.tif", output_files)
        self.assertIn(f"{core_filename}_HV.tif", output_files)
        self.assertIn(f"{core_filename}_VV+VH.tif", output_files)
        self.assertIn(f"{core_filename}_HH+HV.tif", output_files)
        self.assertIn(f"{core_filename}_mask.tif", output_files)

        # Finally, ensure file name was applied to the png browse image
        output_files = glob.glob(join(pge.runconfig.output_product_path, f"{core_filename}*.png"))

        self.assertEqual(len(output_files), 1)

        output_files = list(map(os.path.basename, output_files))

        self.assertIn(f"{core_filename}_BROWSE.png", output_files)

    @patch.object(opera.util.img_utils, "gdal_edit", mock_gdal_edit)
    @patch.object(opera.util.img_utils, "save_as_cog", mock_save_as_cog)
    def test_static_layer_filename_application(self):
        """Test the filename convention applied to RTC static layer output products"""
        runconfig_path = join(self.data_dir, 'test_rtc_s1_static_config.yaml')

        pge = RtcS1Executor(pge_name="RtcPgeTest", runconfig_path=runconfig_path)

        pge.run()

        # Check that the static layer files had conventions applied
        static_output_files = glob.glob(join(pge.runconfig.output_product_path, "*STATIC*.*"))

        self.assertEqual(len(static_output_files), 7)

        static_output_files = list(map(os.path.basename, static_output_files))

        expected_version = 'v1.0'

        core_static_filename = os.path.basename(static_output_files[0]).split(expected_version)[0]

        self.assertIn(f"{core_static_filename}{expected_version}_incidence_angle.tif", static_output_files)
        self.assertIn(f"{core_static_filename}{expected_version}_local_incidence_angle.tif", static_output_files)
        self.assertIn(f"{core_static_filename}{expected_version}_number_of_looks.tif", static_output_files)
        self.assertIn(f"{core_static_filename}{expected_version}_rtc_anf_gamma0_to_beta0.tif", static_output_files)
        self.assertIn(f"{core_static_filename}{expected_version}_rtc_anf_gamma0_to_sigma0.tif", static_output_files)
        self.assertIn(f"{core_static_filename}{expected_version}_mask.tif", static_output_files)
        self.assertIn(f"{core_static_filename}{expected_version}_BROWSE.png", static_output_files)

        # Ensure the DataValidityStartDate was used in the filenames for the
        # static layer products
        expected_data_validity_start_date = pge.runconfig.data_validity_start_date

        for static_output_file in static_output_files:
            self.assertIn(str(expected_data_validity_start_date), static_output_file)

    def test_iso_metadata_creation(self):
        """
        Test that the ISO metadata template is fully filled out when realistic
        RTC metadata is available
        """
        runconfig_path = join(self.data_dir, 'test_rtc_s1_config.yaml')

        pge = RtcS1Executor(pge_name="RtcS1PgeTest", runconfig_path=runconfig_path)

        # Run only the pre-processor steps to ingest the runconfig and set up
        # directories
        pge.run_preprocessor()

        output_product_dir = join(os.curdir, "rtc_s1_test/output_dir/t069_147170_iw1")

        os.makedirs(output_product_dir, exist_ok=True)

        # Create a dummy RTC product
        rtc_metadata_file_path = join(output_product_dir, "rtc_product_v1.0.h5")

        create_test_rtc_metadata_product(rtc_metadata_file_path)

        rtc_metadata = pge._collect_rtc_product_metadata(rtc_metadata_file_path)

        # Initialize the core filename for the catalog metadata generation step
        pge._core_filename(inter_filename=rtc_metadata_file_path)

        # Render ISO metadata using the sample metadata
        iso_metadata = pge._create_iso_metadata(rtc_metadata)

        # Rendered template should not have any missing placeholders
        self.assertNotIn('!Not found!', iso_metadata)

    def test_static_layer_iso_metadata_creation(self):
        """
        Test that the ISO metadata template is fully filled out when realistic
        RTC metadata is available and the workflow is set to RTC_S1_STATIC
        """
        runconfig_path = join(self.data_dir, 'test_rtc_s1_static_config.yaml')

        pge = RtcS1Executor(pge_name="RtcS1PgeTest", runconfig_path=runconfig_path)

        # Run only the pre-processor steps to ingest the runconfig and set up
        # directories
        pge.run_preprocessor()

        output_product_dir = join(os.curdir, "rtc_s1_test/output_dir/t069_147170_iw1")

        os.makedirs(output_product_dir, exist_ok=True)

        # Create a dummy RTC product
        rtc_metadata_file_path = join(output_product_dir, "rtc_product_v1.0.h5")

        create_test_rtc_metadata_product(rtc_metadata_file_path)

        rtc_metadata = pge._collect_rtc_product_metadata(rtc_metadata_file_path)

        # Initialize the core filename for the catalog metadata generation step
        pge._core_filename(inter_filename=rtc_metadata_file_path)

        # Render ISO metadata using the sample metadata
        iso_metadata = pge._create_iso_metadata(rtc_metadata)

        # Rendered template should not have any missing placeholders
        self.assertNotIn('!Not found!', iso_metadata)

    def test_rtc_s1_pge_input_validation(self):
        """Test the input validation checks."""
        runconfig_path = join(self.data_dir, 'test_rtc_s1_config.yaml')

        test_runconfig_path = join(self.data_dir, 'invalid_rtc_s1_runconfig.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)

        input_files_group = runconfig_dict['RunConfig']['Groups']['SAS']['runconfig']['groups']['input_file_group']
        # Test that a non-existent file is detected by pre-processor
        input_files_group['safe_file_path'] = ['non_existent_file.zip']

        with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        try:
            pge = RtcS1Executor(pge_name="RtcS1PgeTest", runconfig_path=test_runconfig_path)

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

            self.assertIn(
                "Could not locate specified input non_existent_file.zip",
                log_contents
            )
            # Reload the valid runconfig for next test
            with open(runconfig_path, 'r', encoding='utf-8') as infile:
                runconfig_dict = yaml.safe_load(infile)

            input_files_group = runconfig_dict['RunConfig']['Groups']['SAS']['runconfig']['groups']['input_file_group']

            # Test that an unexpected file extension for an existing file is caught
            new_name = join(input_files_group['safe_file_path'][0].replace('zip', 'tar'))
            input_files_group['safe_file_path'] = [new_name]

            os.system(f"touch {new_name}")

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = RtcS1Executor(pge_name="RtcS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(
                f"Input file {new_name} does not have an expected file extension.",
                log_contents
            )
        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

    # rtc_s1_pge._output_validation() is tested in the following 3 tests
    def test_rtc_s1_pge_output_validation_bad_extension(self):
        """Test the output validation checks made by RtcS1PostProcessorMixin."""
        runconfig_path = join(self.data_dir, 'test_rtc_s1_config.yaml')

        test_runconfig_path = join(self.data_dir, 'invalid_rtc_s1_runconfig.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)

        file_name = 'rtc_product.bad'

        primary_executable_group = runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']

        primary_executable_group['ProgramOptions'] = [
            '-p rtc_s1_test/output_dir/t069_147170_iw1/;',
            f'/bin/echo hello world > rtc_s1_test/output_dir/t069_147170_iw1/{file_name};',
            '/bin/echo RTC-S1 invoked with RunConfig']

        with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        try:
            pge = RtcS1Executor(pge_name="RtcS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(
                f"SAS output file {file_name} extension error:",
                log_contents
            )
        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

    def test_rtc_s1_pge_output_validation_empty_dir(self):
        """Test the output validation for an empty directory made by RtcS1PostProcessorMixin."""
        output_dir = 'rtc_s1_test/output_dir/t069_147170_iw1'
        runconfig_path = join(self.data_dir, 'test_rtc_s1_config.yaml')

        test_runconfig_path = join(self.data_dir, 'invalid_rtc_s1_runconfig.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)

        primary_executable_group = runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']

        primary_executable_group['ProgramOptions'] = [f'-p {output_dir}/;',
                                                      '/bin/echo RTC-S1 invoked with RunConfig']

        with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        try:
            pge = RtcS1Executor(pge_name="RtcS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(
                f"Empty SAS output directory: {os.path.abspath(output_dir)}",
                log_contents
            )
        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

    def test_rtc_s1_pge_output_validation_empty_file(self):
        """Test the output validation for an empty output file made by RtcS1PostProcessorMixin."""
        runconfig_path = join(self.data_dir, 'test_rtc_s1_config.yaml')

        test_runconfig_path = join(self.data_dir, 'invalid_rtc_s1_runconfig.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)

        file_name = 'rtc_product_empty.nc'

        primary_executable_group = runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']

        primary_executable_group['ProgramOptions'] = [
            '-p rtc_s1_test/output_dir/t069_147170_iw1/;',
            f'/bin/echo -n > rtc_s1_test/output_dir/t069_147170_iw1/{file_name};',
            '/bin/echo RTC-S1 invoked with RunConfig']

        with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        try:
            pge = RtcS1Executor(pge_name="RtcS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(
                f"SAS output file {file_name} exists, but is empty",
                log_contents
            )
        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

    def test_expected_extension(self):
        """Code coverage only right now"""
        # TODO when we get .nc and .h5 files this test will need to be modified
        runconfig_path = join(self.data_dir, 'test_rtc_s1_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_rtc_s1_config.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)

        product_group = runconfig_dict['RunConfig']['Groups']['SAS']['runconfig']['groups']['product_group']
        product_group['output_imagery_format'] = "NETCDF"
        product_group['save_browse'] = False  # Don't check for the .png browse image

        with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        try:
            pge = RtcS1Executor(pge_name="RtcPgeTest", runconfig_path=test_runconfig_path)
            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()
            self.assertIn(" extension error: expected one of ['nc']", log_contents)

            # Do the same thing again except with hdf5
            runconfig_path = join(self.data_dir, 'test_rtc_s1_config.yaml')
            test_runconfig_path = join(self.data_dir, 'invalid_rtc_s1_config.yaml')

            with open(runconfig_path, 'r', encoding='utf-8') as infile:
                runconfig_dict = yaml.safe_load(infile)

            product_group = runconfig_dict['RunConfig']['Groups']['SAS']['runconfig']['groups']['product_group']
            product_group['output_imagery_format'] = "HDF5"
            product_group['save_browse'] = False  # Don't check for the .png browse image

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = RtcS1Executor(pge_name="RtcPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()
            self.assertIn(" extension error: expected one of ['h5']", log_contents)

        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

    @patch.object(opera.util.img_utils, "gdal_edit", mock_gdal_edit)
    @patch.object(opera.util.img_utils, "save_as_cog", mock_save_as_cog)
    def test_no_burst_id(self):
        """Test _iso_metadata_filename with bad burst_id"""
        runconfig_path = join(self.data_dir, 'test_rtc_s1_config.yaml')
        pge = RtcS1Executor(pge_name="RtcPgeTest", runconfig_path=runconfig_path)
        pge.run()

        with self.assertRaises(RuntimeError):
            pge._iso_metadata_filename("bad_burst")

    @patch.object(opera.util.img_utils, "gdal_edit", mock_gdal_edit)
    @patch.object(opera.util.img_utils, "save_as_cog", mock_save_as_cog)
    def test_bad_iso_metadata_template(self):
        """Verify code when the QA application is enabled"""
        runconfig_path = join(self.data_dir, 'test_rtc_s1_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_rtc_s1_config.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)

        primary_executable = runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']
        primary_executable['IsoTemplatePath'] = 'pge/rtc_s1/templates/OPERA_ISO_metadata_L2_RTC_S1_template.xml'

        with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        try:
            pge = RtcS1Executor(pge_name="RtcPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()
            self.assertIn("Could not load ISO template", log_contents)

        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

    @patch.object(opera.util.img_utils, "gdal_edit", mock_gdal_edit)
    @patch.object(opera.util.img_utils, "save_as_cog", mock_save_as_cog)
    def test_qa_enabled(self):
        """Test the staging of the qa.log files."""
        # Verify code when the QA application is enabled
        runconfig_path = join(self.data_dir, 'test_rtc_s1_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_rtc_s1_config.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)

        qa_executable = runconfig_dict['RunConfig']['Groups']['PGE']['QAExecutable']
        qa_executable['Enabled'] = True

        qa_executable['ProgramPath'] = 'rtc_s1_test/input_dir/test_qa_rwx.py'

        with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        try:
            pge = RtcS1Executor(pge_name="RtcS1PgeTest", runconfig_path=test_runconfig_path)

            pge.run()

            # Verify error conditions
            runconfig_path = join(self.data_dir, 'test_rtc_s1_config.yaml')
            test_runconfig_path = join(self.data_dir, 'invalid_rtc_s1_config.yaml')

            with open(runconfig_path, 'r', encoding='utf-8') as infile:
                runconfig_dict = yaml.safe_load(infile)

            qa_executable = runconfig_dict['RunConfig']['Groups']['PGE']['QAExecutable']
            qa_executable['Enabled'] = True

            qa_executable['ProgramPath'] = 'rtc_s1_test/input_dir/test_qa_ro.py'

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = RtcS1Executor(pge_name="RtcS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()
            self.assertIn("Requested QA program path rtc_s1_test/input_dir/test_qa_ro.py exists, but "
                          "does not have execute permissions.", log_contents)
        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)


if __name__ == "__main__":
    unittest.main()
