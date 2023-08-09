#!/usr/bin/env python3

"""
===================
test_cslc_s1_pge.py
===================

Unit tests for the pge/cslc_s1/cslc_s1_pge.py module.
"""

import glob
import os
import re
import stat
import tempfile
import unittest
from io import StringIO
from os.path import abspath, join

from pkg_resources import resource_filename

import yaml

from opera.pge import RunConfig
from opera.pge.cslc_s1.cslc_s1_pge import CslcS1Executor
from opera.util import PgeLogger
from opera.util.metadata_utils import create_test_cslc_metadata_product
from opera.util.metadata_utils import get_cslc_s1_product_metadata


class CslcS1PgeTestCase(unittest.TestCase):
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
            prefix="test_cslc_s1_pge_", suffix="_temp", dir=os.curdir
        )

        # Create the input dir expected by the test RunConfig and add
        # dummy input files with the names expected by the RunConfig
        input_dir = join(self.working_dir.name, "cslc_pge_test/input_dir")
        os.makedirs(input_dir, exist_ok=True)

        # Use empty files for testing the existence of required input files

        os.system(
            f"touch {join(input_dir, 'S1A_IW_SLC__1SDV_20220501T015035_20220501T015102_043011_0522A4_42CC.zip')}"
        )

        os.system(
            f"touch {join(input_dir, 'S1A_OPER_AUX_POEORB_OPOD_20220521T081912_V20220430T225942_20220502T005942.EOF')}"
        )

        os.system(
            f"touch {join(input_dir, 'dem_4326.tiff')}"
        )

        os.system(
            f"touch {join(input_dir, 'jplg1210.22i')}"
        )

        # 'db.sqlite3' simulates the burst_id database file
        os.system(
            f"touch {join(input_dir, 'db.sqlite3')}"
        )

        # When the [QAExecutable] is enabled, a python script (specified in [QAExecutable][ProgramPath] is executed.
        # The empty files below simulate a script with proper permissions, and a script with improper permissions.
        os.system(
            f"touch {join(input_dir, 'test_qa_rwx.py')}"  # rwx - read, write, execute
        )
        os.chmod(f"{join(input_dir, 'test_qa_rwx.py')}", stat.S_IRWXU)   # Set to read, write, execute by owner

        os.system(
            f"touch {join(input_dir, 'test_qa_ro.py')}"   # r0 - read only
        )
        os.chmod(f"{join(input_dir, 'test_qa_ro.py')}", stat.S_IREAD)  # Set to read by owner

        os.chdir(self.working_dir.name)

    def tearDown(self) -> None:
        """Return to starting directory"""
        os.chdir(self.test_dir)
        self.working_dir.cleanup()

    def test_cslc_s1_pge_execution(self):
        """
        Test execution of the CslcS1Executor class and its associated mixins
        using a test RunConfig that creates dummy expected output files and logs
        a message to be captured by PgeLogger.

        """
        runconfig_path = join(self.data_dir, 'test_cslc_s1_config.yaml')

        pge = CslcS1Executor(pge_name="CslcS1PgeTest", runconfig_path=runconfig_path)

        # Check that basic attributes were initialized
        self.assertEqual(pge.name, "CSLC-S1")
        self.assertEqual(pge.pge_name, "CslcS1PgeTest")
        self.assertEqual(pge.runconfig_path, runconfig_path)

        # Check that other objects have not been instantiated yet
        self.assertIsNone(pge.runconfig)
        self.assertIsNone(pge.logger)

        # Kickoff execution of CSLC-S1 PGE
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
        expected_sas_config_file = join(pge.runconfig.scratch_path, 'test_cslc_s1_config_sas.yaml')
        self.assertTrue(os.path.exists(expected_sas_config_file))

        # Check that the catalog metadata file was created in the output directory
        expected_catalog_metadata_file = join(
            pge.runconfig.output_product_path, pge._catalog_metadata_filename())
        self.assertTrue(os.path.exists(expected_catalog_metadata_file))

        # Check that the log file was created and moved into the output directory
        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        # Lastly, check that the dummy output product was created and renamed
        expected_image_file = join(
            pge.runconfig.output_product_path,
            pge._h5_filename(inter_filename='cslc_pge_test/output_dir/t064_135518_iw1/20220501/'
                                            't064_135518_iw1_20220501_VV.h5')
        )
        self.assertTrue(os.path.exists(expected_image_file))

        # Open and read the log
        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn(f"CSLC-S1 invoked with RunConfig {expected_sas_config_file}", log_contents)

    def test_filename_application(self):
        """Test the filename convention applied to CSLC output products"""
        runconfig_path = join(self.data_dir, 'test_cslc_s1_config.yaml')

        pge = CslcS1Executor(pge_name="CslcPgeTest", runconfig_path=runconfig_path)

        pge.run()

        # Grab the metadata generated from the PGE run, as it is used to generate
        # the final filename for output products
        metadata_files = glob.glob(join(pge.runconfig.output_product_path, "OPERA_L2_CSLC-S1_T*.h5"))

        self.assertEqual(len(metadata_files), 1)

        metadata_file = metadata_files[0]

        cslc_metadata = get_cslc_s1_product_metadata(metadata_file)
        burst_metadata = cslc_metadata['processing_information']['input_burst_metadata']

        # Compare the filename returned by the PGE for JSON metadata files
        # to a regex which should match each component of the final filename
        file_name = pge._h5_filename(
            inter_filename='cslc_pge_test/output_dir/t064_135518_iw1/20220501/t064_135518_iw1_20220501.h5'
        )

        file_name_regex = rf"{pge.PROJECT}_{pge.LEVEL}_{pge.NAME}_" \
                          rf"{cslc_metadata['identification']['burst_id'].upper().replace('_', '-')}_" \
                          rf"\d{{8}}T\d{{6}}Z_\d{{8}}T\d{{6}}Z_" \
                          rf"{burst_metadata['platform_id']}_" \
                          rf"{burst_metadata['polarization']}_" \
                          rf"v{pge.runconfig.product_version}.h5"


        result = re.match(file_name_regex, file_name)

        self.assertIsNotNone(result)
        self.assertEqual(result.group(), file_name)

        file_name = pge._static_layers_filename(
            inter_filename='cslc_pge_test/output_dir/t064_135518_iw1/20220501/static_layers_t064_135518_iw1.h5'
        )

        file_name_regex = rf"{pge.PROJECT}_{pge.LEVEL}_{pge.NAME}-STATIC_" \
                          rf"{cslc_metadata['identification']['burst_id'].upper().replace('_', '-')}_" \
                          rf"\d{{8}}_\d{{8}}T\d{{6}}Z_" \
                          rf"{burst_metadata['platform_id']}_" \
                          rf"v{pge.runconfig.product_version}.h5"

        result = re.match(file_name_regex, file_name)

        self.assertIsNotNone(result)
        self.assertEqual(result.group(), file_name)

        # Ensure the DataValidityStartDate value was used in the naming convention
        # for the static layers product
        expected_data_validity_start_date = pge.runconfig.data_validity_start_date

        self.assertIn(str(expected_data_validity_start_date), file_name)

        file_name = pge._browse_filename(
            inter_filename='cslc_pge_test/output_dir/t064_135518_iw1/20220501/t064_135518_iw1_20220501.png'
        )

        file_name_regex = rf"{pge.PROJECT}_{pge.LEVEL}_{pge.NAME}_" \
                          rf"{cslc_metadata['identification']['burst_id'].upper().replace('_', '-')}_" \
                          rf"\d{{8}}T\d{{6}}Z_\d{{8}}T\d{{6}}Z_" \
                          rf"{burst_metadata['platform_id']}_" \
                          rf"{burst_metadata['polarization']}_" \
                          rf"v{pge.runconfig.product_version}_BROWSE.png"

        result = re.match(file_name_regex, file_name)

        self.assertIsNotNone(result)
        self.assertEqual(result.group(), file_name)

    def test_iso_metadata_creation(self):
        """
        Test that the ISO metadata template is fully filled out when realistic
        CSLC JSON metadata is available.
        """
        runconfig_path = join(self.data_dir, 'test_cslc_s1_config.yaml')

        pge = CslcS1Executor(pge_name="CslcPgeTest", runconfig_path=runconfig_path)

        # Run only the pre-processor steps to ingest the runconfig and set
        # up directories
        pge.run_preprocessor()

        # Create a sample metadata file within the output directory of the PGE
        output_dir = join(os.curdir, "cslc_pge_test/output_dir")

        cslc_metadata_path = join(output_dir, 't064_135518_iw1_20220501.h5')

        create_test_cslc_metadata_product(cslc_metadata_path)

        cslc_metadata = pge._collect_cslc_product_metadata(cslc_metadata_path)

        # Initialize the core filename for the catalog metadata generation step
        pge._core_filename(inter_filename=cslc_metadata_path)

        # Render ISO metadata using the sample metadata
        iso_metadata = pge._create_iso_metadata(cslc_metadata)

        # Rendered template should not have any missing placeholders
        self.assertNotIn('!Not found!', iso_metadata)

        os.unlink(cslc_metadata_path)

        # Test bad iso_template_path
        test_runconfig_path = join(self.data_dir, 'invalid_cslc_s1_runconfig.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)

        primary_executable = runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']
        primary_executable['IsoTemplatePath'] = "pge/cslc_s1/templates/OPERA_ISO_metadata_L2_CSLC_S1_template.xml"

        with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        try:
            pge = CslcS1Executor(pge_name="CslcPgeTest", runconfig_path=test_runconfig_path)

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

    def test_cslc_s1_pge_input_validation(self):
        """Test the input validation checks."""
        runconfig_path = join(self.data_dir, 'test_cslc_s1_config.yaml')

        test_runconfig_path = join(self.data_dir, 'invalid_cslc_s1_runconfig.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)

        input_files_group = runconfig_dict['RunConfig']['Groups']['SAS']['runconfig']['groups']['input_file_group']

        # Test that a non-existent file is detected by pre-processor
        input_files_group['safe_file_path'] = ['non_existent_file.zip']

        with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        try:
            pge = CslcS1Executor(pge_name="CslcS1PgeTest", runconfig_path=test_runconfig_path)

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

            pge = CslcS1Executor(pge_name="CslcS1PgeTest", runconfig_path=test_runconfig_path)

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

    def test_cslc_s1_output_validation(self):
        """Test the output validation checks made by CslcS1PostProcessorMixin."""
        runconfig_path = join(self.data_dir, 'test_cslc_s1_config.yaml')

        test_runconfig_path = join(self.data_dir, 'invalid_cslc_s1_runconfig.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)

        primary_executable_group = runconfig_dict['RunConfig']['Groups']['PGE']['PrimaryExecutable']

        # Test with a SAS command that does not produce any output file,
        # post-processor should detect that expected output is missing
        primary_executable_group['ProgramPath'] = 'echo'
        primary_executable_group['ProgramOptions'] = ['hello world']

        with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        try:
            pge = CslcS1Executor(pge_name="CslcS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn("No SAS output file(s) found",
                          log_contents)

            # Test with a SAS command that produces the expected output file, but
            # one that is empty (size 0 bytes). Post-processor should detect this
            # and flag an error
            primary_executable_group['ProgramPath'] = 'mkdir'
            primary_executable_group['ProgramOptions'] = [
                '-p cslc_pge_test/output_dir/t64_iw2_b204/20220501/;',
                'touch cslc_pge_test/output_dir/t64_iw2_b204/20220501/t64_iw2_b204_20220501_VV.h5'
            ]

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = CslcS1Executor(pge_name="CslcS1PgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_output_file = 'cslc_pge_test/output_dir/t64_iw2_b204/20220501/t64_iw2_b204_20220501_VV.h5'
            self.assertTrue(os.path.exists(expected_output_file))

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()

            self.assertIn(f"SAS output file {os.path.basename(expected_output_file)} "
                          f"exists, but is empty", log_contents)

        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)

    def test_geotiff_json_filenames(self):
        """Test that tiff and json filenames are properly returned. Code coverage only."""
        runconfig_path = join(self.data_dir, 'test_cslc_s1_config.yaml')
        pge = CslcS1Executor(pge_name="CslcPgeTest", runconfig_path=runconfig_path)
        pge.run()
        inner_fname = 'cslc_pge_test/output_dir/t064_135518_iw1/20220501/t064_135518_iw1_20220501_VV.tiff'
        try:
            pge._geotiff_filename(inner_fname)
            inner_fname = 'cslc_pge_test/output_dir/t064_135518_iw1/20220501/t064_135518_iw1_20220501_VV.json'
            pge._json_metadata_filename(inner_fname)
            pge._qa_log_filename()
        except ValueError:
            self.fail()

    def test_qa_enabled(self):
        """Test the staging of the qa.log files."""
        # Verify code when the QA application is enabled
        runconfig_path = join(self.data_dir, 'test_cslc_s1_config.yaml')
        test_runconfig_path = join(self.data_dir, 'invalid_cslc_s1_config.yaml')

        with open(runconfig_path, 'r', encoding='utf-8') as infile:
            runconfig_dict = yaml.safe_load(infile)

        qa_executable = runconfig_dict['RunConfig']['Groups']['PGE']['QAExecutable']
        qa_executable['Enabled'] = True

        qa_executable['ProgramPath'] = 'cslc_pge_test/input_dir/test_qa_rwx.py'

        with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
            yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

        try:
            pge = CslcS1Executor(pge_name="CslcPgeTest", runconfig_path=test_runconfig_path)

            pge.run()

            # Verify error conditions
            runconfig_path = join(self.data_dir, 'test_cslc_s1_config.yaml')
            test_runconfig_path = join(self.data_dir, 'invalid_cslc_s1_config.yaml')

            with open(runconfig_path, 'r', encoding='utf-8') as infile:
                runconfig_dict = yaml.safe_load(infile)

            qa_executable = runconfig_dict['RunConfig']['Groups']['PGE']['QAExecutable']
            qa_executable['Enabled'] = True

            qa_executable['ProgramPath'] = 'cslc_pge_test/input_dir/test_qa_ro.py'

            with open(test_runconfig_path, 'w', encoding='utf-8') as outfile:
                yaml.safe_dump(runconfig_dict, outfile, sort_keys=False)

            pge = CslcS1Executor(pge_name="CslcPgeTest", runconfig_path=test_runconfig_path)

            with self.assertRaises(RuntimeError):
                pge.run()

            expected_log_file = pge.logger.get_file_name()
            self.assertTrue(os.path.exists(expected_log_file))

            with open(expected_log_file, 'r', encoding='utf-8') as infile:
                log_contents = infile.read()
            self.assertIn("Requested QA program path cslc_pge_test/input_dir/test_qa_ro.py exists, but "
                          "does not have execute permissions.", log_contents)

        finally:
            if os.path.exists(test_runconfig_path):
                os.unlink(test_runconfig_path)


if __name__ == "__main__":
    unittest.main()
