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
import argparse
import json
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
                print(f' {self._met_file}: {str(self.met_dict)}')
            return self.met_dict


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    # Add arguments to parser
    parser.add_argument('--file', required=True)

    # Get command line arguments
    args = vars(parser.parse_args())

    # Get file names (required)
    met_file = args['file']

    met_data = MetFile(met_file)
    met_data.set_key_value("test key", "test value")
    met_data.write_met_file()
    met_data.read_met_file()
    met_data.set_key_value("test key 2", "test value 2")
    met_data.write_met_file()
    met_data.read_met_file()


if __name__ == "__main__":
    main()
