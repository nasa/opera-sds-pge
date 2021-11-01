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
==============
error_codes.py
==============

Error codes for use with OPERA PGEs.
"""

from enum import IntEnum, auto, unique

CODES_PER_RANGE = 1000
"""Number of error codes allocated to each range"""

INFO_RANGE_START = 0
"""Starting value for the Info code range"""

DEBUG_RANGE_START = INFO_RANGE_START + CODES_PER_RANGE
"""Starting value for the Debug code range"""

WARNING_RANGE_START = DEBUG_RANGE_START + CODES_PER_RANGE
"""Starting value for the Warning code range"""

CRITICAL_RANGE_START = WARNING_RANGE_START + CODES_PER_RANGE
"""Starting value for the Critical code range"""


@unique
class ErrorCode(IntEnum):
    """
    Error codes for OPERA PGEs.

    Each code is combined with the designated error code offset defined by
    the RunConfig to determine the final, logged error code.
    """

    # Info - 0 to 999
    OVERALL_SUCCESS = INFO_RANGE_START
    LOG_FILE_CREATED = auto()
    LOADING_RUN_CONFIG_FILE = auto()
    VALIDATING_RUN_CONFIG_FILE = auto()
    LOG_FILE_INIT_COMPLETE = auto()
    CREATING_WORKING_DIRECTORY = auto()
    DIRECTORY_SETUP_COMPLETE = auto()
    MOVING_LOG_FILE = auto()
    MOVING_OUTPUT_FILE = auto()
    SUMMARY_STATS_MESSAGE = auto()
    RUN_CONFIG_FILENAME = auto()
    PGE_NAME = auto()
    SCHEMA_FILE = auto()
    PROCESSING_INPUT_FILE = auto()
    USING_CONFIG_FILE = auto()
    CREATED_SAS_CONFIG = auto()
    CREATING_OUTPUT_FILE = auto()
    CREATING_CATALOG_METADATA = auto()
    SAS_PROGRAM_STARTING = auto()
    SAS_PROGRAM_COMPLETED = auto()
    QA_SAS_PROGRAM_STARTING = auto()
    QA_SAS_PROGRAM_COMPLETED = auto()
    QA_SAS_PRODUCED_VALIDATION_LOG_MESSAGES = auto()
    QA_SAS_END_OF_VALIDATION_LOG_MESSAGES = auto()
    QA_SAS_DID_NOT_PRODUCE_VALIDATION_LOG_MESSAGES = auto()
    RENDERING_ISO_METADATA = auto()
    CLOSING_LOG_FILE = auto()

    # Debug - 1000 – 1999
    CONFIGURATION_DETAILS = DEBUG_RANGE_START
    HEADER_DETAILS = auto()
    PROCESSING_DETAILS = auto()
    SAS_EXE_COMMAND_LINE = auto()

    # Warning - 2000 – 2999
    DATE_RANGE_MISSING = WARNING_RANGE_START
    ISO_METADATA_CANT_RENDER_ONE_VARIABLE = auto()
    CREATING_ISO_METADATA = auto()

    # Critical - 3000 to 3999
    INPUT_FILE = CRITICAL_RANGE_START
    RUN_CONFIG_VALIDATION_FAILED = auto()
    DIRECTORY_CREATION_FAILED = auto()
    SAS_CONFIG_CREATION_FAILED = auto()
    BAD_HEADER = auto()
    FILENAME_VIOLATES_NAMING_CONVENTION = auto()
    SAS_PROGRAM_NOT_FOUND = auto()
    SAS_PROGRAM_FAILED = auto()
    QA_SAS_PROGRAM_NOT_FOUND = auto()
    QA_SAS_PROGRAM_FAILED = auto()
    ISO_METADATA_GOT_SOME_RENDERING_ERRORS = auto()
    ISO_METADATA_RENDER_FAILED = auto()
    SAS_OUTPUT_FILE_HAS_MISSING_DATA = auto()

    @classmethod
    def describe(cls):
        """
        Provides a listing of the available error codes and their associated
        integer values.
        """
        for name, member in cls.__members__.items():
            print(f'{name}: {member.value}')
