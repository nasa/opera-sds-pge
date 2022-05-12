#!/usr/bin/env python3
#
# Original Author: David White
# Adapted By: Jim Hofman

"""
============
pge_main.py
============

Instantiates and runs an OPERA Product Generation Executable (PGE) instance.
The PGE type instantiated is determined from the provided RunConfig.

"""

import argparse
import os

from opera.pge.base_pge import PgeExecutor
from opera.pge.dswx_pge import DSWxExecutor
from opera.pge.runconfig import RunConfig
from opera.util.error_codes import ErrorCode
from opera.util.logger import PgeLogger

PGE_NAME_MAP = {
    'DSWX_HLS_PGE': DSWxExecutor,
    'default': PgeExecutor
}
"""Mapping of PGE names specified by a RunConfig to the PGE class type to instantiate"""


def get_pge_class(pge_name, logger):
    """
    Returns the PGE class type to be instantiated for the given PGE name.
    If the name is unknown, the default PGE class type is returned.

    Parameters
    ----------
    pge_name : str
        Name of the PGE to instantiate.
    logger : PgeLogger
        Logger instance.

    Returns
    -------
    class[PgeExecutor]
        The flavor of PgeExecutor to be instantiated for the provided name.
        The caller of this function is responsible for instantiating an object
        from the returned class according to the signature of PgeExecutor.__init__.

    """
    # Return either the PGE configured for the name, or the default class
    # if we don't have a mapping for it.
    pge_class = PGE_NAME_MAP.get(pge_name, PGE_NAME_MAP['default'])

    logger.info("pge_main", ErrorCode.PGE_NAME,
                f'Using class {pge_class.__name__} for PGE name {pge_name}')

    return pge_class


def open_log_file():
    """
    Opens a log file using an initial filename and path that
    does not rely on anything read from the run config file

    Returns
    -------
    logger : PgeLogger
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
    logger : PgeLogger
        logger recording pge_main.py events
        Will then be passed to the PgeExecutor() instance
    run_config_filename : str
        Full path to the RunConfig yaml file

    Returns
    -------
    run_config : RunConfig
        The python RunConfig instance

    """
    # Log the yaml config file that is used.
    run_config = RunConfig(run_config_filename)
    msg = f'RunConfig yaml file: {run_config_filename}'
    logger.info("pge_main", ErrorCode.RUN_CONFIG_FILENAME, msg)

    # Log the schema file that is used.
    schema_file = run_config.sas_schema_path
    msg = f"SAS Schema file: {schema_file}"
    logger.info("pge_main", ErrorCode.SCHEMA_FILE, msg)

    # Log the PGE name.
    pge_name = run_config.pge_name
    msg = f"PGE name: {pge_name}"
    logger.info("pge_main", ErrorCode.PGE_NAME, msg)

    return run_config


def pge_start(run_config_filename):
    """
    Opens a log file, loads the yaml run config file, then instantiates and runs
    the PGE.

    Parameters
    ----------
    run_config_filename : str
        Path and filename to run config yaml file.

    """
    logger = open_log_file()

    # Load the yaml run config file
    run_config = load_run_config_file(logger, run_config_filename)

    # Get the appropriate PGE class type based on the name in the RunConfig
    pge_class = get_pge_class(run_config.pge_name, logger)

    # Instantiate and run the pge.
    pge = pge_class(
        pge_name=run_config.pge_name, runconfig_path=run_config_filename, logger=logger
    )

    pge.run()


def pge_main():
    """
    The main entry point for OPERA PGEs.

    Reads the PGEName from the specified run config file to determine the
    specific PGE, then runs that specific PGE.

    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('-f', '--file', required=True, type=str,
                        help='Path to the run configuration yaml file.')

    args = parser.parse_args()

    run_config_filename = os.path.abspath(args.file)

    if not os.path.exists(run_config_filename):
        raise FileNotFoundError(f"Could not find config file: {run_config_filename}")

    pge_start(run_config_filename)


if __name__ == '__main__':
    pge_main()
