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
#
# Original Author: David White
# Adapted By: Jim Hofman

"""
==============
pge_main.py
==============

Instantiates and runs a PGEExecutor instance.

"""

import argparse
import os
import sys

sys.path.append("/Users/jehofman/Documents/opera_pge/src/")

from opera.pge.base_pge import PgeExecutor
from opera.pge.runconfig import RunConfig
from opera.util.logger import PgeLogger
from opera.util.error_codes import ErrorCode


def open_log_file():
    """
    Opens a log file using an initial filename and path that
    does not rely on anything read from the run config file

    Returns
    -------
    logger : PgeLogger()
        PgeLogger object with initialized filename

    """

    logger = PgeLogger('PGE::' + os.path.basename(__file__), PgeLogger.LOGGER_CODE_BASE)

    logger.info("pge_main", ErrorCode.LOG_FILE_CREATED,
                f'Log file initialized to {logger.get_file_name()}')

    return logger


def load_run_config_file(logger, run_config_filename):
    """
    Loads the run config file into a Python dictionary

    Parameters
    ----------
    logger : PgeLogger()
        logger recording pge_main.py events
        Will then be passed to the PgeExecutor() instance
    run_config_filename
        Full path to the RunConfig yaml file

    Returns
    -------
    nun_config :  RunConfig()
        The python RunConfig instance

    """

    # Log the yaml config file that is  used.
    run_config = RunConfig(run_config_filename)
    msg = f'Run config yaml file: {run_config_filename}'
    logger.info("pge_main", ErrorCode.RUN_CONFIG_FILENAME, msg)

    # Log the schema file that is  used.
    schema_file = run_config.sas_schema_path
    msg = f"Schema file: {schema_file}"
    logger.info("pge_main", ErrorCode.SCHEMA_FILE, msg)

    # Log the PGE name.
    pge_name = run_config.pge_name
    msg = f"PGE name: {pge_name}"
    logger.info("pge_main", ErrorCode.PGE_NAME, msg)

    return run_config


def pge_start(run_config_filename):
    """
    Opens a log file, loads the yaml run config file, then instantiates and runs the PGE.

    Parameters
    ----------
    run_config_filename : str
        Path and filename to run config yaml file.

    """

    logger = open_log_file()

    # load the yaml run config file
    run_config = load_run_config_file(logger, run_config_filename)

    # Instantiate and run the base pge.
    pge = PgeExecutor(run_config.pge_name, run_config_filename, logger=logger)

    pge.run()


def pge_main():
    """
    The main entry point for OPERA PGEs.

    Reads the PGEName from the specified run config file to determine the
    specific PGE, then runs that specific PGE.

    """

    parser = argparse.ArgumentParser(
        description='\n'.join(__doc__.split('\n')[0:2]),
        epilog='\n'.join(__doc__.split('\n')[2:]),
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('-f', '--file', required=True, type=str,
                        help='The run configuration yaml file (full path).')

    args = parser.parse_args()

    if not os.path.exists(args.file):
        raise FileNotFoundError(f"Could not find config file: {args.file}")

    run_config_filename = os.path.abspath(args.file)

    pge_start(run_config_filename)


if __name__ == '__main__':
    pge_main()
