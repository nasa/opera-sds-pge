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

import os
from os.path import abspath, exists, join

from pkg_resources import resource_filename

from opera.pge import PgeExecutor, RunConfig
from opera.util.metfile import MetFile
from opera.util import PgeLogger


class MetFileTestCase(unittest.TestCase):
    """Base test class using unittest"""

    starting_dir = None
    working_dir = None
    test_dir = None

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
            prefix="test_met_file_", suffix='_temp', dir=os.curdir)

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
            __setitem__
            __getitem__
            write(met_file_name, met_dict=None):
                - Writes .json catalog metadata file
            write(met_file_name, met_dict='update_dict'):
                - Adds key/value pairs before writing .json catalog metadata file
            read():
                - Reads the catalog metadata file into self.met_dict.

        """
        met_file = 'testMetFile.json'
        met_data = MetFile(met_file)
        self.assertIsInstance(met_data, MetFile)
        # Verify __setitem__ and __getitem__
        met_data["test key"] = "test value"
        self.assertEqual(met_data["test key"], "test value")
        # Verify write()
        met_data.write()
        # Verify that write() created the simple met file
        self.assertTrue(exists(met_file))
        # Verify read and return
        met_data.read()
        # Verify the key value pair read from the file
        self.assertEqual(met_data["test key"], "test value")
        # Verify merge with an existing met file
        update_dict = {"test key 2": "test value 2"}
        met_merge = MetFile(met_file, update_dict)
        met_merge.write()
        # Verify the update
        met_data.read()
        # Verify both lines are in the file
        self.assertEqual(met_data["test key"], "test value")
        self.assertEqual(met_data["test key 2"], "test value 2")

    def test_validate_json_file(self):
        """
        Instantiates a MetFile object
        Creates a dummy catalog metadata with valid data
        Writes to a JSON file
        Verifies that the schema test passes
        Modify metadata, making an invalid entry
        Verify the schema test fails

        """
        # Creat a dummy metadata file
        catalog_metadata = {
            'PGE_Name': "BASE_PGE_TEST",
            'PGE_Version': "1.0.test",
            'SAS_Version': "2.0.test",
            'Input_Files': ["input/input_file01.h5", "input/input_file02.h5"],
            'Ancillary_Files': ["input/input_dem.vrt"],
            'Production_DateTime': "2022-01-20T12:07:10.9143060000Z"
        }

        met_file = 'testCatalogMetadata.json'
        met_data = MetFile(met_file, catalog_metadata)
        self.assertIsInstance(met_data, MetFile)
        # Save the test catalog metadata to temporary
        met_data.write()
        # Verify that the schema test passes
        self.assertTrue(met_data.validate_json_file(met_file, met_data.get_schema_file_path()))
        # Modify the test catalog metadata
        met_data.read()
        # Remove a ':' from the between mm:ss
        met_data['Production_DateTime'] = "2022-01-20T12:0710.9143060000Z"
        # Verify that the schema test fails
        met_data.write()
        self.assertFalse(met_data.validate_json_file(met_file, met_data.get_schema_file_path()))
