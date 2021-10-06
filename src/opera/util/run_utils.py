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
import subprocess
import time

from .error_codes import ErrorCode


def time_and_execute(command_line, logger):
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

    Returns
    -------
    elapsed_time : float
        The time elapsed during execution, in seconds.

    """
    module_name = f'time_and_execute::{os.path.basename(__file__)}'

    start_time = time.monotonic()

    # TODO: support for timeout argument?
    run_result = subprocess.run(command_line, env=os.environ.copy(), check=False,
                                stdout=logger.get_file_object(),
                                stderr=subprocess.STDOUT)

    if run_result.returncode:
        error_msg = (f'Command "{" ".join(command_line)}" failed with exit '
                     f'code {run_result.returncode}')

        logger.critical(module_name, ErrorCode.SAS_PROGRAM_FAILED, error_msg)

        raise ChildProcessError(error_msg)

    stop_time = time.monotonic()

    elapsed_time = stop_time - start_time

    return elapsed_time
