#!/usr/bin/env python

"""
==============
test_logger.py
==============

Unit tests for the util/logger.py module.

"""
import os
import re
import tempfile
import unittest
from io import StringIO
from os.path import abspath, exists, join
from random import randint

from opera.test import path

from opera.util.error_codes import (CODES_PER_RANGE,
                                    CRITICAL_RANGE_START,
                                    DEBUG_RANGE_START,
                                    ErrorCode,
                                    INFO_RANGE_START,
                                    WARNING_RANGE_START)
from opera.util.logger import PgeLogger
from opera.util.logger import default_log_file_name
from opera.util.logger import get_severity_from_error_code
from opera.util.logger import standardize_severity_string
from opera.util.logger import write


class LoggerTestCase(unittest.TestCase):
    """Base test class using unittest"""

    data_dir = None
    starting_dir = None
    test_dir = None
    working_dir = None

    @classmethod
    def setUpClass(cls) -> None:
        """
        Set up directories for testing
        Initialize class variables
        Define regular expression used while checking log files
        Instantiate PgeLogger

        """
        cls.starting_dir = abspath(os.curdir)
        with path('opera.test', 'util') as test_dir_path:
            cls.test_dir = str(test_dir_path)
        cls.data_dir = join(cls.test_dir, os.pardir, "data")

        cls.config_file = join(cls.data_dir, "test_base_pge_config.yaml")
        cls.fn_regex = r'^pge_\d[0-9]{7}T\d{6}.log$'
        cls.iso_regex = r'^(-?(?:[0-9][0-9]*)?[0-9]{4})-(1[0-2]|0[1-9])-(3[01]|0[1-9]|[12][0-9])T(2[0-3]|[01][0-9]):' \
                        r'([0-5][0-9]):([0-5][0-9])(\.[0-9]+)?(Z)$'
        cls.monotonic_regex = r'^\d*.\d*$'
        cls.logger = PgeLogger()

        os.chdir(cls.test_dir)

    @classmethod
    def tearDownClass(cls) -> None:
        """At completion re-establish starting directory"""
        os.chdir(cls.starting_dir)

    def setUp(self) -> None:
        """Use the temporary directory as the working directory"""
        # Re-initialize a new logger for each test
        self.logger = PgeLogger()
        self.working_dir = tempfile.TemporaryDirectory(
            prefix="test_logger_", suffix='temp', dir=os.curdir)
        os.chdir(self.working_dir.name)

    def tearDown(self) -> None:
        """Return to test directory"""
        os.chdir(self.test_dir)
        self.working_dir.cleanup()

    def add_backframe(self, back_frames):
        """
        Makes a logs one line, then calls another method, that also logs one line

        Parameters
        ----------
        back_frames : int
            Starting number of back frames, typically this is one for a call like this.
            Allow zero to be entered to simulate not using the 'additional_back_frames'
            argument in the logging.

        """
        # This allows testing function calls with zero backframes
        inc = 0 if not back_frames else 1
        self.logger.log_one_metric(
            'test_logger.py', 'Test log_one_metric(): log from method call (back_frames = 0)',
            18, additional_back_frames=back_frames
        )
        self.one_deeper(back_frames + inc)

    def one_deeper(self, back_frames):
        """Logs a metric from a function call"""
        self.logger.log_one_metric(
            'test_logger.py', 'Test log_one_metric(): log called from 2 method calls (no bf)',
            19, additional_back_frames=back_frames
        )

    def test_write(self):
        """
        Write one line to a log file, read it back and verify things
        were written properly

        """
        match_iso_time = re.compile(self.iso_regex).match

        # initialize arguments for write() call
        severity = "Info"
        workflow = "test_workflow"
        module = "test_module"
        error_code = ErrorCode(0)
        error_location = 'test_file line 28'
        description = 'unittest write() function in logger.py utility'

        test_stream = StringIO("unittest of standalone write() function in logger.py utility")
        write(test_stream, severity, workflow, module, error_code, error_location, description)

        file_text = test_stream.getvalue()

        line_fields = file_text.split(',')

        # Test each field in the log line.
        self.assertEqual(line_fields[0], match_iso_time(line_fields[0]).group())
        self.assertEqual(line_fields[1].strip(), severity)
        self.assertEqual(line_fields[2].strip(), workflow)
        self.assertEqual(line_fields[3].strip(), module)
        # Python 3.11 (used by some SAS containers) changes the semantics of
        # string representation for an IntEnum, so cover both cases here
        self.assertIn(line_fields[4].strip(), ('0', 'ErrorCode.OVERALL_SUCCESS'))
        self.assertEqual(line_fields[5].strip(), error_location)
        self.assertEqual(line_fields[6].strip(), f'"{description}"')

    def test_default_log_file_name(self):
        """Test the formatted string that is returned by the default_log_file_name()"""
        file_name = default_log_file_name().split(os.sep)[-1]

        self.assertEqual(file_name, re.match(self.fn_regex, file_name).group())

    def test_get_severity_from_error_code(self):
        """
        Test get_severity_from_error_code(error_code)
        Only tests one per category
        Selection is made from a random integer within each individual range.
        """
        info_index = randint(INFO_RANGE_START, DEBUG_RANGE_START - 1)
        self.assertEqual(get_severity_from_error_code(info_index), "Info")
        debug_index = randint(DEBUG_RANGE_START, WARNING_RANGE_START - 1)
        self.assertEqual(get_severity_from_error_code(debug_index), "Debug")
        warning_index = randint(WARNING_RANGE_START, CRITICAL_RANGE_START - 1)
        self.assertEqual(get_severity_from_error_code(warning_index), "Warning")
        critical_index = randint(CRITICAL_RANGE_START, CRITICAL_RANGE_START + CODES_PER_RANGE)
        self.assertEqual(get_severity_from_error_code(critical_index), "Critical")

    def test_standardize_severity_string(self):
        """
        Test that the string returned has the first character capitalized and
        the rest are lower case
        """
        self.assertEqual(standardize_severity_string("info"), "Info")
        self.assertEqual(standardize_severity_string("DeBuG"), "Debug")
        self.assertEqual(standardize_severity_string("wARNING"), "Warning")
        self.assertEqual(standardize_severity_string("CrItIcAl"), "Critical")

    def test_pge_logger(self):
        """The PgeLogger class"""
        self.assertIsInstance(self.logger, PgeLogger)

        # Verify the default arguments that are assigned, and other initializations
        self.assertEqual(self.logger._workflow, "pge_init::logger.py")
        self.assertEqual(self.logger._error_code_base, 900000)

        # Verify, the log file name contains a datetime, verify the format of
        # the filename with the included datetime
        self.assertEqual(self.logger.log_filename,
                         re.match(self.fn_regex, self.logger.log_filename).group())
        self.assertEqual(str(self.logger.start_time),
                         re.match(self.monotonic_regex, str(self.logger.start_time)).group())

        # Check that an in-memory log was created
        stream = self.logger.get_stream_object()
        self.assertTrue(isinstance(stream, StringIO))

        # Check that the log file name was created
        log_file = self.logger.get_file_name()
        self.assertEqual(log_file, re.match(self.fn_regex, log_file).group())

        # Write a few log messages to the log file, verify case does not matter in 'type' field
        self.logger.write('info', "opera_pge", 0, 'test string with error code OVERALL_SUCCESS')
        self.logger.write('deBug', "opera_pge", 1, 'test string with error code LOG_FILE_CREATED')
        self.logger.write('Warning', "opera_pge", 2, 'test string with error code LOADING_RUN_CONFIG_FILE')
        self.logger.write('CriticaL', "opera_pge", 3, 'test string with error code VALIDATING_RUN_CONFIG_FILE')

        # Write messages at different levels with different methods
        self.logger.info('opera_pge', 4, 'Test info() method.')
        self.logger.debug('opera_pge', 5, 'Test debug() method.')
        self.logger.warning('opera_pge', 6, 'Test warning() method.')
        self.logger.log('opera_pge', 7, "Test log() method.")

        # Write a message into the log using log_one_metric() (although it is
        # used by write_log_summary() to record summary data at the end of the log file.)
        self.logger.log_one_metric('test_logger.py', 'Test log_one_metric()', 17, 1)
        self.logger.write_log_summary()

        # Get current dictionary
        pre_increment_dict = self.logger.get_log_count_by_severity('info')
        self.logger.increment_log_count_by_severity('info')
        self.assertNotEqual(pre_increment_dict, self.logger.get_log_count_by_severity('info'))

        pre_increment_dict = self.logger.get_log_count_by_severity('debug')
        self.logger.increment_log_count_by_severity('debug')
        self.assertNotEqual(pre_increment_dict, self.logger.get_log_count_by_severity('debug'))

        pre_increment_dict = self.logger.get_log_count_by_severity('warning')
        self.logger.increment_log_count_by_severity('warning')
        self.assertNotEqual(pre_increment_dict, self.logger.get_log_count_by_severity('warning'))

        # Test with backframes having being designated as before
        self.add_backframe(1)

        # Test with backframes not being designated
        self.add_backframe(0)

        # Test append text from another file
        test_append_file = tempfile.NamedTemporaryFile(prefix="new_file_", suffix='_txt', dir=os.curdir)
        with open(test_append_file.name, 'w', encoding='utf-8') as temp_file:
            temp_file.write(
                f'Text from "{test_append_file.name}" to test append_text_from another file().'
            )
        self.logger.append(test_append_file.name)

        self.logger.move('test_move.log')
        self.logger.log('opera_pge', 8, "Moving log file to: test_move.log")

        # Check log level counts match expected
        self.assertEqual(
            self.logger.log_count_by_severity,
            {'Debug': 3, 'Info': 22, 'Warning': 3, 'Critical': 1}
        )

        # Verify that when a critical event is logged via the critical() method, that a RunTimeError is raised
        self.assertRaises(RuntimeError, self.logger.critical, 'opera_pge', 8, "Test critical() method.")

        with open('test_move.log', 'r', encoding='utf-8') as file_handle:
            log = file_handle.read()

        # Verify that the entries have been made in the log
        self.assertIn('Moving log file to: ', log)
        self.assertIn('test string with error code OVERALL_SUCCESS', log)
        self.assertIn('test string with error code LOG_FILE_CREATED', log)
        self.assertIn('test string with error code LOADING_RUN_CONFIG_FILE', log)
        self.assertIn('test string with error code VALIDATING_RUN_CONFIG_FILE', log)
        self.assertIn('Test info() method.', log)
        self.assertIn('Test debug() method.', log)
        self.assertIn('Test warning() method.', log)
        self.assertIn('Test log() method.', log)
        look_for = f'Text from "{test_append_file.name}" to test append_text_from another file().'
        self.assertIn(look_for, log)
        self.assertIn('Test log_one_metric(): 17', log)

        # Check similar methods against each other
        self.assertEqual(self.logger.get_log_count_by_severity("warning"), self.logger.get_warning_count())
        self.assertEqual(self.logger.get_log_count_by_severity("critical"), self.logger.get_critical_count())

        # Verify that critical event was logged before the file was closed.
        self.assertIn('Test critical() method.', log)

        # Check that the severity dictionary is updating properly
        self.assertEqual(self.logger.log_count_by_severity, self.logger.get_log_count_by_severity_dict())

        # Instantiate a logger to test PgeLogger attributes and warning messages
        self.arg_test_logger = PgeLogger(workflow='test_pge_args', error_code_base=17171717,
                                         log_filename='test_args.log')

        # Add a new line
        self.arg_test_logger.log('opera_pge', 7, "Verify arguments in the file.")

        # Error Cases
        # Illegal category
        self.arg_test_logger.increment_log_count_by_severity("BROKEN")

        # Verify there are no entries with a category 'BROKEN'
        self.assertEqual(self.arg_test_logger.get_log_count_by_severity("BROKEN"), 0)

        self.arg_test_logger.close_log_stream()

        with open('test_args.log', 'r', encoding='utf-8') as file_handle:
            args_log = file_handle.read()

        # Verify warnings
        self.assertIn("Could not increment severity level: 'Broken' ", args_log)
        self.assertIn("No messages logged with severity: 'Broken' ", args_log)

        # Verify the log file was created
        self.assertTrue(exists('test_args.log'))

        # Verify workflow and error_code_base arguments
        with open('test_args.log', 'r', encoding='utf-8') as file_handle:
            for line in file_handle:
                self.assertIn("test_pge_args", line)
                self.assertIn("1717", line)

    def test_append_sas_log(self):
        """
        Test appending of a SAS-formatted log file to ensure contents are parsed
        and merged correctly with the PGE log
        """
        # Ensure we're starting with a clean log instance
        self.assertIsInstance(self.logger, PgeLogger)

        self.assertEqual(
            self.logger.log_count_by_severity,
            {'Debug': 0, 'Info': 0, 'Warning': 0, 'Critical': 0}
        )

        # Append contents of a sample SAS output log to the PGE logger
        sas_log_file = join(self.data_dir, "test_sas_log.txt")

        self.logger.append(sas_log_file)

        # Check that the severity count totals were updated as-expected
        self.assertEqual(
            self.logger.log_count_by_severity,
            {'Debug': 3, 'Info': 72, 'Warning': 2, 'Critical': 2}
        )

        # Check that each line appended to the PGE was formatted as expected
        self.logger.log_stream.seek(0)

        match_iso_time = re.compile(self.iso_regex).match

        for log_line in self.logger.log_stream.readlines():
            line_components = log_line.split(',', maxsplit=6)

            line_components = tuple(map(str.strip, line_components))

            (time_tag,
             severity,
             workflow,
             module,
             error_code,
             error_location,
             description) = line_components

            # Ensure an ISO format time tag was used
            self.assertIsNotNone(match_iso_time(time_tag))

            # Ensure description is double-quoted, but no double-quotes are used
            # again within the body of the text
            self.assertTrue(description.startswith('"'))
            self.assertTrue(description.endswith('"'))
            self.assertNotIn('"', description[1:-1])

            # Ensure severity string was standardized
            self.assertIn(severity, ["Info", "Warning", "Debug", "Critical"])

            # Ensure that the appropriate error code offsets were used
            error_code_map = {
                "Debug": ErrorCode.LOGGED_DEBUG_LINE,
                "Info": ErrorCode.LOGGED_INFO_LINE,
                "Warning": ErrorCode.LOGGED_WARNING_LINE,
                "Critical": ErrorCode.LOGGED_CRITICAL_LINE
            }

            self.assertEqual(self.logger.error_code_base,
                             int(error_code) - error_code_map[severity])


if __name__ == "__main__":
    unittest.main()
