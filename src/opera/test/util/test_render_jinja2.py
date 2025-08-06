#!/usr/bin/env python

"""
=====================
test_render_jinja2.py
=====================

Unit tests for the util/render_jinja2.py module.
"""
import os
import shutil
import tempfile
import unittest
from glob import glob
from os.path import abspath, join

from importlib.resources import files

from opera.util.logger import PgeLogger
from opera.util.render_jinja2 import JSON_VALIDATOR, render_jinja2, UNDEFINED_ERROR, XML_VALIDATOR, YAML_VALIDATOR


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
        cls.test_dir = str(files(__name__))
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
            prefix="test_met_file_", suffix='_temp', dir=os.path.abspath(os.curdir)
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
        """
        Returns a "movie" dictionary as the test data
        -------

        """
        data = {
            "movies": [
                {
                    "title": 'Terminator',
                    "description": 'A soldier is sent back in time to protect an important '
                                   'woman from a killing android.'
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
        rendered_text = render_jinja2(template_file, data, self.logger, validator=None)
        # Verify the titles were properly added to the html file
        self.assertIn('Terminator', rendered_text)
        self.assertIn('The Sandlot', rendered_text)
        self.assertIn('The Lion King', rendered_text)
        # Verify the descriptions were properly added into the html file
        self.assertIn('A soldier is sent back in time to protect an important woman from a killing android.',
                      rendered_text)
        self.assertIn('Boys have a magical summer of baseball and discovery.', rendered_text)
        self.assertIn('A young lion prince is born in Africa.', rendered_text)

        # run without a logger
        rendered_text = render_jinja2(template_file, data, validator=None)
        # Verify the titles were properly added to the html file
        self.assertIn('Terminator', rendered_text)
        self.assertIn('The Sandlot', rendered_text)
        self.assertIn('The Lion King', rendered_text)
        # Verify the descriptions were properly added into the html file
        self.assertIn('A soldier is sent back in time to protect an important woman from a killing android.',
                      rendered_text)
        self.assertIn('Boys have a magical summer of baseball and discovery.', rendered_text)
        self.assertIn('A young lion prince is born in Africa.', rendered_text)
        # Move a template with another name into the temp directory.
        shutil.copy(template_file, join(os.getcwd(), 'render_jinja_test_template_2.html'))
        # Verify that os.getcmd() is used to find the new template.
        render_jinja2('render_jinja_test_template_2.html', data, validator=None)

        # Remove the title fields and verify the UNDEFINED_ERROR constant is returned
        new_data = self.get_data()
        self.remove_key(new_data, 'title')

        rendered_text = render_jinja2(template_file, new_data, self.logger, validator=None)
        self.assertIn(UNDEFINED_ERROR, rendered_text)
        # Verify the log has been updated.
        stream = self.logger.get_stream_object()
        self.assertIn('Missing/undefined ISO metadata template variable:', stream.getvalue())

        # Run again without a logger and expect a KeyError
        new_data = self.get_data()
        self.remove_key(new_data, 'title')
        render_jinja2(template_file, new_data, validator=None)
        self.assertRaises(KeyError)

    def testRenderJinja2ValidateJSON(self):
        template_file = join(self.data_dir, 'render_jinja_json_test_template.json.jinja2')
        logger = PgeLogger()

        # Test for valid JSON
        rendered_text = render_jinja2(
            template_file,
            {'foo': {'bar': '"bar"'}},
            logger,
            self.working_dir.name,
            validator=JSON_VALIDATOR
        )

        # Test for invalid JSON
        with self.assertRaises(RuntimeError):
            rendered_text = render_jinja2(
                template_file,
                {'foo': {'bar': '"bar'}},
                logger,
                self.working_dir.name,
                validator=JSON_VALIDATOR
            )

        log_file = logger.get_file_name()

        with open(log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn(
            'Failed to render jinja2 template. Err: "Invalid control character at: line 2 column 14 (char 15)" @ 2:14.',
            log_contents
        )

        self.assertEqual(
            len(glob(join(self.working_dir.name, 'bad_json_*.json'))),
            1
        )

    def testRenderJinja2ValidateYAML(self):
        template_file = join(self.data_dir, 'render_jinja_yaml_test_template.yaml.jinja2')
        logger = PgeLogger()

        # Test for valid YAML
        rendered_text = render_jinja2(
            template_file,
            {'foo': {'bar': 'bar'}},
            logger,
            self.working_dir.name,
            validator=YAML_VALIDATOR
        )

        # Test for invalid YAML
        with self.assertRaises(RuntimeError):
            rendered_text = render_jinja2(
                template_file,
                {'foo': {'bar': ' : bar'}},
                logger,
                self.working_dir.name,
                validator=YAML_VALIDATOR
            )

        log_file = logger.get_file_name()

        with open(log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn(
            'Failed to render jinja2 template. Err: "mapping values are not allowed here" @ 2:8.',
            log_contents
        )

        self.assertEqual(
            len(glob(join(self.working_dir.name, 'bad_yaml_*.yaml'))),
            1
        )

    def testRenderJinja2ValidateXML(self):
        template_file = join(self.data_dir, 'render_jinja_xml_test_template.xml.jinja2')
        logger = PgeLogger()

        # Test for valid XML
        rendered_text = render_jinja2(
            template_file,
            {'foo': {'bar': 'http://example.com?foo=foo&amp;bar=bar'}},
            logger,
            self.working_dir.name,
            validator=XML_VALIDATOR
        )

        # Test for invalid XML
        with self.assertRaises(RuntimeError):
            rendered_text = render_jinja2(
                template_file,
                {'foo': {'bar': 'http://example.com?foo=foo&bar=bar'}},
                logger,
                self.working_dir.name,
                validator=XML_VALIDATOR
            )

        log_file = logger.get_file_name()

        with open(log_file, 'r', encoding='utf-8') as infile:
            log_contents = infile.read()

        self.assertIn(
            'Failed to render jinja2 template. Err: "EntityRef: expecting \';\', line 3, column 40" @ 3:40.',
            log_contents
        )

        self.assertEqual(
            len(glob(join(self.working_dir.name, 'bad_xml_*.xml'))),
            1
        )
