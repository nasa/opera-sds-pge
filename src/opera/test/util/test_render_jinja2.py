#!/usr/bin/env python

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
=================
test_render_jinja2.py
=================

Unit tests for the util/render_jinja2.py module.
"""
import os
import tempfile
import unittest
import jinja2
from os.path import abspath, join

from pkg_resources import resource_filename

from opera.util.error_codes import ErrorCode

from opera.util.logger import PgeLogger
from opera.util.render_jinja2 import render_jinja2


class RenderJinja2TestCase(unittest.TestCase):
    """Base test class using unittest"""
    starting_dir = None
    working_dir = None
    test_dir = None

    @classmethod
    def setUpClass(cls) -> None:
        """
        Set up directories for testing
        Initialize regular expression
        Initialize other class variables

        """
        cls.starting_dir = abspath(os.curdir)
        cls.test_dir = resource_filename(__name__, "")
        cls.data_dir = join(cls.test_dir, os.pardir, "data")

        os.chdir(cls.test_dir)
        cls.logger = PgeLogger()

    @classmethod
    def tearDownClass(cls) -> None:
        """
        At completion re-establish starting directory
        -------
        """
        os.chdir(cls.starting_dir)

    def setUp(self) -> None:
        """
        Use the temporary directory as the working directory
        -------
        """
        self.working_dir = tempfile.TemporaryDirectory(
            prefix="test_met_file_", suffix='_temp', dir=os.curdir
        )
        os.chdir(self.working_dir.name)

    def tearDown(self) -> None:
        """
        Return to starting directory
        -------
        """
        os.chdir(self.test_dir)
        self.working_dir.cleanup()

    def get_data(self):
        data = {
            "movies": [
                {
                    "title": 'Terminator',
                    "description": 'A soldier is sent back in time to protect an important woman from a killing android.'
                },
                {
                    "title": 'The Sandlot',
                    "description": 'Boys have a magical summer of baseball and discovery.'
                },
                {
                    "title": 'The Lion King',
                    "description": 'A young lion prince is born in Africa.'
                }
            ]
        }
        return data

    def remove_key(self, movie_dict, key):
        """
        Remove all passed 'key' from dictionary

        Returns
        -------
        movie_dict : dict
            The modified dictionary
        """

        for entry in movie_dict['movies']:
            entry.pop(key)

    def testRenderJinja2(self):
        """
        Use a simple template to test the basic functionality of the module.
        Test the 'dunder functions defined in the LoggingUndefined class
        Test that the proper substitutions are made in the rendered html file
        -------

        """

        self.logger.write('info', "opera_pge", 0, 'Dummy entry in log')

        template_file = join(self.data_dir, 'render_jinja_test_template.html')

        data = self.get_data()
        # run with a logger
        render_jinja2(template_file, data['movies'], 'test.html', self.logger)
        # Write test.html into a string
        with open('test.html', 'r') as html_file:
            file_str = html_file.read().rstrip()
        # Verify the titles were properly added to the html file
        self.assertIn('Terminator', file_str)
        self.assertIn('The Sandlot', file_str)
        self.assertIn('The Lion King', file_str)
        # Verify the descriptions were properly added into the html file
        self.assertIn('A soldier is sent back in time to protect an important woman from a killing android.', file_str)
        self.assertIn('Boys have a magical summer of baseball and discovery.', file_str)
        self.assertIn('A young lion prince is born in Africa.', file_str)

        # run without a logger
        render_jinja2(template_file, data['movies'], 'test.html')
        # Write test.html into a string
        with open('test.html', 'r') as html_file:
            file_str = html_file.read().rstrip()
        # Verify the titles were properly added to the html file
        self.assertIn('Terminator', file_str)
        self.assertIn('The Sandlot', file_str)
        self.assertIn('The Lion King', file_str)
        # Verify the descriptions were properly added into the html file
        self.assertIn('A soldier is sent back in time to protect an important woman from a killing android.', file_str)
        self.assertIn('Boys have a magical summer of baseball and discovery.', file_str)
        self.assertIn('A young lion prince is born in Africa.', file_str)

        # Remove the title fields and verify the '!Not Found! is returned
        new_data = self.get_data()
        self.remove_key(new_data, 'title')

        render_jinja2(template_file, new_data['movies'], 'test.html', self.logger)
        # Write test.html into a string
        with open('test.html', 'r') as html_file:
            file_str = html_file.read().rstrip()
        self.assertIn('!Not found!', file_str)
        # Verify the log has been updated.
        stream = self.logger.get_stream_object()
        self.assertIn('Missing/undefined ISO metadata template variable:', stream.getvalue())

        # Run again without a logger and expect a KeyError
        new_data = self.get_data()
        self.remove_key(new_data, 'title')
        render_jinja2(template_file, new_data['movies'], 'test.html')
        self.assertRaises(KeyError)