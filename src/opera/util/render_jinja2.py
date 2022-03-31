#
# Copyright 2022, by the California Institute of Technology.
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
================
render_jinja2.py
================

Helper function(s) to render a Jinja2-based template.

Original Author: David White
Adapted by: Jim Hofman
"""
import os

import jinja2

from opera.util.error_codes import ErrorCode
from opera.util.logger import PgeLogger


def _make_undefined_handler_class(logger: PgeLogger):
    """
    Factory function, returns a child class of the jinja2.Undefined class for
    use when rendering templates.
    The intent is to override the default behavior which can raise an exception
    while rendering Jinja2 templates if there is a failure to render a
    template variable. Instead:
        log the error the PGE way (using the PgeLogger class)
        put "!Not found!" in the rendered text
        let the template rendering continue, try to render the rest of the template.

    Parameters
    ----------
    logger : PgeLogger
        logger of the current pge instance

    Returns
    -------
    LoggingUndefined : class
        child class of the jinja2.Undefined class, used to avoid exception handling.
        Allows 'not found' to be added to the rendered text


    """

    def _log_message(undef):
        """Notes missing/undefined ISO metadate template variable in logger.

        Parameters
        ----------
        undef : object

        """
        msg = f"Missing/undefined ISO metadata template variable: {undef._undefined_message}"
        logger.log("render_jinja2", ErrorCode.ISO_METADATA_CANT_RENDER_ONE_VARIABLE, msg)

    class LoggingUndefined(jinja2.Undefined):
        """Override the default behavior which can raise an exception"""

        def _fail_with_undefined_error(self, *args, **kwargs):
            _log_message(self)

        def __str__(self):
            _log_message(self)
            return "!Not found!"

        def __iter__(self):
            _log_message(self)
            return super().__iter__()

        def __bool__(self):
            _log_message(self)
            return super().__bool__()

        def __getattr__(self, name):
            _log_message(self)
            return super().__getattr__(name)

    return LoggingUndefined


def render_jinja2(template_filename: str, input_data: dict,
                  logger: PgeLogger = None):
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

    if logger is not None:
        undefined_handler_class = _make_undefined_handler_class(logger)
    else:
        undefined_handler_class = jinja2.Undefined

    template_env = jinja2.Environment(loader=template_loader,
                                      autoescape=jinja2.select_autoescape(),
                                      undefined=undefined_handler_class)

    template = template_env.get_template(template_filename)

    rendered_text = template.render(input_data)

    return rendered_text
