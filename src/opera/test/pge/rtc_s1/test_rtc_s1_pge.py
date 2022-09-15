#!/usr/bin/env python3

"""
==================
test_rtc_s1_pge.py
==================

Unit tests for the pge/rtc_s1/rtc_s1_pge.py module.
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
from opera.pge.rtc_s1.rtc_s1_pge import RtcS1Executor
from opera.util import PgeLogger


class RtcS1PgeTestCase(unittest.TestCase):

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

        os.system(f"touch {join(input_dir, 'SAFE.zip')}")

        os.system(f"touch {join(input_dir, 'ORBIT.EOF')}")

        os.system(f"touch {join(input_dir, 'dem.tif')}")

        os.chdir(self.working_dir.name)

    def tearDown(self) -> None:
        """Return to test directory"""
        os.chdir(self.test_dir)
        self.working_dir.cleanup()

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
            pge.runconfig.output_product_path,
            pge._rtc_filename(inter_filename='rtc_s1_test/output_dir/t069_147170_iw1/rtc_product.nc')
        )
        self.assertTrue(os.path.exists(expected_output_file))

        # Open and read the log
        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn(f"RTC-S1 invoked with RunConfig {expected_sas_config_file}", log_contents)
