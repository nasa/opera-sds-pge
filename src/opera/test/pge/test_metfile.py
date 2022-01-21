#!/usr/bin/env python

#
# Copyright 2021, by the California Institute of Technology.
# ALL RIGHTS RESERVED.
# United States Government sponsorship acknowledged.
# Any commercial use must be negotiated with the Office of Technology Transfer
# at the California Institute of Technology.
# This software may be subject to U.S. export control laws and regulations.
# By accepting this document, the user agrees to comply with all applicable
# U.S. export laws and regulations. User has the responsibility to obtain
# export licenses, or other export authority as may be required, before
# exporting such information to foreign countries or providing access to
# foreign persons.
#

"""
=================
test_metfile.py
=================

Unit tests for the util/metfile.py module.
"""
import fileinput
import os
import shutil
import tempfile
import unittest

from os.path import abspath, join

from pkg_resources import resource_filename

from opera.pge import PgeExecutor, RunConfig
from opera.util.metfile import MetFile
from opera.util import PgeLogger


class MetFileTestCase(unittest.TestCase):
    """Base test class using unittest"""

    TEST_MET_FILE = resource_filename('opera', '/test/pge/base_pge_test/scratch/testMetFile.met')

    @classmethod
    def setUpClass(cls) -> None:
        """
        Set up directories for testing
        Initialize regular expression
        Initialize other class variables

        """
        cls.starting_dir = abspath(os.curdir)
        cls.test_dir = resource_filename(__name__, "")
        cls.data_dir = join(cls.test_dir, "data")

        os.chdir(cls.test_dir)

        cls.working_dir = tempfile.TemporaryDirectory(
            prefix="test_time_", suffix='temp', dir=os.curdir)

    @classmethod
    def tearDownClass(cls) -> None:
        """
        At completion re-establish starting directory
        -------
        """
        cls.working_dir.cleanup()
        os.chdir(cls.starting_dir)

    def setUp(self) -> None:
        """
        Use the temporary directory as the working directory
        -------
        """
        os.chdir(self.working_dir.name)

    def tearDown(self) -> None:
        """
        Return to starting directory
        -------
        """
        os.chdir(self.test_dir)

    def testMetFile(self):
        """
        Tests instantiation of MetFile class
        Methods tested in MetFile class:
            set_key_value()
            write_met_file()
            read_met_file()

        """
        met_file = MetFileTestCase.TEST_MET_FILE
        met_data = MetFile(met_file)
        self.assertIsInstance(met_data, MetFile)

        # Test __setitem__ and __getitem__
        met_data["test key"] = "test value"
        self.assertEqual(met_data["test key"], "test value")
        # Test write_met_file()
        met_data.write_met_file()
        # Copy contents of the file into a variable
        with open(met_file, 'r') as mf:
            lines = (mf.readlines())
        # Test string to look for string in the dictionary
        test_str = '  "test key": "test value",\n'
        self.assertIn(test_str, lines)
        # Test read_met_file()
        met_dict = met_data.read_met_file()
        self.assertEqual(met_data['test key'], 'test value')

        # Read another line to test for an existing file
        met_dict = "test key 2", "test value 2"
        met_data.write_met_file()
        with open(met_file, 'r') as mf:
            lines = (mf.readlines())
        # Test string to look for
        test_str = '  "test key 2": "test value 2"\n'
        self.assertIn(test_str, lines)
        # Test read_met_file()
        met_dict = met_data.read_met_file()
        self.assertEqual(met_dict['test key 2'], 'test value 2')

    def test_validate_json_file(self):
        """
        Instantiates pge objects
        Verifies that the catalog metadata json file is created
        Verifies that the schema is correct
        Verifies that an Error is written to the log file is there is a schema error in the catalog metadata file.

        """
        # instantiate a pge object
        runconfig_path = join(self.data_dir, 'test_base_pge_config.yaml')

        pge = PgeExecutor(pge_name='BasePgeTest', runconfig_path=runconfig_path)

        # Check that basic attributes were initialized
        self.assertEqual(pge.name, "PgeExecutor")
        self.assertEqual(pge.pge_name, "BasePgeTest")
        self.assertEqual(pge.runconfig_path, runconfig_path)

        # Kickoff execution of base PGE
        pge.run()

        # Check that runconfig and logger were instantiated as expected
        self.assertIsInstance(pge.runconfig, RunConfig)
        self.assertIsInstance(pge.logger, PgeLogger)

        # Verify a schema check was successfully recorded in the log file
        log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(log_file))

        # Open the log file, and check that the validation error details were captured
        with open(log_file, 'r', encoding='utf-8') as log:
            log = log.read()

        # Verify the catalog metadata json file creation was logged.
        self.assertIn("Successfully created catalog metadata json file.", log)

        # Change the schema file
        met = MetFile
        # save the schema file
        schema_file = met.get_schema_file_path()
        shutil.copyfile(schema_file, 'save_file.json')

        # Change the regular expression in for date-time in the schema file
        self.change_schema(schema_file, {'d+': 'd-'})

        # Run the PGE again
        pge = PgeExecutor(pge_name='BasePgeTest', runconfig_path=runconfig_path)
        pge.run()

        # Verify a schema check failed in the log file
        log_file = pge.logger.get_file_name()

        # Open the log file, and check that the validation error details were captured
        with open(log_file, 'r', encoding='utf-8') as log:
            log = log.read()

        # Verify the SCHEMA ERROR: was logged.
        self.assertIn("SCHEMA ERROR: ", log)

        # Restore the original schema file
        shutil.copyfile('save_file.json', schema_file)
        # Run the PGE again
        pge = PgeExecutor(pge_name='BasePgeTest', runconfig_path=runconfig_path)
        pge.run()
        # Verify a schema check was successfully recorded in the log file
        log_file = pge.logger.get_file_name()
        self.assertTrue(os.path.exists(log_file))

        # Open the log file, and check that the validation error details were captured
        with open(log_file, 'r', encoding='utf-8') as log:
            log = log.read()

        # Verify the catalog metadata json file creation was logged.
        self.assertIn("Successfully created catalog metadata json file.", log)

    def change_schema(self, schema_file, replace_values):
        """Used to modify 'catalog_metadata_schema.json'

        Parameters
        ----------
        schema_file : JSON
            Schema file for the catalog_metadata_schema check
        replace_values : str
            Text string to be added or modify the schema file

        """
        for line in fileinput.input(schema_file, inplace=True):
            for search_text in replace_values:
                replace_text = replace_values[search_text]
                line = line.replace(search_text, replace_text)
            print(line, end='')
