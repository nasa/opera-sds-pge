#!/usr/bin/env python3

"""
============
run_utils.py
============

Contains utility functions for running executable processes within the OPERA PGE
subsystem.

"""

import hashlib
import os
import shutil
import subprocess
import time
from os.path import abspath

from .error_codes import ErrorCode


def get_checksum(file_name):
    """
    Generate the MD5 checksum of the provided file.

    This function was adapted from swot_pge.util.BasePgeWrapper.get_checksum()

    Parameters
    ----------
    file_name : str
        Path the file on disk to generate the checksum for.

    Returns
    -------
    checksum : str
        MD5 checksum of the provided file.

    """
    hash_md5 = hashlib.md5()

    with open(file_name, "rb") as infile:
        # chunk size is set to 1048576
        for chunk in iter(lambda: infile.read(2 ** 20), b""):
            hash_md5.update(chunk)

    return hash_md5.hexdigest()


def get_extension(file_name):
    """Returns the file extension (including the dot) of the provided file name."""
    return os.path.splitext(file_name)[-1]


def create_sas_command_line(sas_program_path, sas_runconfig_path,
                            sas_program_options=None):
    """
    Forms the appropriate command line for executing a SAS from the parameters
    obtained from the RunConfig.

    By default, this function assumes the SAS program path corresponds to an
    executable file reaching within the current environment's PATH. If this
    function cannot locate the executable, the SAS program path is assumed to be
    a Python module path and treated accordingly.

    Parameters
    ----------
    sas_program_path : str
        The path to the SAS executable to be invoked by the returned command line.
    sas_runconfig_path : str
        The path to the RunConfig to feed to the SAS executable in the returned
        command line.
    sas_program_options : list[str], optional
        List of options to include in the returned command line.

    Returns
    -------
    command_line : list[str]
        The fully formed command line, returned in list format suitable for use
        with subprocess.run.

    Raises
    ------
    OSError
        If the SAS executable exists within the current environment, but is not
        set with execute permissions for the current process.

    """
    command_line = []

    if executable_path := shutil.which(sas_program_path):
        command_line = [executable_path]
    else:
        executable_path = abspath(sas_program_path)

        # Check if the executable exists
        if os.access(executable_path, mode=os.F_OK):
            # Check if the executable has 'execute' permissions on it
            if not os.access(executable_path, mode=os.X_OK):
                raise OSError(f"Requested SAS program path {sas_program_path} exists, "
                              f"but does not have execute permissions.")
        # Otherwise, sas_program_path might be a python module path
        else:
            command_line = ['python3', '-m', sas_program_path]

    # Add any provided arguments
    if sas_program_options:
        command_line.extend(sas_program_options)

    # Lastly, only explicit input should ever be the path to the runconfig
    command_line.append(sas_runconfig_path)

    return command_line


def create_qa_command_line(qa_program_path, qa_program_options=None):
    """
    Forms the appropriate command line for executing a SAS Quality Assurance (QA)
    application from parameters obtained from the RunConfig.

    By default, this function assumes the QA program path corresponds to an
    executable file reaching within the current environment's PATH. If this
    function cannot locate the executable, the QA program path is assumed to be
    a Python module path and treated accordingly.

    Parameters
    ----------
    qa_program_path : str
        The path to the QA executable to be invoked by the returned command line.
    qa_program_options : list[str], optional
        List of options to include in the returned command line.

    Returns
    -------
    command_line : list[str]
        The fully formed command line, returned in list format suitable for use
        with subprocess.run.

    Raises
    ------
    OSError
        If the QA executable exists within the current environment, but is not
        set with execute permissions for the current process.

    """
    command_line = []

    if executable_path := shutil.which(qa_program_path):
        command_line = [executable_path]
    else:
        executable_path = abspath(qa_program_path)

        # Check if the executable exists
        if os.access(executable_path, mode=os.F_OK):
            # Check if the executable has 'execute' permissions on it
            if not os.access(executable_path, mode=os.X_OK):
                raise OSError(f"Requested QA program path {qa_program_path} exists, "
                              f"but does not have execute permissions.")
        # Otherwise, qa_program_path might be a python module path
        else:
            command_line = ['python3', '-m', qa_program_path]

    # Add any provided arguments
    if qa_program_options:
        command_line.extend(qa_program_options)

    return command_line


def time_and_execute(command_line, logger, execute_via_shell=False):
    """
    Executes the provided command line via subprocess while collecting the
    runtime of the execution.

    Parameters
    ----------
    command_line : Iterable[str]
        The command line program, including options/arguments, to execute.
        Each
    logger : PgeLogger
        A logger object used to capture any error status returned from execution.
    execute_via_shell : bool, optional
        If true, instruct subprocess.run to execute the command-line via system
        shell. Useful for running test commands but should generally not be used
        for production.

    Returns
    -------
    elapsed_time : float
        The time elapsed during execution, in seconds.

    """
    module_name = f'time_and_execute::{os.path.basename(__file__)}'

    start_time = time.monotonic()

    # If the command is to be fed to shell, recombine the list into a single
    # string. Otherwise, only the first token (the executable) would be invoked.
    if execute_via_shell:
        command_line = " ".join(command_line)

    # TODO: support for timeout argument?
    run_result = subprocess.run(command_line, env=os.environ.copy(), check=False,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                shell=execute_via_shell)

    # Append the stdout/stderr captured by the subprocess to our log
    logger.append(run_result.stdout.decode())

    tail = run_result.stdout.decode().split('\n')
    tail = "\n".join(tail[-20:])

    if run_result.returncode:
        error_msg = (f'Command "{str(command_line)}" failed with exit '
                     f'code {run_result.returncode}, traceback: {tail}')

        logger.critical(module_name, ErrorCode.SAS_PROGRAM_FAILED, error_msg)

    stop_time = time.monotonic()

    elapsed_time = stop_time - start_time

    return elapsed_time
