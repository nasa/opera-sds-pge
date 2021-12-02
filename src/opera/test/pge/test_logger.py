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
test_logger.py
=================

Unit tests for the util/logger.py module.
"""
import os
import tempfile
import unittest
import re
from os.path import abspath, join
from pkg_resources import resource_filename
from io import StringIO
import weakref

from opera.util.error_codes import ErrorCode
from opera.util.logger import write
from opera.util.logger import default_log_file_name
from opera.util.logger import get_severity_from_error_code
from opera.util.logger import standardize_severity_string

from opera.util.logger import PgeLogger


def clean_up(*args):
    """
    It is necessary for the weakref.finalize() method to call this for garbage collection
    The __del__ function in the logger causes an error because the code prematurely finalizes.
    The error is seen when a file is opened and the 'open' keyword is not recognized.
    This is a know problem with the logger module, and our logger causes the same problem.
    The print statement is temporary, and will be replaced with 'pass'.

    Parameters
    ----------
    args - objects with object to garbage collect (probably will only need to garbage collect the PGELogger object.

    """
    print('Cleaning up: ', args)


class LoggerTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.starting_dir = abspath(os.curdir)
        cls.test_dir = resource_filename(__name__, "")
        cls.data_dir = join(cls.test_dir, "data")

        os.chdir(cls.test_dir)

        cls.working_dir = tempfile.TemporaryDirectory(
            prefix="test_usage_metrics_", suffix='temp', dir=os.curdir)
        cls.config_file = join(cls.data_dir, "test_base_pge_config.yaml")
        cls.fn_regex = '^pge_\d[0-9]{7}T\d{6}.log$'
        cls.iso_regex = r'^(-?(?:[0-9][0-9]*)?[0-9]{4})-(1[0-2]|0[1-9])-(3[01]|0[1-9]|[12][0-9])T(2[0-3]|[01][0-9]):' \
                    r''r'([0-5][0-9]):([0-5][0-9])(\.[0-9]+)?(Z)$'
        cls.monotonic_regex = '^\d*.\d*$'
        cls.reps = 1
        cls.severity_summary_pre_resync = {'Debug': 2, 'Info': 7, 'Warning': 2, 'Critical': 1}
        cls.severity_summary_resync = {'Debug': 0, 'Info': 0, 'Warning': 0, 'Critical': 0}
        cls.severity_summary_post_resync = {'Debug': 1, 'Info': 30, 'Warning': 1, 'Critical': 1}
        cls.logger = PgeLogger()

    @classmethod
    def tearDownClass(cls) -> None:
        # cls.working_dir.cleanup()
        os.chdir(cls.starting_dir)
        weakref.finalize(cls.logger, clean_up)

    def setUp(self) -> None:
        # os.chdir(self.working_dir.name)
        print(self.severity_summary_pre_resync)
        print(self.severity_summary_post_resync)
        pass

    def tearDown(self) -> None:
        os.chdir(self.test_dir)

    def test_write(self):
        """
        Low-level logging function. May be called directly in lieu of PgeLogger class.

        Write one line to a log file, read it back and verify things were written properly

        """

        match_iso_time = re.compile(self.iso_regex).match

        # set up test arguments for write() call
        severity = "Info"
        workflow = "test_workflow"
        module = "test_module"
        error_code = ErrorCode(0)
        error_location = 'test_file line 28'
        description = 'unittest write() function in logger.py utility'

        # with open("test_write.log", "w") as log_file:
        #     write(log_file, severity, workflow, module, error_code, error_location, description)
        #
        # with open("test_write.log", "r") as file:
        #     file_text = file.read()

        test_stream = StringIO("unittest of write() function in logger.py utility")
        write(test_stream, severity, workflow, module, error_code, error_location, description)

        file_text = test_stream.getvalue()

        line_fields = file_text.split(',')

        # Test each field in the log line.
        self.assertEqual(line_fields[0], match_iso_time(line_fields[0]).group())
        self.assertEqual(line_fields[1].strip(), severity)
        self.assertEqual(line_fields[2].strip(), workflow)
        self.assertEqual(line_fields[3].strip(), module)
        self.assertEqual(line_fields[4].strip(), 'ErrorCode.OVERALL_SUCCESS')
        self.assertEqual(line_fields[5].strip(), error_location)
        self.assertEqual(line_fields[6].strip(), '"' + description + '"')

    def test_default_log_file_name(self):
        """
        Test the formatted string that is returned by the default_log_file_name()

        """
        file_name = default_log_file_name().split(os.sep)[-1]

        self.assertEqual(file_name, re.match(self.fn_regex, file_name).group())

    def test_get_severity_from_error_code(self):
        """
        Test get_severity_from_error_code(error_code)

        """

        for i in range(999):
            self.assertEqual(get_severity_from_error_code(i), "Info")
        for i in range(1000, 1999):
            self.assertEqual(get_severity_from_error_code(i), "Debug")
        for i in range(2000, 2999):
            self.assertEqual(get_severity_from_error_code(i), "Warning")
        for i in range(3000, 3999):
            self.assertEqual(get_severity_from_error_code(i), "Critical")

    def test_standardize_severity_string(self):
        """
        Test that the string returned has the first character capitalized and the rest are lower case
        -------

        """
        self.assertEqual(standardize_severity_string("info"),  "Info")
        self.assertEqual(standardize_severity_string("DeBuG"), "Debug")
        self.assertEqual(standardize_severity_string("wARNING"), "Warning")
        self.assertEqual(standardize_severity_string("CrItIcAl"), "Critical")

    def test_pge_logger(self):
        """
        The the PgeLogger class.

        """
        # Instantiate with default arguments
        # self.logger = PgeLogger()

        self.assertIsInstance(self.logger, PgeLogger)

        # Check that default arguments that are assigned and other initializations
        self.assertEqual(self.logger._workflow, "pge_init::logger.py")
        self.assertEqual(self.logger._error_code_base, 900000)
        # The log file name contains a datetime so checks the format of the filename with the included datetime
        self.assertEqual(self.logger.log_filename, re.match(self.fn_regex, self.logger.log_filename).group())
        self.assertEqual(str(self.logger.start_time), re.match(self.monotonic_regex, str(self.logger.start_time)).group())

        # Check the function call to return the newly initialized dictionary
        self.assertEqual(self.logger.log_count_by_severity, self.logger.get_log_count_by_severity_dict())
        self.assertEqual(self.logger.log_count_by_severity, {'Debug': 0, 'Info': 3, 'Warning': 0, 'Critical': 0})
        # Check that the log file was created
        log_file = self.logger.get_file_name()
        self.assertEqual(log_file, re.match(self.fn_regex, log_file).group())
        # write a few log messages to the log file
        self.logger.write('info', "opera_pge", 0, 'test string with error code OVERALL_SUCCESS')
        self.logger.write('deBug', "opera_pge", 1, 'test string with error code LOG_FILE_CREATED')
        self.logger.write('Warning', "opera_pge", 2, 'test string with error code LOADING_RUN_CONFIG_FILE')
        self.logger.write('CriticaL', "opera_pge", 3, 'test string with error code VALIDATING_RUN_CONFIG_FILE')
        # write messages at different levels with different methods
        self.logger.info('opera_pge', 4, 'Test info() method.')
        self.logger.debug('opera_pge', 5, 'Test debug() method.')
        self.logger.warning('opera_pge', 6, 'Test warning() method.')
        self.logger.log('opera_pge', 7, "Test log() method.")
        # write a message into the log using log_one_metric() (although it is used by write_log_summary() to
        # ... record summary data at the end of the log file.)
        self.logger.log_one_metric('test_logger.py', 'Test log_one_metric()', 17, 1)
        # Update log_count_by_severity dict to summarize the number of the various errors
        # TODO: talk to Scott about removing this method
        self.assertEqual(self.logger.log_count_by_severity, self.severity_summary_pre_resync)

        self.logger.resync_log_count_by_severity()
        self.assertEqual(self.logger.log_count_by_severity, self.severity_summary_resync)

        self.logger.write_log_summary()
        # get current dictionary
        pre_increment_dict = self.logger.get_log_count_by_severity('info')
        self.logger.increment_log_count_by_severity('info')
        self.assertNotEqual(pre_increment_dict, self.logger.get_log_count_by_severity('info'))

        pre_increment_dict = self.logger.get_log_count_by_severity('debug')
        self.logger.increment_log_count_by_severity('debug')
        self.assertNotEqual(pre_increment_dict, self.logger.get_log_count_by_severity('debug'))

        pre_increment_dict = self.logger.get_log_count_by_severity('warning')
        self.logger.increment_log_count_by_severity('warning')
        # Verify the counts no longer match
        self.assertNotEqual(pre_increment_dict, self.logger.get_log_count_by_severity('warning'))

        # TODO check with Scott about getting rid of the backframe stuff
        self.test_add_backframe()

        # Test append text from another file
        with open('new_file.txt', 'w') as temp_file:
            temp_file.write('Text from "new_file.txt" to test append_text_from another file().')
        self.logger.append_text_from_another_file('new_file.txt')

        self.logger.move('test_move.log')

        # Verify that when a critical event is logged via the critical() method, that a RunTimeError is raised
        self.assertRaises(RuntimeError, self.logger.critical, 'opera_pge', 8, "Test critical() method.")

        with open('test_move.log', 'r') as fn:
            log = fn.read()

        # Verify that the entries have been made in the log
        self.assertIn('Moving and saving log file', log)
        self.assertIn('test string with error code OVERALL_SUCCESS', log)
        self.assertIn('test string with error code LOG_FILE_CREATED', log)
        self.assertIn('test string with error code LOADING_RUN_CONFIG_FILE', log)
        self.assertIn('test string with error code VALIDATING_RUN_CONFIG_FILE', log)
        self.assertIn('Test info() method.', log)
        self.assertIn('Test debug() method.', log)
        self.assertIn('Test warning() method.', log)
        self.assertIn('Test log() method.', log)
        self.assertIn('Text from "new_file.txt" to test append_text_from another file()', log)
        self.assertIn('Test log_one_metric(): 17', log)

        # Check similar methods against each other
        self.assertEqual(self.logger.get_log_count_by_severity("warning"), self.logger.get_warning_count())
        self.assertEqual(self.logger.get_log_count_by_severity("critical"), self.logger.get_critical_count())

        # Check that the severity dictionary is updating properly
        self.assertEqual(self.logger.log_count_by_severity, self.logger.get_log_count_by_severity_dict())

        # Verify that critical event was logged before the file was closed.
        self.assertIn('Test critical() method.', log)
        # Verify critical() method close the log file.
        self.assertIn('Closing log file ', log)
        # 2nd test to Verify critical() method closed the log file.  (ValueError: I/O operations on closed file.)
        self.assertRaises(ValueError, self.logger.move, 'test_move_new.log')

        self.assertEqual(self.logger.log_count_by_severity, self.severity_summary_post_resync)

        # Instantiate a logger to test PgeLogger attributes
        self.arg_test_logger = PgeLogger(workflow='test_pge', error_code_base=100000,
                                         log_filename='test_move.log', append=True)

        self.arg_test_logger.log('opera_pge', 17, "Testing adding to a log file.")

    def test_add_backframe(self):
        self.logger.log_one_metric('test_logger.py', 'Test log_one_metric(): log from method call (back_frames = 0)',
                                   18, additional_back_frames=0)
        self.test_one_deeper()

    def test_one_deeper(self):
        self.logger.log_one_metric('test_logger.py', 'Test log_one_metric(): log called from 2 method calls (no bf)',
                                   19, additional_back_frames=0)

#     def cleanup(self):
#         os.remove('./new_file.txt')
#         os.remove('./test_move.log')


if __name__ == "__main__":
    unittest.main()
