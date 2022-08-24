#!/usr/bin/env python

"""
=================
test_metfile.py
=================

Unit tests for the util/metfile.py module.
"""
import os
import tempfile
import unittest
from os.path import abspath, exists

from opera.util.metfile import MetFile

from pkg_resources import resource_filename


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

        os.chdir(cls.test_dir)

    @classmethod
    def tearDownClass(cls) -> None:
        """
        At completion re-establish starting directory
        -------
        """
        os.chdir(cls.starting_dir)

    def setUp(self) -> None:
        """
        Use the temporary directory as the working directory
        -------
        """
        self.working_dir = tempfile.TemporaryDirectory(
            prefix="test_met_file_", suffix='_temp', dir=os.curdir
        )
        os.chdir(self.working_dir.name)

    def tearDown(self) -> None:
        """
        Return to starting directory
        -------
        """
        os.chdir(self.test_dir)
        self.working_dir.cleanup()

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
        met_data = MetFile()
        self.assertIsInstance(met_data, MetFile)
        # Verify __setitem__ and __getitem__
        met_data["test key"] = "test value"
        self.assertEqual(met_data["test key"], "test value")
        # Verify write()
        met_data.write(met_file)
        # Verify that write() created the simple met file
        self.assertTrue(exists(met_file))
        # Verify read and return
        met_data.read(met_file)
        # Verify the key value pair read from the file
        self.assertEqual(met_data["test key"], "test value")
        # Verify merge with an existing met file
        update_dict = {"test key 2": "test value 2"}
        met_merge = MetFile(update_dict)
        met_merge.write(met_file)
        # Verify the update
        met_data.read(met_file)
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
        # Create a dummy metadata file
        catalog_metadata = {
            'PGE_Name': "BASE_PGE",
            'PGE_Version': "1.0.test",
            'SAS_Version': "2.0.test",
            'Input_Files': ["input/input_file01.h5", "input/input_file02.h5"],
            'Ancillary_Files': ["input/input_dem.vrt"],
            'Production_DateTime': "2022-01-20T12:07:10.9143060000Z",
            'Output_Product_Checksums': {
                "output_file01.tif": "abcdefghijklmnop"
            }
        }

        met_file = 'testCatalogMetadata.json'
        met_data = MetFile(catalog_metadata)
        self.assertIsInstance(met_data, MetFile)

        # Save the test catalog metadata to temporary
        met_data.write(met_file)

        # Verify that the schema test passes
        self.assertTrue(met_data.validate(met_data.get_schema_file_path()))

        # Modify the test catalog metadata
        met_data.read(met_file)

        # Remove a ':' from the between mm:ss
        met_data['Production_DateTime'] = "2022-01-20T12:0710.9143060000Z"

        # Verify that the schema test fails
        self.assertFalse(met_data.validate(met_data.get_schema_file_path()))
