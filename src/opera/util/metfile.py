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


class MetFile:
    """Class read and write .met files."""

    def __init__(self, met_file_name, met_dict={}):
        """
        Constructor get filename and initialize dictionary

        Parameters
        ----------
        met_file_name : str, required
            Name of the file that will be written to or read.

        """

        self._met_file = met_file_name
        self.met_dict = met_dict
        self.combined_error_msg = None

    def set_key_value(self, key_name, val):
        """Simply sets a key value pair"""
        self.met_dict[key_name] = val

    def write_met_file(self):
        """Writes met file in JSON format to disk"""
        if os.path.exists(self._met_file):
            merged_met_dict = {}
            with open(self._met_file) as json_file:
                file_met_dict = json.load(json_file)
                merged_met_dict = file_met_dict.copy()
                merged_met_dict.update(self.met_dict)
            with open(self._met_file, "w") as f:
                json.dump(merged_met_dict, f, indent=2, sort_keys=True)
        else:
            with open(self._met_file, "w") as f:
                json.dump(self.met_dict, f, indent=2, sort_keys=True)

    def read_met_file(self):
        """Reads, returns an existing met file."""
        if os.path.exists(self._met_file):
            # Open JSON file
            with open(self._met_file) as json_file:
                self.met_dict = json.load(json_file)
            return self.met_dict

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
        if success:
            return True
        else:
            return False

    def get_error_msg(self):
        """Returns the error message if a schema check is unsuccessful."""
        return self.combined_error_msg
