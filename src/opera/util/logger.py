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
=========
logger.py
=========

Logging utilities for use with OPERA PGEs.

This module is adapted for OPERA from the NISAR PGE R2.0.0 util/logger.py
Original Authors: Alice Stanboli, David White
Adapted By: Scott Collins

"""

import csv
import datetime
import inspect
import shutil
import time
from io import StringIO

from os.path import basename
from sys import is_finalizing

import opera.util.error_codes as error_codes
import opera.util.time as time_util

from .error_codes import ErrorCode
from .usage_metrics import get_os_metrics


def write(log_stream, severity, workflow, module, error_code, error_location,
          description):
    """
    Low-level logging function. May be called directly in lieu of PgeLogger class.

    Parameters
    ----------
    log_stream : io.StringIO
        The log stream to write to.
    severity : str
        The severity level of the log message.
    workflow : str
        Name of the workflow where the logging took place.
    module : str
        Name of the module where the logging took place.
    error_code : int or ErrorCode
        The error code associated with the logged message.
    error_location : str
        File name and line number where the logging took place.
    description : str
        Description of the logged event.

    """
    time_tag = time_util.get_current_iso_time()

    # TODO: rework into a string constant that this function calls .format on
    message_str = time_tag + ", " + severity + ", " + workflow + ", " + module + ", " + \
        str(error_code) + ", " + error_location + ", " + '"' + description + '"' + "\n"

    # print(message_str)

    log_stream.write(message_str)

    return 0


# TODO - this can probably go away after we get the in-memory file object
def default_log_file_name():
    """
    Returns a path + filename that can be used for the log file right away.

    To minimize the risk of errors opening a log file, the initial log filename
    does not rely on anything read from a run config file, SAS output file, etc.
    Therefore this filename does not follow the file naming convention.

    Later (elsewhere), after everything is known, the log file will be renamed.

    Returns
    -------
    file_path : str
        Path to the default log file name.

    """
    log_datetime_str = time_util.get_time_for_filename(datetime.datetime.now())
    file_path = "pge_{}.log".format(log_datetime_str)

    return file_path


def get_severity_from_error_code(error_code):
    """
    Determines the log level (Critical, Warning, Info, or Debug) based on the
    provided error code.

    Parameters
    ----------
    error_code : int or ErrorCode
        The error code to map to a severity level.

    Returns
    -------
    severity : str
        The severity level associated to the provided error code.

    """
    # TODO: constants for max codes and severity strings
    error_code_offset = error_code % 10000

    if error_code_offset < error_codes.DEBUG_RANGE_START:
        return "Info"

    if error_code_offset < error_codes.WARNING_RANGE_START:
        return "Debug"

    if error_code_offset < error_codes.CRITICAL_RANGE_START:
        return "Warning"

    return "Critical"


def standardize_severity_string(severity):
    """
    Returns the severity string in a consistent way.

    Parameters
    ----------
    severity : str
        The severity string to standardize.

    Returns
    -------
    severity : str
        The standardized severity string.

    """
    return severity.title()  # first char uppercase, rest lowercase.


def test_save():
    with open('text.txt', 'w') as fd:
        fd.write("hello")


class PgeLogger:
    """
    Class to help with the PGE logging.

    Advantages over the standalone write() function:
    * Opens and closes the log file for you
    * The class's write() function has fewer arguments that need to be provided.

    """
    LOGGER_CODE_BASE = 900000

    def __init__(self, workflow=None, error_code_base=None,
                 log_filename=None, existing_logfile_object=None, append=False):
        """
        Constructor opens the log file unless an existing_logfile_object is
        specified

        Parameters
        ----------
        workflow : str, optional
            Name of the workflow this logger is associated to. Defaults
            to "pge".
        error_code_base : int, optional
            The base error code value to associated to the logger. This gives
            the logger a de-facto severity level. Defaults to the Info level
            offset.
        log_filename : str, optional
            Path to write the log's contents to on disk. Ignored if
            existing_logfile_object is provided. Defaults to the value
            provided by default_log_file_name().
        existing_logfile_object : file-like, optional
            An existing open file-like object to write logged messages to.
        append : bool, optional
            If true, messages logged by this object are appended to the associated
            log file. Otherwise, a new file is created.

        """
        self.start_time = time.monotonic()
        self.log_count_by_severity = self._make_blank_log_count_by_severity_dict()
        self.log_filename = log_filename

        # TODO: consolidate existing_logfile_object and log_filename into a single arg
        # Idea: get rid of this argument and if append is 'True' assume it's an existing_log_file_object
        if existing_logfile_object:
            self.log_file = existing_logfile_object
        else:
            if not log_filename:
                self.log_filename = default_log_file_name()

            if append:
                # Get existing file and write it into a stream to be kept in memory
                self.log_stream = self.file_to_stream(log_filename)

            else:
                # open as an empty stream that will be kept in memory
                self.log_stream = StringIO()
                self.log_stream.seek(0)
                print("TYPE: ", type(self.log_stream))

        self._workflow = (workflow
                          if workflow else f"pge_init::{basename(__file__)}")

        self._error_code_base = (error_code_base
                                 if error_code_base else PgeLogger.LOGGER_CODE_BASE)

    # def __del__(self):
    #     """
    #     Destructor for PgeLogger.
    #
    #     Ensures the internally managed log file is properly closed before this
    #     object is garbage collected.
    #
    #     """
    #     if self.log_stream and not self.log_stream.closed:
    #         self.close_log_stream()

    def file_to_stream(self, log_file):
        """
        Takes a log file as an input and reads it into a log stream

        Parameters
        ----------
        log_file - log file read from disk

        Returns
        -------
        TextIOWrapper object that contains the log file data.

        """
        # Read contents of log file into a log stream
        print("TYPE - log_file: ", type(log_file))
        print(log_file)
        with open(log_file, 'r') as fd:
            log = fd.read()
            log_stream = StringIO(log)
            return log_stream

    def stream_to_file(self, log_stream, log_file_name):
        """
        Writes log file in memory to a log file on disk
        Parameters
        ----------
        log_stream
        log_file_name

        """
        print("LOG STREAM:")
        print(log_stream)
        print("LOG FILENAME: ", log_file_name)
        # if this is True (which it is right now) 'open' is not available
        print("IS FINALIZING: ", is_finalizing())

        with open(log_file_name, 'w') as fd:
            log_stream.seek(0)
            shutil.copyfileobj(log_stream, fd)

    def close_log_stream(self):
        print("Closing log stream.", self.log_stream, self.log_stream.closed)
        if self.log_stream and not self.log_stream.closed:
            self.info("PgeLogger", ErrorCode.CLOSING_LOG_FILE,
                      f"Closing log file {self.get_file_name()}")
            self.write_log_summary()

            # Save and close log stream
            print(type(self.log_stream))
            self.stream_to_file(self.log_stream, self.log_filename)

            with open(self.log_filename, 'w') as fd:
                self.log_stream.seek(0)
                shutil.copyfileobj(self.log_stream, fd)

            self.log_stream.close()

    @property
    def workflow(self):
        return self._workflow

    @workflow.setter
    def workflow(self, workflow: str):
        self._workflow = workflow

    @property
    def error_code_base(self):
        return self._error_code_base

    @error_code_base.setter
    def error_code_base(self, error_code_base: int):
        self._error_code_base = error_code_base

    def get_log_count_by_severity(self, severity):
        """
        Gets the number of messages logged for the specified severity

        Parameters
        ----------
        severity : str
            The severity level to get the log count of. Should be one of
            info, debug, warning, critical (case-insensitive).

        Returns
        -------
        log_count : int
            The number of messages logged at the provided severity level.

        """
        try:
            severity = standardize_severity_string(severity)
            count = self.log_count_by_severity[severity]
            return count
        except KeyError:
            return 0

    @staticmethod
    def _make_blank_log_count_by_severity_dict():
        return {
            "Debug": 0,
            "Info": 0,
            "Warning": 0,
            "Critical": 0
        }

    def get_log_count_by_severity_dict(self):
        """Returns a copy of the dictionary of log counts by severity."""
        return self.log_count_by_severity.copy()

    def increment_log_count_by_severity(self, severity):
        """
        Increments the logged message count of the provided severity level.

        Parameters
        ----------
        severity : str
            The severity level to increment the log count of. Should be one of
            info, debug, warning, critical (case-insensitive).

        """
        try:
            severity = standardize_severity_string(severity)
            count = 1 + self.log_count_by_severity[severity]
            self.log_count_by_severity[severity] = count
        except KeyError:
            # TODO: log this?
            pass

    def write(self, severity, module, error_code_offset, description,
              additional_back_frames=0):
        """
        Write a message to the log.

        Parameters
        ----------
        severity : str
            The severity level to log at. Should be one of info, debug, warning,
            critical (case-insensitive).
        module : str
            Name of the module where the logging took place.
        error_code_offset : int
            Error code offset to add to the specified base to determine the
            error code associated with the log message
            TODO: should this be just the error code itself?
        description : str
            Description message to write to the log.
        additional_back_frames : int, optional
            Number of call-stack frames to "back up" to in order to determine
            the calling function and line number.

        """
        severity = standardize_severity_string(severity)
        self.increment_log_count_by_severity(severity)

        caller = inspect.currentframe().f_back

        # TODO: Can the number of back frames be determined implicitly?
        #       i.e. back up until the first non-logging frame is reached?
        for _ in range(additional_back_frames):
            caller = caller.f_back

        location = caller.f_code.co_filename + ':' + str(caller.f_lineno)

        write(self.log_stream, severity, self.workflow, module,
              self.error_code_base + error_code_offset,
              location, description)

    def info(self, module, error_code_offset, description):
        """
        Write an info-level message to the log.

        Parameters
        ----------
        module : str
            Name of the module where the logging took place.
        error_code_offset : int
            Error code offset to add to the specified base to determine the
            error code associated with the log message
            TODO: should this be just the error code itself?
        description : str
            Description message to write to the log.

        """
        self.write("Info", module, error_code_offset, description,
                   additional_back_frames=1)

    def debug(self, module, error_code_offset, description):
        """
        Write a debug-level message to the log.

        Parameters
        ----------
        module : str
            Name of the module where the logging took place.
        error_code_offset : int
            Error code offset to add to the specified base to determine the
            error code associated with the log message
            TODO: should this be just the error code itself?
        description : str
            Description message to write to the log.

        """
        self.write("Debug", module, error_code_offset, description,
                   additional_back_frames=1)

    def warning(self, module, error_code_offset, description):
        """
        Write a warning-level message to the log.

        Parameters
        ----------
        module : str
            Name of the module where the logging took place.
        error_code_offset : int
            Error code offset to add to the specified base to determine the
            error code associated with the log message
            TODO: should this be just the error code itself?
        description : str
            Description message to write to the log.

        """
        self.write("Warning", module, error_code_offset, description,
                   additional_back_frames=1)

    def critical(self, module, error_code_offset, description):
        """
        Write a critical-level message to the log.

        Since critical messages should be used for unrecoverable errors, any
        time this log level is invoked a RuntimeError is raised with the
        description provided to this function. The log file is closed and
        finalized before the exception is raised.

        Parameters
        ----------
        module : str
            Name of the module where the logging took place.
        error_code_offset : int
            Error code offset to add to the specified base to determine the
            error code associated with the log message
            TODO: should this be just the error code itself?
        description : str
            Description message to write to the log.

        """
        self.write("Critical", module, error_code_offset, description,
                   additional_back_frames=1)

        self.close_log_stream()

        raise RuntimeError(description)

    def log(self, module, error_code_offset, description, additional_back_frames=0):
        """
        Logs any kind of message.

        Determines the log level (Critical, Warning, Info, or Debug) based on
        the provided error code offset.

        Parameters
        ----------
        module : str
            Name of the module where the logging took place.
        error_code_offset : int
            Error code offset to add to the specified base to determine the
            error code associated with the log message
            TODO: should this be just the error code itself?
        description : str
            Description message to write to the log.
        additional_back_frames : int, optional
            Number of call-stack frames to "back up" to in order to determine
            the calling function and line number.

        """
        severity = get_severity_from_error_code(error_code_offset)
        self.write(severity, module, error_code_offset, description,
                   additional_back_frames=additional_back_frames + 1)

    def get_warning_count(self):
        """Returns the number of messages logged at the warning level."""
        return self.get_log_count_by_severity('Warning')

    def get_critical_count(self):
        """Returns the number of messages logged at the critical level."""
        return self.get_log_count_by_severity('Critical')

    # def flush(self):
    #     """Flushes the current contents of the log file to disk."""
    #     # Todo will probably get rid of this
    #     self.log_file.flush()

    def log_save_and_close(self):
        with open(self.log_filename, 'w') as fd:
            self.log_stream.seek(0)
            shutil.copyfileobj(self.log_stream, fd)
            # self.log_stream.close()

    def move(self, new_filename):
        """

        This function is useful when the log file has been given a default name,
        and needs to be assigned a name that meets the PGE file naming conventions.

        We probably don't need this anymore.

        Parameters
        ----------
        new_filename : str
            The new filename (including path) to assign to this log file.

        """
        msg = "Moving and saving log file {} as {}".format(self.log_filename, new_filename)
        # print(msg)
        self.info("PgeLogger", 900, msg)
        self.log_filename = new_filename
        self.log_save_and_close()

    def get_stream_object(self):
        """Return the stingIO object for the current log."""
        return self.log_stream

    def get_file_name(self):
        """Return the file name for the current log."""
        return self.log_filename

    def append_text_from_another_file(self, source_filename):
        """
        Appends text from another file to this log file.

        Parameters
        ----------
        source_filename : str
            File to read and append text from.

        """
        # TODO: check for file existence
        with open(source_filename, 'r') as source_file_object:
            source_contents = source_file_object.read()
            self.log_stream.write(source_contents)

    def log_one_metric(self, module, metric_name, metric_value,
                       additional_back_frames=0):
        """
        Writes one metric value to the log file.

        Parameters
        ----------
        module : str
            Name of the module where the logging took place.
        metric_name : str
            Name of the metric being logged.
        metric_value : object
            Value to associate to the logged metric.
        additional_back_frames : int
            Number of call-stack frames to "back up" to in order to determine
            the calling function and line number.

        """
        msg = "{}: {}".format(metric_name, metric_value)
        self.log(module, ErrorCode.SUMMARY_STATS_MESSAGE, msg,
                 additional_back_frames=additional_back_frames + 1)

    def write_log_summary(self):
        """
        Writes a summary at the end of the log file, which includes totals
        of each message logged for each severity level, OS-level metrics,
        and total elapsed run time (since logger creation).

        """
        module_name = "PgeLogger"

        # totals of messages logged
        copy_of_log_count_by_severity = self.log_count_by_severity.copy()
        for severity, count in copy_of_log_count_by_severity.items():
            metric_name = "overall.log_messages." + severity.lower()
            self.log_one_metric(module_name, metric_name, count)

        # overall OS metrics
        metrics = get_os_metrics()
        for metric_name, value in metrics.items():
            self.log_one_metric(module_name, "overall." + metric_name, value)

        # Overall elapsed time
        elapsed_time_seconds = time.monotonic() - self.start_time
        self.log_one_metric(module_name, "overall.elapsed_seconds",
                            elapsed_time_seconds)

    def resync_log_count_by_severity(self):
        """
        Resynchronizes the dictionary of log counts by severity for all log
        messages in the log file, including messages logged by anything external
        to the PgeLogger class, such as an external SAS invoked by a PGE wrapper.

        """
        # TODO: is this method really necessary? if the log file was kept in
        #       memory, could these tallies be kept in real-time?
        if not self.log_stream:
            return

        # read the file and get a count of log messages for each severity
        count_by_severity = self._make_blank_log_count_by_severity_dict()
        # log_filename = self.log_file.name

        # with open(log_filename, 'r', newline='') as in_file:
        # with open(self.log_filename, 'r', newline='') as in_file:
        #     csv_reader = csv.reader(in_file)
        csv_reader = self.log_stream.getvalue()
        for row in csv_reader:
            if len(row) >= 2:
                try:
                    severity = standardize_severity_string(row[1].strip())
                    count_by_severity[severity] += 1
                except KeyError:
                    pass

        self.log_count_by_severity = count_by_severity
