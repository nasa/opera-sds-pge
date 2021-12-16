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
test_run_utils.py
=================

Unit tests for the util/run_utils.py module.

"""
import os
import tempfile
import unittest
from os.path import abspath, basename, exists, join, splitext

from pkg_resources import resource_filename

import yaml

from opera.pge.runconfig import RunConfig
from opera.util.error_codes import ErrorCode
from opera.util.logger import PgeLogger
from opera.util.run_utils import create_sas_command_line
from opera.util.run_utils import time_and_execute


class RunUtilsTestCase(unittest.TestCase):
    """Base test class using unittest"""

    starting_dir = None
    working_dir = None
    config_file = None
    data_dir = None
    test_dir = None

    @classmethod
    def setUpClass(cls) -> None:
        """
        Set up class variables:
        Initialize the number of times to exercise the module (currently 1000)

        """
        cls.starting_dir = abspath(os.curdir)
        cls.test_dir = resource_filename(__name__, "")
        cls.data_dir = join(cls.test_dir, "data")

        os.chdir(cls.test_dir)

        cls.working_dir = tempfile.TemporaryDirectory(
            prefix="test_run_utils_", suffix='temp', dir=os.curdir)
        cls.config_file = join(cls.data_dir, "test_run_utils_config.yaml")
        cls.first_time = 0.0
        cls.second_time = 0.0
        cls.logger = PgeLogger()
        cls.run_config = RunConfig(cls.config_file)

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

    def _isolate_sas_runconfig(self):
        """
        Isolates the SAS-specific portion of the RunConfig into its own
        YAML file, so it may be fed into the SAS executable without unneeded
        PGE configuration settings.  (Note) This is copied from base_pge.py
        and modified slightly.

        """
        sas_config = self.run_config.sas_config

        pge_runconfig_filename = basename(self.run_config.filename)
        pge_runconfig_fileparts = splitext(pge_runconfig_filename)

        sas_runconfig_filename = f'{pge_runconfig_fileparts[0]}_sas{pge_runconfig_fileparts[1]}'
        # Working in a temporary directory; adjust path to access files
        dir_tweak = '/base_pge_test/scratch/'
        sas_runconfig_filepath = join(os.path.dirname(os.getcwd()) + dir_tweak, sas_runconfig_filename)

        if not exists(sas_runconfig_filepath):
            try:
                with open(sas_runconfig_filepath, 'w') as outfile:
                    yaml.safe_dump(sas_config, outfile, sort_keys=False)
            except OSError as err:
                self.logger.critical("test_run_utils", ErrorCode.SAS_CONFIG_CREATION_FAILED,
                                     f'Failed to create SAS config file {sas_runconfig_filepath}, '
                                     f'reason: {str(err)}')

        self.logger.info("test_run_utils", ErrorCode.CREATED_SAS_CONFIG,
                         f'SAS RunConfig created at {sas_runconfig_filepath}')

        return sas_runconfig_filepath

    def test_create_sas_command_line(self):
        """
        This test creates a simple linux command:
            /bin/echo Hello from test_create_command_line function.

        It uses create_sas_command_line() to make the function then
        it then uses time_and_execute() to execute the command.
        It records the elapsed time and writes it to the log file

        """
        # Make a command from something locally available
        self.logger.info('test', 1, 'Testing create_sas_command_line().')
        cmd = '/bin/echo'
        command = create_sas_command_line(cmd, self.config_file,
                                          sas_program_options=['Hello from test_create_command_line function.'])
        self.first_time = time_and_execute(command, self.logger, execute_via_shell=False)
        self.logger.info('test', 1, f'First elapsed time: {self.first_time}.')

    def test_time_and_execute(self):
        """
        This is first tested in test_create_sas_command_line().
        This test generates a command that is derived from a .yaml
        configuration file.  The command is created by
        create_sas_command_line(), then executed. It calls
        check_results() to examine the log file.

        """
        self.logger.info('test', 1, 'Testing test_time_and_execute().')
        sas_program_path = self.run_config.sas_program_path
        sas_program_options = self.run_config.sas_program_options
        sas_runconfig_filepath = self._isolate_sas_runconfig()

        command_line = create_sas_command_line(sas_program_path, sas_runconfig_filepath, sas_program_options)

        # Execute the command
        self.second_time = time_and_execute(command_line, self.logger, execute_via_shell=False)
        self.logger.info('test', 1, f'Second elapsed time: {self.second_time}.')

        self.check_results()

    def check_results(self):
        """
        Save the log stream to a file, then examine the file for
        expected values.

        """
        self.logger.close_log_stream()
        log_file = self.logger.get_file_name()
        self.assertTrue(os.path.exists(log_file))
        # Open the log file, and check for specific messages
        with open(log_file, 'r') as infile:
            log = infile.read()

        self.assertIn('Testing create_sas_command_line().', log)
        self.assertIn('Hello from test_create_command_line function.', log)
        self.assertIn(f'First elapsed time: {self.first_time}', log)

        self.assertIn('Testing test_time_and_execute().', log)
        self.assertIn('Hello from run_utils unit test, testing time_and_execute().', log)
        self.assertIn(f'Second elapsed time: {self.second_time}', log)
