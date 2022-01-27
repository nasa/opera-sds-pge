#
# Copyright 2022, by the California Institute of Technology.
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
=========
metfile.py
=========

Creates .met file for the OPERA PGEs.

This module is adapted for OPERA from the NISAR PGE R2.0.0 util/metfile.py
Original Author: Alice Stanboli
Adapted By: Jim Hofman

"""


import json
import jsonschema
import os

from pkg_resources import resource_filename


class MetFile:
    """Class used to read and write .json catalog metadata files."""

    SCHEMA_PATH = resource_filename('opera', 'schema/catalog_metadata_schema.json')

    def __init__(self, met_file_name, met_dict=None):
        """
        Constructor get filename and initialize dictionary

        Parameters
        ----------
        met_file_name : str, required
            Name of the file that will be written to or read.
        met_dict : dict, optional
            Dictionary passed to be merged with existing catalog metadata
            file or to be used to make a new catalog metadata file

        """

        if met_dict is None:
            met_dict = {}
        self._met_file = met_file_name
        self.met_dict = met_dict
        self.combined_error_msg = None

    def __setitem__(self, key_name, value):
        self.met_dict[key_name] = value

    def __getitem__(self, key_name):
        return self.met_dict[key_name]

    @classmethod
    def get_schema_file_path(cls):
        """Returns the path to schema file"""
        return cls.SCHEMA_PATH

    def write(self):
        """
        Writes the catalog metadata file in JSON format to disk.
        If there is an existing catalog metadata file:
            1) Load the file as JSON
            2) Copy the file into a python dictionary
            3) Use update() method:
                 a) Adds new (key, value) pairs based on a unique key
                 b) Updates any values changes to existing keys

        """

        merged_met_dict = {}

        if os.path.exists(self._met_file):
            with open(self._met_file) as json_file:
                file_met_dict = json.load(json_file)
                merged_met_dict = file_met_dict.copy()

        merged_met_dict.update(self.met_dict)

        with open(self._met_file, "w") as f:
            json.dump(merged_met_dict, f, indent=2, sort_keys=True)

    def read(self):
        """
        Reads, an existing catalog metadata file.
        Loads the JSON fields into the instance's met_dict

        """
        if os.path.exists(self._met_file):
            with open(self._met_file) as json_file:
                self.met_dict = json.load(json_file)

    def validate_json_file(self, json_filename: str, schema_filename: str) -> (bool, str):
        """
        Validates the specified json file against the specified jsonschema file.

        Parameters
        ----------
        json_filename: str
            JSON file to check against schema
        schema_filename: str
            JSON schema file

        Returns
        -------
        boolean
            1: pass
            0: fail

        """
        with open(schema_filename, 'tr') as schema_file:
            schema = json.load(schema_file)
        with open(json_filename, 'tr') as json_file:
            json_data = json.load(json_file)

        # Initialize and run the validator
        validator = jsonschema.validators.validator_for(schema)(schema)
        # record errors (if any)
        errors = validator.iter_errors(json_data)
        self.combined_error_msg = '\n'.join(error.message for error in errors)
        # success if combined_error_text is an empty string
        success = len(self.combined_error_msg) == 0
        return success

    def get_error_msg(self):
        """Returns the error message if a schema check is unsuccessful."""
        return self.combined_error_msg
