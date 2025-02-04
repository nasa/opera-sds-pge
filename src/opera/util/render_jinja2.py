#!/usr/bin/env python3

"""
================
render_jinja2.py
================

Helper function(s) to render a Jinja2-based template.

Original Author: David White
Adapted by: Jim Hofman
"""

import html
import json
import os
import re

from functools import partial

import jinja2
import yaml

import numpy as np

from lxml import etree
from opera.util.error_codes import ErrorCode
from opera.util.h5_utils import MEASURED_PARAMETER_PATH_SEPARATOR
from opera.util.logger import PgeLogger

XML_TYPES = {
    str: 'string',
    int: 'int',
    float: 'float',
    bool: 'boolean',
}

INTEGER_PATTERN = re.compile(r'^[+-]?\d+$')
FLOATING_POINT_PATTERN = re.compile(r'^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$')

UNDEFINED_ERROR = '!Not found!'
"""
Placeholder written in for missing fields when rendering a jinja2 template.
If this value is written to an instantiated template, it indicates an unexpected
error, either in the template itself or the Measured Parameters config file.
"""

UNDEFINED_WARNING = 'Not provided'
"""
Placeholer written in for undefined fields when rendering a jinja2 template.
Unlike UNDEFINED_ERROR, existence of this placeholder within a rendered template
does not indicate a configuration error, rather an incomplete or missing Measured
Parameters config file.
"""


def _make_undefined_handler_class(logger: PgeLogger):
    """
    Factory function, returns a child class of the jinja2.Undefined class for
    use when rendering templates.
    The intent is to override the default behavior which can raise an exception
    while rendering Jinja2 templates if there is a failure to render a
    template variable. Instead:
        log the error the PGE way (using the PgeLogger class)
        put UNDEFINED_ERROR constant in the rendered text
        let the template rendering continue, try to render the rest of the template.

    Parameters
    ----------
    logger : PgeLogger
        logger of the current pge instance

    Returns
    -------
    LoggingUndefined : class
        child class of the jinja2.Undefined class, used to avoid exception handling.
        Allows UNDEFINED_ERROR constant to be added to the rendered text


    """

    def _log_message(undef):
        """Notes missing/undefined ISO metadate template variable in logger.

        Parameters
        ----------
        undef : object

        """
        # pylint: disable=protected-access
        msg = f"Missing/undefined ISO metadata template variable: {undef._undefined_message}"
        logger.log("render_jinja2", ErrorCode.ISO_METADATA_CANT_RENDER_ONE_VARIABLE, msg)

    class LoggingUndefined(jinja2.Undefined):
        """Override the default behavior which can raise an exception"""

        def _fail_with_undefined_error(self, *args, **kwargs):  # pragma no cover
            _log_message(self)

        def __str__(self):
            _log_message(self)
            return UNDEFINED_ERROR

        def __iter__(self):  # pragma no cover
            _log_message(self)
            return super().__iter__()

        def __bool__(self):  # pragma no cover
            _log_message(self)
            return super().__bool__()

        def __getattr__(self, name):
            _log_message(self)
            return super().__getattr__(name)

    return LoggingUndefined


def _try_parse_xml_string(s: str):
    _ = etree.fromstring(s.encode('utf-8'))


JSON_VALIDATOR = json.loads
YAML_VALIDATOR = partial(yaml.load, Loader=yaml.SafeLoader)
XML_VALIDATOR = _try_parse_xml_string


def render_jinja2(
        template_filename: str,
        input_data: dict,
        logger: PgeLogger = None,
        validator=XML_VALIDATOR
):
    """
    Renders from a jinja2 template using the specified input data.
    Writes the rendered output to the specified output file.

    Parameters
    ----------
    template_filename: str
        Jinja2 template file
    input_data: dict
        The input data dictionary passed to the Jinja2 template render function.
    logger:
        PgeLogger (optional, suggested). If provided, template rendering
        errors due to missing/undefined variables will be logged and
        will not raise exceptions or abort rendering. If not provided,
        the default Jinja2 error handling will apply for such errors,
        possibly including raised exceptions.
    validator:
        Callable which, if provided, takes the rendered text as an input and
        attempts to parse it. Must raise an exception if given invalid input.

    Returns
    -------
    rendered_text : str
        The body of the specified template, instantiated with the provided
        input data.

    """
    template_directory = os.path.dirname(template_filename)

    if not template_directory:
        template_directory = os.getcwd()

    template_filename = os.path.basename(template_filename)

    template_loader = jinja2.FileSystemLoader(searchpath=template_directory)

    undefined_handler_class = (_make_undefined_handler_class(logger)
                               if logger is not None
                               else jinja2.Undefined)

    template_env = jinja2.Environment(loader=template_loader,
                                      autoescape=jinja2.select_autoescape(),
                                      undefined=undefined_handler_class)

    template = template_env.get_template(template_filename)

    rendered_text = template.render(input_data)

    if validator is not None:
        try:
            validator(rendered_text)
        except Exception as err:
            raise RuntimeError(f"Error parsing rendered ISO XML: {err}") from err

    return rendered_text


def python_type_to_xml_type(obj) -> str:
    """Returns a guess for the XML type of a Python object."""
    if isinstance(obj, str):
        if obj.lower() in ['true', 'false']:
            obj = obj.lower() == 'true'
        elif re.match(INTEGER_PATTERN, obj) is not None:
            obj = int(obj)
        elif re.match(FLOATING_POINT_PATTERN, obj) is not None:
            obj = float(obj)

    if not isinstance(obj, type):
        obj = type(obj)

    return XML_TYPES[obj]


def augment_measured_parameters(measured_parameters: dict, mpc_path: str, logger: PgeLogger) -> dict:
    """
    Augment the measured parameters dict of GeoTIFF metadata into a dict of dicts
    containing the needed fields for the MeasuredParameters section of the ISO XML
    file.

    For HDF5 or NetCDF metadata, use augment_hd5_measured_parameters()

    Parameters
    ----------
    measured_parameters : dict
       The GeoTIFF metadata from the output product. See get_geotiff_metadata()
    mpc_path: str
        Path to the Measured Parameters Descriptions YAML file
    logger: PgeLogger
        PgeLogger instance

    Returns
    -------
    augmented_parameters : dict
       The metadata fields converted to a list with name, value, types, etc
    """
    augmented_parameters = dict()

    if mpc_path is not None:
        with open(mpc_path) as f:
            descriptions = yaml.safe_load(f)

        missing_description_value = UNDEFINED_ERROR
    else:
        descriptions = dict()
        missing_description_value = UNDEFINED_WARNING

    for name, value in measured_parameters.items():
        if isinstance(value, np.generic):
            value = value.item()

        if isinstance(value, np.ndarray):
            value = value.tolist()

        if isinstance(value, (list, dict)):
            value = json.dumps(value, cls=NumpyEncoder)

        guessed_data_type = python_type_to_xml_type(value)
        guessed_attr_name = guess_attribute_display_name(name)

        descriptions.setdefault(name, dict())

        attr_description = descriptions[name].get('description', missing_description_value)
        data_type = descriptions[name].get('attribute_data_type', guessed_data_type)
        attr_type = descriptions[name].get('attribute_type', UNDEFINED_ERROR)
        attr_name = descriptions[name].get('display_name', guessed_attr_name)
        escape_html = descriptions[name].get('escape_html', False)

        if escape_html:
            value = html.escape(value)

        augmented_parameters[name] = (
            dict(name=attr_name, value=value, attr_type=attr_type,
                 attr_description=attr_description, data_type=data_type)
        )

    return augmented_parameters


def augment_hd5_measured_parameters(measured_parameters: dict, mpc_path: str, logger: PgeLogger) -> dict:
    """
    The augment_measured_parameters() function wrapped in a "preprocessing" step to
    handle the structure of HDF5 metadata. While GeoTIFF metadata is a flat
    dictionary, HDF5 metadata is a nested dictionary structure, wherein the variable
    "keys" can be arbitrarily deep into the structure and the values likewise can be
    nested dictionaries.

    The preprocessing step in this method selectively flattens the metadata
    dictionary based on the "paths" provided in the variable keys of the configuration
    YAML file. The result of this preprocessing is then safely passed to the base
    method to get the correct structure expected by the Jinja template.

    Parameters
    ----------
    measured_parameters : dict
        The HDF5 metadata from the output product. See get_cslc_s1_product_metadata()
    mpc_path: str
        Path to the Measured Parameters Descriptions YAML file
    logger: PgeLogger
        PgeLogger instance

    Returns
    -------
    augmented_parameters : dict
        The metadata fields converted to a list with name, value, types, etc
    """
    new_measured_parameters = {}

    if mpc_path:
        with open(mpc_path) as f:
            descriptions = yaml.safe_load(f)
    else:
        msg = ('Measured parameters configuration is needed to extract the measured parameters attributes from the '
               'metadata')
        logger.critical("render_jinja2", ErrorCode.ISO_METADATA_DESCRIPTIONS_CONFIG_NOT_FOUND, msg)

    for parameter_var_name in descriptions:
        key_path = parameter_var_name.split(MEASURED_PARAMETER_PATH_SEPARATOR)

        mp = measured_parameters
        missing = False

        while len(key_path) > 0:
            try:
                mp = mp[key_path.pop(0)]
            except KeyError:
                msg = (f'Measured parameters configuration contains a path {parameter_var_name} that is missing '
                       f'from the output product')
                if descriptions[parameter_var_name].get('optional', False):
                    logger.warning("render_jinja2", ErrorCode.ISO_METADATA_NO_ENTRY_FOR_DESCRIPTION, msg)
                    missing = True
                else:
                    logger.critical("render_jinja2", ErrorCode.ISO_METADATA_DESCRIPTIONS_CONFIG_INVALID, msg)

        if not missing:
            new_measured_parameters[parameter_var_name] = mp

    return augment_measured_parameters(new_measured_parameters, mpc_path, logger)


class NumpyEncoder(json.JSONEncoder):
    """Class to handle serialization of Numpy types during JSON enconding"""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.bool_):
            return bool(obj)
        return super(NumpyEncoder, self).default(obj)


def guess_attribute_display_name(var_name: str) -> str:
    """
    Returns an approximation of an Additional Attribute's display name from its attribute name by converting snake_case
    to PascalCase.
    Ex. sample_attribute_name -> SampleAttributeName
    """
    return var_name.title().replace('_', '')
