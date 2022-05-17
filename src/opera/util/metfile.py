#!/usr/bin/env python3

"""
==========
metfile.py
==========

Creates .met file for the OPERA PGEs.

This module is adapted for OPERA from the NISAR PGE R2.0.0 util/metfile.py
Original Author: Alice Stanboli
Adapted By: Jim Hofman

"""

import json
import os

import jsonschema

from pkg_resources import resource_filename


class MetFile:
    """Class used to read and write .json catalog metadata files."""

    SCHEMA_PATH = resource_filename('opera', 'schema/catalog_metadata_schema.json')

    def __init__(self, met_dict=None):
        """
        Constructor get filename and initialize dictionary

        Parameters
        ----------
        met_dict : dict, optional
            Dictionary passed to be merged with existing catalog metadata
            file or to be used to make a new catalog metadata file

        """
        if met_dict is None:
            met_dict = {}

        self.met_dict = met_dict
        self.combined_error_msg = None

    def __setitem__(self, key_name, value):
        """Set as dictionary"""
        self.met_dict[key_name] = value

    def __getitem__(self, key_name):
        """Get as dictionary"""
        return self.met_dict[key_name]

    def asdict(self):
        """Return dictionary representation of catalog metadata"""
        return self.met_dict

    @classmethod
    def get_schema_file_path(cls):
        """Returns the path to schema file"""
        return cls.SCHEMA_PATH

    def write(self, output_path):
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

        if os.path.exists(output_path):
            with open(output_path, "r", encoding="utf-8") as json_file:
                file_met_dict = json.load(json_file)
                merged_met_dict = file_met_dict.copy()

        merged_met_dict.update(self.met_dict)

        with open(output_path, "w", encoding='utf-8') as outfile:
            json.dump(merged_met_dict, outfile, indent=2, sort_keys=True)

    def read(self, input_path):
        """
        Reads, an existing catalog metadata file.
        Loads the JSON fields into the instance's met_dict

        """
        with open(input_path, "r", encoding='utf-8') as json_file:
            self.met_dict = json.load(json_file)

    def validate(self, schema_filename: str) -> bool:
        """
        Validates the specified json file against the specified jsonschema file.

        Parameters
        ----------
        schema_filename: str
            JSON schema file

        Returns
        -------
        boolean
            1: pass
            0: fail

        """
        with open(schema_filename, "tr", encoding='utf-8') as schema_file:
            schema = json.load(schema_file)

        # Initialize and run the validator
        validator = jsonschema.validators.validator_for(schema)(schema)

        # record errors (if any)
        errors = validator.iter_errors(self.met_dict)
        self.combined_error_msg = '\n'.join(error.message for error in errors)

        # success if combined_error_text is an empty string
        success = len(self.combined_error_msg) == 0  # pylint: disable=compare-to-zero

        return success

    def get_error_msg(self):
        """Returns the error message if a schema check is unsuccessful."""
        return self.combined_error_msg
