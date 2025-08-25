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
from collections.abc import Callable
from datetime import datetime
from typing import Any, Optional

import jinja2

from lxml import etree

import numpy as np

import yaml

from yaml.scanner import ScannerError

from opera.util.error_codes import ErrorCode
from opera.util.h5_utils import MEASURED_PARAMETER_PATH_SEPARATOR
from opera.util.logger import PgeLogger
import opera.util.time as time_util

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


def _validate_rendered_json_string(string: str, output_directory: str, logger: PgeLogger):
    try:
        _ = json.loads(string)
    except json.JSONDecodeError as err:
        msg_lines = ['Rendered JSON not valid!']

        rendered_lines = string.splitlines()

        err_line, err_col = err.lineno, err.colno
        err_line_index = err_line - 1

        msg_lines.extend(rendered_lines[max(err_line_index - 2, 0):err_line_index + 1])
        msg_lines.append(f'{" " * (err_col - 1)}^')
        msg_lines.extend(rendered_lines[err_line_index + 1:min(err_line_index + 2, len(rendered_lines))])

        if output_directory is not None:
            dumpfile_name = f'bad_json_{time_util.get_time_for_filename(datetime.now())}.json'
            dumpfile_path = os.path.join(output_directory, dumpfile_name)

            with open(dumpfile_path, 'w', encoding='utf-8') as f:
                f.write(string)

            msg_lines.append(f'Failed to render jinja2 template. Err: "{err.args[0]}" @ {err_line}:{err_col}. Rendered'
                             f' text dumped to {dumpfile_path}')
        else:
            msg_lines.append(f'Failed to render jinja2 template. Err: "{err.args[0]}" @ {err_line}:{err_col}.')

        logger.critical(
            "render_jinja2",
            ErrorCode.LOGGED_CRITICAL_LINE,
            msg_lines,
        )


def _validate_rendered_yaml_string(string: str, output_directory: str, logger: PgeLogger):
    try:
        _ = yaml.load(string, Loader=yaml.SafeLoader)
    except ScannerError as err:
        msg_lines = ['Rendered YAML not valid!']

        rendered_lines = string.strip().splitlines()

        err_line, err_col = err.problem_mark.line, err.problem_mark.column
        err_line_index = err_line - 1

        msg_lines.extend(rendered_lines[max(err_line_index - 2, 0):err_line_index + 1])
        msg_lines.append(f'{" " * (err_col - 1)}^')
        msg_lines.extend(rendered_lines[err_line_index + 1:min(err_line_index + 2, len(rendered_lines))])

        if output_directory is not None:
            dumpfile_name = f'bad_yaml_{time_util.get_time_for_filename(datetime.now())}.yaml'
            dumpfile_path = os.path.join(output_directory, dumpfile_name)

            with open(dumpfile_path, 'w', encoding='utf-8') as f:
                f.write(string)

            msg_lines.append(f'Failed to render jinja2 template. Err: "{err.problem}" @ {err_line}:{err_col}. Rendered'
                             f' text dumped to {dumpfile_path}')
        else:
            msg_lines.append(f'Failed to render jinja2 template. Err: "{err.problem}" @ {err_line}:{err_col}.')

        logger.critical(
            "render_jinja2",
            ErrorCode.LOGGED_CRITICAL_LINE,
            msg_lines,
        )


def _validate_rendered_xml_string(string: str, output_directory: str, logger: PgeLogger):
    try:
        _ = etree.fromstring(string.encode('utf-8'))
    except etree.XMLSyntaxError as err:
        msg_lines = ['Rendered XML not valid!']

        rendered_lines = string.splitlines()

        err_line, err_col = err.position
        err_line_index = err_line - 1

        msg_lines.extend(rendered_lines[max(err_line_index - 2, 0):err_line_index+1])
        msg_lines.append(f'{" " * (err_col-1)}^')
        msg_lines.extend(rendered_lines[err_line_index+1:min(err_line_index+2, len(rendered_lines))])

        if output_directory is not None:
            dumpfile_name = f'bad_xml_{time_util.get_time_for_filename(datetime.now())}.xml'
            dumpfile_path = os.path.join(output_directory, dumpfile_name)

            with open(dumpfile_path, 'w', encoding='utf-8') as f:
                f.write(string)

            msg_lines.append(f'Failed to render jinja2 template. Err: "{err.msg}" @ {err_line}:{err_col}. Rendered'
                             f' text dumped to {dumpfile_path}')
        else:
            msg_lines.append(f'Failed to render jinja2 template. Err: "{err.msg}" @ {err_line}:{err_col}.')

        logger.critical(
            "render_jinja2",
            ErrorCode.LOGGED_CRITICAL_LINE,
            msg_lines,
        )


JSON_VALIDATOR = _validate_rendered_json_string
YAML_VALIDATOR = _validate_rendered_yaml_string
XML_VALIDATOR = _validate_rendered_xml_string


def render_jinja2(
        template_filename: str,
        input_data: dict,
        logger: PgeLogger = None,
        output_directory: str = None,
        validator: Optional[Callable[[str, str, PgeLogger], Any]] = XML_VALIDATOR
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
    output_directory: str
        Optional directory which, if validator fails, the rendered text will
        be dumped to.
    validator: collections.abc.Callable[[str, str, PgeLogger], Any]
        Callable which, if provided, takes the rendered text as an input and
        attempts to parse it. Must call logger.critical if given invalid input.

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

    template_env.filters['basename'] = lambda x: os.path.basename(str(x))

    template = template_env.get_template(template_filename)

    rendered_text = template.render(input_data)

    if validator is not None:
        validator(rendered_text, output_directory, logger)

    return rendered_text


def python_type_to_xml_type(obj) -> str:
    """Returns a guess for the XML type of a Python object."""
    if isinstance(obj, str):
        if obj.lower() in {'true', 'false'}:
            obj = obj.lower() == 'true'
        elif re.match(INTEGER_PATTERN, obj) is not None:
            obj = int(obj)
        elif re.match(FLOATING_POINT_PATTERN, obj) is not None:
            obj = float(obj)

    if not isinstance(obj, type):
        obj = type(obj)

    return XML_TYPES[obj]


# pylint: disable=unused-argument,consider-alternative-union-syntax
def augment_measured_parameters(measured_parameters: dict, mpc_path: Optional[str], logger: PgeLogger) -> dict:
    """
    Augment the measured parameters dict of GeoTIFF metadata into a dict of dicts
    containing the needed fields for the MeasuredParameters section of the ISO XML
    file.

    The configuration for how this is done is provided by the mpc_path parameter
    (see src/opera/pge/base/schema/iso_metadata_measured_parameters_config_schema.yaml).
    This configuration file is optional. If not provided (mpc_path=None), then the
    ISO XML's AdditionalAttribute descriptions will be fixed as "Not Provided", and
    the data type and display names will be guessed. If it is provided, any AdditionalAttributes
    present in the metadata that are missing corresponding entries in the MPC will
    be rendered as "!Not Found!" which is indicative of a configuration error.

    For HDF5 or NetCDF metadata, use augment_hd5_measured_parameters()

    Parameters
    ----------
    measured_parameters : dict
       The GeoTIFF metadata from the output product. See get_geotiff_metadata()
    mpc_path: str | None
        Path to the Measured Parameters Descriptions YAML file (OPTIONAL)
    logger: PgeLogger
        PgeLogger instance

    Returns
    -------
    augmented_parameters : dict
       The metadata fields converted to a list with name, value, types, etc
    """
    augmented_parameters = {}

    if mpc_path is not None:
        with open(mpc_path, 'r', encoding='utf-8') as data:
            descriptions = yaml.safe_load(data)

        missing_description_value = UNDEFINED_ERROR
    else:
        descriptions = {}
        missing_description_value = UNDEFINED_WARNING

    for name in measured_parameters:
        value = measured_parameters[name]

        if isinstance(value, np.generic):
            value = value.item()

        if isinstance(value, np.ndarray):
            value = value.tolist()

        if isinstance(value, (list, dict)):
            value = json.dumps(value, cls=NumpyEncoder)

        guessed_data_type = python_type_to_xml_type(value)
        guessed_attr_name = guess_attribute_display_name(name)

        descriptions.setdefault(name, {})

        attr_description = descriptions[name].get('description', missing_description_value)
        data_type = descriptions[name].get('attribute_data_type', guessed_data_type)
        attr_type = descriptions[name].get('attribute_type', UNDEFINED_ERROR)
        attr_name = descriptions[name].get('display_name', guessed_attr_name)
        escape_html = descriptions[name].get('escape_html', False)

        if escape_html:
            value = html.escape(value)

        augmented_parameters[name] = {
            'name': attr_name,
            'value': value,
            'attr_type': attr_type,
            'attr_description': attr_description,
            'data_type': data_type
        }

    return augmented_parameters


def augment_hdf5_measured_parameters(measured_parameters: dict, mpc_path: str, logger: PgeLogger) -> dict:
    """
    The augment_measured_parameters() function wrapped in a "preprocessing" step to
    handle the structure of HDF5 metadata. While GeoTIFF metadata is a flat
    dictionary, HDF5 metadata is a nested dictionary structure, wherein the variable
    "keys" can be arbitrarily deep into the structure and the values likewise can be
    nested dictionaries.

    The preprocessing step in this method selectively flattens the metadata
    dictionary based on the "paths" provided in the variable keys of the configuration
    YAML file. The result of this preprocessing is then safely passed to
    augment_measured_parameters()  to get the correct structure expected by the Jinja
    template.

    Unlike in augment_measured_parameters() the mpc_path parameter is REQUIRED. Since
    the measured_parameters metadata dictionary is not flat (vs a flat name: value
    structure expected by augment_measured_parameters()) there needs to be a way to
    determine which values are desired metadata values (which can be dictionaries).

    Metadata paths specified in the MPC but absent from the measured parameters
    dictionary are raised as a critical error by default, unless that entry in the
    MPC is marked optional, in which case a warning is logged.

    Parameters
    ----------
    measured_parameters : dict
        The HDF5 metadata from the output product. Ex: see get_cslc_s1_product_metadata()
    mpc_path: str
        Path to the Measured Parameters Descriptions YAML file (REQUIRED)
    logger: PgeLogger
        PgeLogger instance

    Returns
    -------
    augmented_parameters : dict
        The metadata fields converted to a list with name, value, types, etc
    """
    new_measured_parameters = {}
    descriptions = {}

    if mpc_path:
        with open(mpc_path, 'r', encoding='utf-8') as data:
            descriptions = yaml.safe_load(data)
    else:
        msg = ('Measured parameters configuration is needed to extract the measured parameters attributes from the '
               'metadata')
        logger.critical("render_jinja2", ErrorCode.ISO_METADATA_DESCRIPTIONS_CONFIG_NOT_FOUND, msg)

    for parameter_var_name in descriptions:
        key_path = parameter_var_name.split(MEASURED_PARAMETER_PATH_SEPARATOR)

        mp_item = measured_parameters
        missing = False

        while len(key_path) > 0:  # pylint: disable=while-used
            try:
                mp_item = mp_item[key_path.pop(0)]
            except KeyError:
                msg = (f'Measured parameters configuration contains a path {parameter_var_name} that is missing '
                       f'from the output product')
                if descriptions[parameter_var_name].get('optional', False):
                    logger.warning("render_jinja2", ErrorCode.ISO_METADATA_NO_ENTRY_FOR_DESCRIPTION, msg)
                    missing = True
                else:
                    logger.critical("render_jinja2", ErrorCode.ISO_METADATA_DESCRIPTIONS_CONFIG_INVALID, msg)

        if not missing:
            new_measured_parameters[parameter_var_name] = mp_item

    return augment_measured_parameters(new_measured_parameters, mpc_path, logger)


class NumpyEncoder(json.JSONEncoder):
    """Class to handle serialization of Numpy types during JSON enconding"""

    def default(self, o):
        """Serialize Numpy types to related python types."""
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, np.bool_):
            return bool(o)
        return super().default(o)


def guess_attribute_display_name(var_name: str) -> str:
    """
    Returns an approximation of an Additional Attribute's display name from its attribute name by converting snake_case
    to PascalCase.
    Ex. sample_attribute_name -> SampleAttributeName
    """
    return var_name.title().replace('_', '')
