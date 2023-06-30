#!/usr/bin/env python3


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
from os.path import abspath, basename, isabs, isdir, isfile, join

from pkg_resources import resource_filename

import yamale

import yaml


BASE_PGE_SCHEMA = resource_filename('opera', 'pge/base/schema/base_pge_schema.yaml')
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


        Raises
        ------
        RuntimeError
            If the parsed config does not define a top-level "RunConfig" entry

        """
        with open(yaml_filename, 'r', encoding='utf-8') as stream:
            dictionary = yaml.safe_load(stream)

        try:
            return dictionary['RunConfig']
        except KeyError as key_error:
            raise RuntimeError(
                f'Unable to parse {yaml_filename}, expected top-level RunConfig entry'
            ) from key_error

    @staticmethod
    def _parse_algorithm_parameters_run_config_file(yaml_filename):
        """
        Loads an algorithm parameter run configuration YAML file.
        Returns the loaded data as a Python object.

        Parameters
        ----------
        yaml_filename : str
            Path to the runconfig YAML file to parse.


        Raises
        ------
        RuntimeError
            If the parsed config does not define dictionary.

        """
        with open(yaml_filename, 'r', encoding='utf-8') as stream:
            dictionary = yaml.safe_load(stream)

        if dictionary:
            if 'runconfig' in dictionary:
                return dictionary['runconfig']
            else:
                return dictionary
        else:
            raise RuntimeError(f'Unable to parse {yaml_filename}')

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
            sas_schema_filepath = self.sas_schema_path

            if isfile(sas_schema_filepath):
                sas_schema = yamale.make_schema(sas_schema_filepath)

                # Link the SAS schema to the PGE as an "include"
                # Note that the key name "sas_configuration" must match the include statement
                # reference in the base PGE schema.
                pge_schema.includes['sas_configuration'] = sas_schema
            else:
                raise RuntimeError(
                    f'Can not validate RunConfig {self.name}, as the associated SAS '
                    f'schema ({sas_schema_filepath}) cannot be located.'
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

        Raises
        ------
        RuntimeError
            If the attribute requests fails (from missing field in RunConfig).

        """
        try:
            return object.__getattribute__(self, item)
        except KeyError as error:
            # TODO: create exceptions package with more intuitive exception class names
            raise RuntimeError(
                f'Expected field {str(error)} is missing from RunConfig '
                f'{abspath(self.filename)}'
            ) from error

    @property
    def filename(self) -> str:
        """Returns the of the file parsed to create the RunConfig"""
        return self._filename

    @property
    def name(self) -> str:
        """Returns the name of the RunConfig file"""
        return self._run_config['Name']

    # PGENameGroup
    @property
    def pge_name(self) -> str:
        """Returns the PGE Name from the PGE Name Group"""
        return self._pge_config['PGENameGroup']['PGEName']

    # InputFilesGroup
    @property
    def input_files(self) -> list:
        """Returns the path from the Input Files Group"""
        return self._pge_config['InputFilesGroup']['InputFilePaths']

    # DynamicAncillaryFilesGroup
    @property
    def ancillary_file_map(self) -> dict:
        """Returns the Ancillary File Map from the Dynamic Ancillary Files Group"""
        return self._pge_config['DynamicAncillaryFilesGroup']['AncillaryFileMap']

    # ProductPathGroup
    @property
    def output_product_path(self) -> str:
        """Returns the Output Product Path from the Product Path Group"""
        return self._pge_config['ProductPathGroup']['OutputProductPath']

    @property
    def scratch_path(self) -> str:
        """Returns the Scratch Path from the Product Path Group"""
        return self._pge_config['ProductPathGroup']['ScratchPath']

    # PrimaryExecutable
    @property
    def product_identifier(self) -> str:
        """Returns the Product Identifier from the Primary Executable Category"""
        return self._pge_config['PrimaryExecutable']['ProductIdentifier']

    @property
    def product_version(self) -> str:
        """Returns the Product Version from the Primary Executable Category"""
        return self._pge_config['PrimaryExecutable']['ProductVersion']

    @property
    def composite_release_id(self) -> str:
        """Returns the Composite Release ID (CRID) from the Primary Executable Category"""
        return self._pge_config['PrimaryExecutable']['CompositeReleaseID']

    @property
    def sas_program_path(self) -> str:
        """Returns the Program Path from a Primary Executable Category"""
        return self._pge_config['PrimaryExecutable']['ProgramPath']

    @property
    def sas_program_options(self) -> str:
        """Returns the Program Options (arguments) to a Primary Executable"""
        return self._pge_config['PrimaryExecutable']['ProgramOptions']

    @property
    def error_code_base(self) -> int:
        """Returns the Error Code Base for a particular Primary Executable"""
        return self._pge_config['PrimaryExecutable']['ErrorCodeBase']

    @property
    def sas_schema_path(self) -> str:
        """Returns the path to the Schema file for a Primary Executable"""
        sas_schema_path = self._pge_config['PrimaryExecutable']['SchemaPath']
        return (
            sas_schema_path
            if isabs(sas_schema_path)
            else resource_filename('opera', sas_schema_path)
        )

    @property
    def algorithm_parameters_schema_path(self) -> str:
        """Returns the path to the optional algorithm parameter Schema file for DSWX-S1"""
        algorithm_parameters_schema_path = self._pge_config['PrimaryExecutable']['AlgorithmParametersSchemaPath']
        if algorithm_parameters_schema_path is None:
            return None
        else:
            return (
                algorithm_parameters_schema_path
                if isabs(algorithm_parameters_schema_path)
                else resource_filename('opera', algorithm_parameters_schema_path)
            )

    @property
    def algorithm_parameters_file_config_path(self) -> str:
        """Returns the path to the algorithm parameters run configuration file"""
        dynamic_ancillary_file_group = self._sas_config['dynamic_ancillary_file_group']

        # ADT is inconsistent with how they define this location across different SAS,
        # so check all known permutations
        try:
            algorithm_parameters_file_config_path = dynamic_ancillary_file_group['algorithm_parameters_file']
        except KeyError:
            try:
                algorithm_parameters_file_config_path = dynamic_ancillary_file_group['algorithm_parameters']
            except KeyError:
                return None

        return (
            algorithm_parameters_file_config_path
            if isabs(algorithm_parameters_file_config_path)
            else resource_filename('opera', algorithm_parameters_file_config_path)
        )

    @property
    def iso_template_path(self) -> str:
        """Returns the ISO Template Path for a Primary Executable"""
        iso_template_path = self._pge_config['PrimaryExecutable']['IsoTemplatePath']
        return (
            iso_template_path
            if isabs(iso_template_path)
            else resource_filename('opera', iso_template_path)
        )

    @property
    def data_validity_start_time(self) -> str:
        """Returns the DataValidityStartTime value for the Primary Executable"""
        return self._pge_config['PrimaryExecutable'].get('DataValidityStartTime', None)

    # QAExecutable
    @property
    def qa_enabled(self) -> bool:
        """Returns a boolean indicating the state of QAExecutable: enabled/disabled"""
        return bool(self._pge_config['QAExecutable']['Enabled'])

    @property
    def qa_program_path(self) -> str:
        """Return the path to a QA Executable"""
        return self._pge_config['QAExecutable']['ProgramPath']

    @property
    def qa_program_options(self) -> str:
        """Return program options (arguments) for an executable command"""
        return self._pge_config['QAExecutable']['ProgramOptions']

    @property
    def debug_switch(self) -> bool:
        """Returns a boolean indicating the debugging state: enabled/disabled."""
        return bool(self._pge_config['DebugLevelGroup']['DebugSwitch'])

    @property
    def execute_via_shell(self) -> bool:
        """Returns a boolean indicating the state of ExecuteViaShell: enabled/disabled"""
        return bool(self._pge_config['DebugLevelGroup'].get('ExecuteViaShell', False))

    @property
    def sas_config(self) -> dict:
        """Returns the short-cut to the SAS-specific section of the parsed RunConfig"""
        return self._sas_config

    def asdict(self) -> dict:
        """Returns the entire parsed RunConfig in its dictonary representation"""
        return self._run_config

    def get_input_filenames(self):
        """
        Iterates over the input_file list from the runconfig and returns a list
        of all files.

        Files in the list are immediately included in the returned list.

        Directories in the list will be examined and any files found will be
        added to the list.

        Returns
        -------
        input_file : list of str
            The expanded list of input files determined from the RunConfig
            setting. The list is sorted prior to being returned.

        Raises
        ------
        OSError
            If anything that is not a file or directory is encountered while
            traversing the set of input file locations.

        """
        preliminary_file_list = self.input_files

        input_files = []

        def __is_input_file(filename):
            """Helper function for filtering out directories and hidden files"""
            return isfile(filename) and not basename(filename).startswith('.')

        for item in preliminary_file_list:
            if __is_input_file(item):
                input_files.append(item)
            elif isdir(item):
                for dir_item in os.listdir(item):
                    path = join(item, dir_item)

                    # for now only look for files at first level
                    if __is_input_file(path):
                        input_files.append(path)

        input_files.sort()

        return input_files

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
        result = list(self.ancillary_file_map.values())

        return result

    def get_output_product_filenames(self):
        """
        Returns a sorted list of all product file paths currently written to the
        output location specified by the RunConfig.

        Any hidden files (starting with ".") are ignored, as well as any files
        within the designated "scratch" path (if it happens to be defined within
        the output product directory).

        """
        output_product_path = abspath(self.output_product_path)
        scratch_path = abspath(self.scratch_path)

        output_products = []

        for dirpath, dirnames, filenames in os.walk(output_product_path, topdown=False):
            for filename in filter(lambda name: not name.startswith('.'), filenames):
                product_path = os.path.join(dirpath, filename)

                if scratch_path not in product_path:
                    output_products.append(product_path)

        return sorted(output_products)
