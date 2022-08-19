#!/usr/bin/env python3

"""
===================
test_cslc_s1_pge.py
===================

Unit tests for the pge/cslc_s1/cslc_s1_pge.py module.
"""

import glob
import json
import os
import re
import shutil
import tempfile
import unittest
from io import StringIO
from os.path import abspath, join

from pkg_resources import resource_filename

from opera.pge import RunConfig
from opera.pge.cslc_s1.cslc_s1_pge import CslcS1Executor
from opera.util import PgeLogger


class CslcS1PgeTestCase(unittest.TestCase):

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

        # Create the input dir expected by the test RunConfig and add a
        # dummy input file
        input_dir = join(self.working_dir.name, "cslc_pge_test/input_dir")
        os.makedirs(input_dir, exist_ok=True)

        self.input_file = tempfile.NamedTemporaryFile(
            dir=input_dir, prefix="test_input_", suffix=".tiff"
        )

        os.chdir(self.working_dir.name)

    def tearDown(self) -> None:
        """Return to starting directory"""
        os.chdir(self.test_dir)
        self.input_file.close()
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
        self.assertEqual(pge.name, "CSLC")
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

        # Check that the ISO metadata file was created (not all placeholders are
        # expected to be filled in by this test)
        expected_iso_metadata_file = join(
            pge.runconfig.output_product_path, pge._iso_metadata_filename())
        self.assertTrue(os.path.exists(expected_iso_metadata_file))

        # Check that the log file was created and moved into the output directory
        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        # Lastly, check that the dummy output products were created and renamed
        expected_image_file = join(
            pge.runconfig.output_product_path, pge._geotiff_filename(inter_filename=''))
        self.assertTrue(os.path.exists(expected_image_file))

        expected_image_metadata_file = join(
            pge.runconfig.output_product_path, pge._json_metadata_filename(inter_filename='')
        )
        self.assertTrue(os.path.exists(expected_image_metadata_file))

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
        metadata_files = glob.glob(join(pge.runconfig.output_product_path, "*Z.json"))

        self.assertEqual(len(metadata_files), 1)

        metadata_file = metadata_files[0]

        with open(metadata_file, 'r') as infile:
            cslc_metadata = json.load(infile)

        # Compare the filename returned by the PGE for JSON metadata files
        # to a regex which should match each component of the final filename
        file_name = pge._json_metadata_filename(inter_filename='')

        file_name_regex = rf"{pge.PROJECT}_{pge.LEVEL}_{pge.NAME}_" \
                          rf"{cslc_metadata['platform_id']}_" \
                          rf"IW_{cslc_metadata['burst_id'].upper().replace('_', '-')}_" \
                          rf"{cslc_metadata['polarization']}_" \
                          rf"\d{{8}}T\d{{6}}Z_v{pge.SAS_VERSION}_\d{{8}}T\d{{6}}Z.json"

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

        # Copy sample JSON metadata to the output directory of the PGE
        output_dir = join(os.curdir, "cslc_pge_test/output_dir")

        sample_metadata_file = join(self.data_dir, 't64_135524_iw2_20220501_VV.json')

        shutil.copy(sample_metadata_file, output_dir)

        # Initialize the core filename for the catalog metadata generation step
        pge._core_filename(inter_filename=sample_metadata_file)

        # Render ISO metadata using the sample metadata
        iso_metadata = pge._create_iso_metadata()

        # Rendered template should not have any missing placeholders
        self.assertNotIn('!Not found!', iso_metadata)


if __name__ == "__main__":
    unittest.main()