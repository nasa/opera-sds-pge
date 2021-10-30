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
============
runconfig.py
============

Module for parsing and validating run configuration files for OPERA PGEs.

This module is adapted for OPERA from the NISAR PGE R2.0.0 util/l1_l2_runconfig.py
Original Author: David White
Adapted By: Scott Collins

"""
import os

import yaml

import yamale
from pkg_resources import resource_filename

BASE_PGE_SCHEMA = resource_filename('opera', 'schema/base_pge_schema.yaml')
"""Path to the Yamale schema applicable to the PGE portion of each RunConfig"""


class RunConfig:
    """
    Class used to parse and validate run configuration files for OPERA PGEs.

    RunConfig files are written in YAML, and contain distinct configuration
    sections for both the PGE and SAS executables. Schema-based validation is
    performed via the Yamale library (https://github.com/23andMe/Yamale).

    Attributes
    ----------
    _filename : str
        Name of the file parsed to create the RunConfig
    _run_config : dict
        Parsed contents of the provided RunConfig file
    _pge_config : dict
        Short-cut to the PGE-specific section of the parsed RunConfig
    _sas_config : dict
        Short-cut to the SAS-specific section of the parsed RunConfig

    """

    def __init__(self, filename):
        self._filename = filename

        self._run_config = self._parse_run_config_file(filename)
        self._pge_config = self._run_config['Groups']['PGE']
        # SAS section may not always be present, during testing for example
        self._sas_config = self._run_config['Groups'].get('SAS')

    @staticmethod
    def _parse_run_config_file(yaml_filename):
        """
        Loads a run configuration YAML file.
        Returns the loaded data as a Python object.

        Parameters
        ----------
        yaml_filename : str
            Path to the RunConfig YAML file to parse.

        Returns
        -------
        run_config : dict
            All contents of the parsed

        Raises
        ------
        RuntimeError
            If the parsed config does not define a top-level "RunConfig" entry

        """
        with open(yaml_filename, 'r') as stream:
            dictionary = yaml.safe_load(stream)

        try:
            return dictionary['RunConfig']

        except KeyError:
            raise RuntimeError(
                f'Unable to parse {yaml_filename}, expected top-level RunConfig entry'
            )

    def validate(self, pge_schema_file=BASE_PGE_SCHEMA, strict_mode=True):
        """
        Validates the RunConfig using a combination of the base PGE schema,
        and the specific SAS schema defined by the RunConfig itself.

        Parameters
        ----------
        pge_schema_file : str, optional
            The Yamale schema file for the PGE portion of the RunConfig.
            Defaults to the base PGE schema. Inheritors of RunConfig that
            overload this method may use this argument to provide their own
            tailored schema.
        strict_mode : bool, optional
            Toggle for Yamale validation strict mode. When enabled, unexpected
            elements not defined by the schema will raise validation errors.

        Raises
        ------
        RuntimeError
            If the SAS schema defined by the parsed RunConfig cannot be located.
        YamaleError
            If the RunConfig does not validate against the combined PGE/SAS
            schema.

        """
        # Load the schema for the PGE portion of the RunConfig, which should
        # be fixed across all PGE-SAS combinations
        pge_schema = yamale.make_schema(pge_schema_file)

        # If there was a SAS section included with the parsed config, pull
        # in its schema before validating. Otherwise, only the base PGE schema
        # will be used.
        if self.sas_config is not None:
            # Determine the SAS schema file to load from the provided RunConfig
            sas_schema_filename = self.sas_schema_path
            sas_schema_filepath = resource_filename('opera', f'schema/{sas_schema_filename}')

            if os.path.isfile(sas_schema_filepath):
                # TODO: better error handling for missing sas schema,
                #       support for absolute paths as fallback when resource_filename fails?
                sas_schema = yamale.make_schema(sas_schema_filepath)

                # Link the SAS schema to the PGE as an "include"
                # Note that the key name "sas_configuration" must match the include
                # reference in the base PGE schema.
                pge_schema.includes['sas_configuration'] = sas_schema
            else:
                raise RuntimeError(
                    f'Can not validate RunConfig {self.name} as the associated SAS '
                    f'schema ({sas_schema_filename}) cannot be located within the '
                    f'schemas directory.'
                )

        # Yamale expects its own formatting of the parsed config, hence the need
        # to call "make_data()" here.
        runconfig_data = yamale.make_data(self.filename)

        # Finally, validate the RunConfig against the combined PGE/SAS schema
        yamale.validate(pge_schema, runconfig_data, strict=strict_mode)

    def __getattribute__(self, item):
        """
        Wrapper function for all attribute access attempts on instances of
        RunConfig. Used to provide consistent error handling for when an
        expected file is missing from a RunConfig.

        Parameters
        ----------
        item : str
            Name of the attribute to be accessed.

        Returns
        -------
        attribute : object
            The accessed attribute.

        """
        try:
            return object.__getattribute__(self, item)
        except KeyError as error:
            # TODO: create exceptions package with more intuitive exception class names
            raise RuntimeError(
                f'Expected field "{str(error)}" is missing from RunConfig {self.filename}'
            )

    @property
    def filename(self) -> str:
        return self._filename

    @property
    def name(self) -> str:
        return self._run_config['Name']

    # PGENameGroup
    @property
    def pge_name(self) -> str:
        return self._pge_config['PGENameGroup']['PGEName']

    # InputFilesGroup
    @property
    def input_files(self) -> list:
        return self._pge_config['InputFilesGroup']['InputFilePaths']

    # DynamicAncillaryFilesGroup
    @property
    def ancillary_file_map(self) -> dict:
        return self._pge_config['DynamicAncillaryFilesGroup']['AncillaryFileMap']

    # ProductPathGroup
    @property
    def product_counter(self) -> int:
        return self._pge_config['ProductPathGroup']['ProductCounter']

    @property
    def output_product_path(self) -> str:
        return self._pge_config['ProductPathGroup']['OutputProductPath']

    @property
    def scratch_path(self) -> str:
        return self._pge_config['ProductPathGroup']['ScratchPath']

    @property
    def sas_output_file(self) -> str:
        return self._pge_config['ProductPathGroup']['SASOutputFile']

    # PrimaryExecutable
    @property
    def product_identifier(self) -> str:
        return self._pge_config['PrimaryExecutable']['ProductIdentifier']

    @property
    def sas_program_path(self) -> str:
        return self._pge_config['PrimaryExecutable']['ProgramPath']

    @property
    def sas_program_options(self) -> str:
        return self._pge_config['PrimaryExecutable']['ProgramOptions']

    @property
    def error_code_base(self) -> int:
        return self._pge_config['PrimaryExecutable']['ErrorCodeBase']

    @property
    def sas_schema_path(self) -> str:
        return self._pge_config['PrimaryExecutable']['SchemaPath']

    @property
    def iso_template_path(self) -> str:
        return self._pge_config['PrimaryExecutable']['IsoTemplatePath']

    # QAExecutable
    @property
    def qa_enabled(self) -> bool:
        return self._pge_config['QAExecutable']['Enabled']

    @property
    def qa_program_path(self) -> str:
        return self._pge_config['QAExecutable']['ProgramPath']

    @property
    def qa_program_options(self) -> str:
        return self._pge_config['QAExecutable']['ProgramOptions']

    @property
    def debug_switch(self) -> bool:
        return bool(self._pge_config['DebugLevelGroup']['DebugSwitch'])

    @property
    def sas_config(self) -> dict:
        return self._sas_config

    def get_ancillary_filenames(self):
        """
        Returns a list of all ancillary filenames listed in the
        DynamicAncillaryFilesGroup section of the run config file.
        The returned list only has the filenames, not the types of the files.

        Returns
        -------
        ancillary_filenames : list of str
            List of all ancillary filenames listed in the RunConfig under
            the DynamicAncillaryFilesGroup section.

        """
        result = list(
            filter(lambda filename: filename, self.ancillary_file_map.values())
        )

        return result
