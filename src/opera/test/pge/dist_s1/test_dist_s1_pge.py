#!/usr/bin/env python3

"""
===================
test_dist_s1_pge.py
===================
Unit tests for the pge/dist_s1/dist_s1_pge.py module.
"""

import os
import random
import tempfile
import unittest
from io import StringIO
from os.path import abspath, join
from pathlib import Path

from pkg_resources import resource_filename

from opera.pge import RunConfig
from opera.pge.dist_s1.dist_s1_pge import DistS1Executor
from opera.util import PgeLogger


class DistS1PgeTestCase(unittest.TestCase):
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
            prefix="test_dist_s1_pge_", suffix="_temp", dir=os.curdir
        )

        # Create the input dir expected by the test RunConfig and add a
        # dummy input file
        input_dir = join(self.working_dir.name, "dist_s1_pge_test/input_dir")
        os.makedirs(input_dir, exist_ok=True)

        self.input_file = tempfile.NamedTemporaryFile(
            dir=input_dir, prefix="test_input_", suffix=".tif"
        )

        os.chdir(self.working_dir.name)

    def tearDown(self) -> None:
        """Return to starting directory"""
        os.chdir(self.test_dir)
        self.input_file.close()
        self.working_dir.cleanup()

    @staticmethod
    def _create_dummy_input_files(run_config_path):
        """
        Create dummy input files in the working directory based on the inputs
        section of a RunConfig
        """
        rc = RunConfig(run_config_path)

        for file in rc.input_files:
            Path(file).parent.mkdir(parents=True, exist_ok=True)
            with open(file, "wb") as f:
                f.write(random.randbytes(1024))

    def test_dist_s1_pge_execution(self):
        """
        Test execution of the DistS1Executor class and its associated mixins
        using a test RunConfig that creates dummy expected output files and logs
        a message to be captured by PgeLogger.
        """
        runconfig_path = join(self.data_dir, 'test_dist_s1_config.yaml')

        DistS1PgeTestCase._create_dummy_input_files(runconfig_path)

        pge = DistS1Executor(pge_name="DistS1PgeTest", runconfig_path=runconfig_path)

        # Check that basic attributes were initialized
        self.assertEqual(pge.name, "DIST-S1")
        self.assertEqual(pge.pge_name, "DistS1PgeTest")
        self.assertEqual(pge.runconfig_path, runconfig_path)

        # Check that other objects have not been instantiated yet
        self.assertIsNone(pge.runconfig)
        self.assertIsNone(pge.logger)

        # Kickoff execution of DIST-S1 PGE
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
        expected_sas_config_file = join(pge.runconfig.scratch_path, 'test_dist_s1_config_sas.yaml')
        self.assertTrue(os.path.exists(expected_sas_config_file))

        # Check that the log file was created and moved into the output directory
        expected_log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(expected_log_file))

        # Open and read the log
        with open(expected_log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn(f"DIST-S1 invoked with RunConfig {expected_sas_config_file}", log_contents)


if __name__ == "__main__":
    unittest.main()
