#!/usr/bin/env python3
#

"""
==============
dyn_import.py
==============

Implements dynamic imports

"""

import importlib.util

from opera.util.error_codes import ErrorCode


def import_module_from_spec(module_to_import, logger):
    """
           Check the module to verify it can be loaded, if not return False

       Parameters
       ----------
       module_to_import : str
            Module that will be imported
       logger :  Pge_logger
            logger for this particular run

       Returns
       -------
       module : module class
           The module that has been imported

       """
    module_spec = importlib.util.find_spec(module_to_import)
    if module_spec is None:
        logger.critical("dyn_import", ErrorCode.DYNAMIC_IMPORT_FAILED,
                        f'Could not find specs needed to import {module_to_import}')
        return None
    else:
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        return module

