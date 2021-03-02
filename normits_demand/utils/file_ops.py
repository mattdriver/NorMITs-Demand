# -*- coding: utf-8 -*-
"""
Created on: Thur February 11 15:59:21 2020
Updated on:

Original author: Ben Taylor
Last update made by:
Other updates made by:

File purpose:
A collections of utility functions for file operations
"""
# builtins
import os
import pathlib

from typing import Union

# Third Party

# Local imports


def file_exists(file_path: Union[str, pathlib.Path]) -> bool:
    """
    Checks if a file exists at the given path.

    Parameters
    ----------
    file_path:
        path to the file to check.

    Returns
    -------
    file_exists:
        True if a file exists, else False
    """
    if not os.path.exists(file_path):
        return False

    if not os.path.isfile(file_path):
        raise IOError(
            "The given path exists, but does not point to a file. "
            "Given path: %s" % str(file_path)
        )

    return True


def check_file_exists(file_path: Union[str, pathlib.Path]) -> None:
    """
    Checks if a file exists at the given path. Throws an error if not.

    Parameters
    ----------
    file_path:
        path to the file to check.

    Returns
    -------
    None
    """
    if not file_exists(file_path):
        raise IOError(
            "Cannot find a path to: %s" % str(file_path)
        )


def is_csv(file_path: Union[str, pathlib.Path]) -> bool:
    """
    Returns True if given file path points to a csv, else False

    Parameters
    ----------
    file_path:
        path to the file to check

    Returns
    -------
    boolean:
        True if given file path points to a csv, else False
    """
    # Try to extract the filename extension
    filename_parts = str(file_path).split('.')

    # File doesn't seem to have an file_extension?
    if len(filename_parts) < 1:
        return False

    file_extension = filename_parts[-1].lower()
    return file_extension == 'csv'


def maybe_add_suffix(path: Union[str, pathlib.Path],
                     suffix: str,
                     overwrite: bool = False,
                     ) -> pathlib.Path:
    """
    Adds suffix to path if no suffix already exists.

    Will overwrite any existing suffix if overwrite is set to True

    Parameters
    ----------
    path:
        The path to maybe add the suffix to.

    suffix:
        The suffix to add onto path.

    overwrite:
        If set to True, will overwrite any suffix that already exists in path.

    Returns
    -------
    path:
        The original passed in path with an updated suffix.
    """
    # Init
    if not isinstance(path, pathlib.Path):
        out_path = pathlib.Path(path)

    # Remove current suffix if we're overwriting
    if overwrite:
        path = path.parent / path.stem

    # Add suffix if not there
    if path.suffix == '':
        path = path.parent / (path.name + suffix)

    return path
