#!/usr/bin/env python3
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
run_utils.py
============

Contains utility functions for running executable processes within the OPERA PGE
subsystem.

"""

import os
import shutil
import subprocess
import time

from os.path import abspath

from .error_codes import ErrorCode


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
    executable_path = shutil.which(sas_program_path)

    if executable_path:
        command_line = [executable_path]
    else:
        executable_path = abspath(sas_program_path)

        # Check if the executable exists, but does not have execute permissions on it
        if (os.access(executable_path, mode=os.F_OK)
                and not os.access(executable_path, mode=os.X_OK)):
            raise OSError(f"Requested SAS program path {sas_program_path} exists, "
                          f"but does not have execute permissions.")
        # Otherwise, sas_program_path might be a python module path
        else:
            command_line = ['python3', '-m', sas_program_path]

    # Add any provided arguments
    for sas_program_option in sas_program_options:
        command_line.extend(sas_program_option.split())

    # Lastly, only explicit input should ever be the path to the runconfig
    command_line.append(sas_runconfig_path)

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
    # string. Otherwise only the first token (the executable) would be invoked.
    if execute_via_shell:
        command_line = " ".join(command_line)

    # TODO: support for timeout argument?
    run_result = subprocess.run(command_line, env=os.environ.copy(), check=False,
                                stdout=logger.get_file_object(),
                                stderr=subprocess.STDOUT, shell=execute_via_shell)

    if run_result.returncode:
        error_msg = (f'Command "{" ".join(command_line)}" failed with exit '
                     f'code {run_result.returncode}')

        logger.critical(module_name, ErrorCode.SAS_PROGRAM_FAILED, error_msg)

    stop_time = time.monotonic()

    elapsed_time = stop_time - start_time

    return elapsed_time
