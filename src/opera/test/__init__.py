#!/usr/bin/env python3

"""
====
test
====

The unit-level regression test module for the OPERA PGE Subsystem.

"""
import os
import pathlib
import types
from importlib.resources import as_file, files

from typing import Union, ContextManager

Package = Union[types.ModuleType, str]
Resource = Union[str, os.PathLike]


def normalize_path(path):
    """Normalize a path by ensuring it is a string.

    If the resulting string contains path separators, an exception is raised.
    """
    str_path = str(path)
    parent, file_name = os.path.split(str_path)
    if parent:
        raise ValueError(f'{path!r} must be only a file name')
    return file_name


def path(package: Package, resource: Resource,) -> ContextManager[pathlib.Path]:
    """A context manager providing a file path object to the resource.

    If the resource does not already exist on its own on the file system,
    a temporary file will be created. If the file was created, the file
    will be deleted upon exiting the context manager (no exception is
    raised if the file was deleted prior to the context manager
    exiting).

    This function (and normalize_path) are adapted from the _legacy.py module
    of the imporlib_resources repository to avoid deprecation warnings emitted
    from use of the baseline  importlib.resources.path function.
    """
    return as_file(files(package) / normalize_path(resource))
