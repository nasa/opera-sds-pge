#!/usr/bin/env python3

"""
================
render_jinja2.py
================

Helper function(s) to render a Jinja2-based template.

Original Author: David White
Adapted by: Jim Hofman
"""

import json
import numpy as np
import os
import re
import jinja2

from opera.util.error_codes import ErrorCode
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

        def _fail_with_undefined_error(self, *args, **kwargs):   # pragma no cover
            _log_message(self)

        def __str__(self):
            _log_message(self)
            return UNDEFINED_ERROR

        def __iter__(self):   # pragma no cover
            _log_message(self)
            return super().__iter__()

        def __bool__(self):   # pragma no cover
            _log_message(self)
            return super().__bool__()

        def __getattr__(self, name):
            _log_message(self)
            return super().__getattr__(name)

    return LoggingUndefined


def render_jinja2(template_filename: str, input_data: dict, logger: PgeLogger = None):
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

    return rendered_text


def python_type_to_xml_type(obj) -> str:
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
    return var_name.title().replace('_', '')

