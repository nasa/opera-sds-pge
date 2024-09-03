#!/usr/bin/env python3

"""
=================
test_runconfig.py
=================

Unit tests for the pge/runconfig.py module.
"""
import os
import tempfile
import unittest
from os.path import join

from pkg_resources import resource_filename

from yamale import YamaleError

from opera.pge import RunConfig


class RunconfigTestCase(unittest.TestCase):
    """Base test class using unittest"""

    data_dir = None
    test_dir = None

    @classmethod
    def setUpClass(cls) -> None:
        """Initialize class variables for required paths"""
        cls.test_dir = resource_filename(__name__, "")
        cls.data_dir = join(cls.test_dir, os.pardir, os.pardir, "data")
        cls.valid_config_full = join(cls.data_dir, "valid_runconfig_full.yaml")
        cls.valid_config_no_sas = join(cls.data_dir, "valid_runconfig_no_sas.yaml")
        cls.valid_config_extra_fields = join(cls.data_dir, "valid_runconfig_extra_fields.yaml")
        cls.invalid_config = join(cls.data_dir, "invalid_runconfig.yaml")

    def _compare_runconfig_to_expected(self, runconfig):
        """
        Helper method to check the properties of a parsed runconfig against the
        expected values as defined by the "valid" sample runconfig files.
        """
        self.assertEqual(runconfig.name, "OPERA-SAMPLE-PGE-SAS-CONFIG")
        self.assertEqual(runconfig.pge_name, "EXAMPLE_PGE")
        self.assertListEqual(runconfig.input_files, ["input/input_file01.h5", "input/input_file02.h5"])
        self.assertDictEqual(runconfig.ancillary_file_map, {"DEMFile": "input/input_dem.vrt", 'IonosphereFiles': None})
        self.assertEqual(runconfig.output_product_path, "outputs/")
        self.assertEqual(runconfig.scratch_path, "temp/")
        self.assertEqual(runconfig.product_identifier, "EXAMPLE")
        self.assertEqual(runconfig.sas_program_path, "pybind_opera.workflows.example_workflow")
        self.assertListEqual(runconfig.sas_program_options, ["--debug", "--restart"])
        self.assertEqual(runconfig.error_code_base, 100000)
        self.assertEqual(runconfig.sas_schema_path, resource_filename("opera", "test/data/sample_sas_schema.yaml"))
        self.assertEqual(runconfig.iso_template_path, resource_filename("opera", "sample_iso_template.xml.jinja2"))
        self.assertEqual(runconfig.iso_measured_parameter_descriptions, resource_filename("opera", "sample_iso_measured_parameter_descriptions.yaml"))
        self.assertEqual(runconfig.qa_enabled, True)
        self.assertEqual(runconfig.qa_program_path, "/opt/QualityAssurance/sample_qa.py")
        self.assertListEqual(runconfig.qa_program_options, ["--debug"])
        self.assertEqual(runconfig.debug_switch, False)
        self.assertListEqual(runconfig.get_ancillary_filenames(), ["input/input_dem.vrt"])
        self.assertEqual(runconfig.data_validity_start_date, 20010101)

    def test_full_pge_config_parse_and_validate(self):
        """
        Test basic parsing and validation of an input RunConfig that includes
        both the base PGE section and the SAS section.
        """
        # Create a RunConfig with the valid test data
        runconfig = RunConfig(self.valid_config_full)

        # Run validation on the parsed RunConfig, it should succeed
        try:
            runconfig.validate()
        except YamaleError as err:
            self.fail(str(err))

        # Check the properties of the RunConfig to ensure they match as expected
        self.assertEqual(runconfig.filename, self.valid_config_full)
        self._compare_runconfig_to_expected(runconfig)

        # Make sure something was parsed for SAS section, not concerned with
        # the internals though as it's just an example SAS schema being used for
        # this test
        self.assertIsInstance(runconfig.sas_config, dict)

        # Ensure empty ancillary fields are filtered out of list returned
        # from get_ancillary_filenames()
        ancillary_filenames = runconfig.get_ancillary_filenames()

        self.assertIn("input/input_dem.vrt", ancillary_filenames)
        self.assertNotIn(None, ancillary_filenames)

    def test_pge_only_config_parse_and_validate(self):
        """
        Test basic parsing and validation of an input RunConfig that only
        defines a PGE section
        """
        # Create a RunConfig with the valid test data
        runconfig = RunConfig(self.valid_config_no_sas)

        # Run validation on the parsed RunConfig, it should succeed even without
        # a SAS section since its marked required=False
        try:
            runconfig.validate()
        except YamaleError as err:
            self.fail(str(err))

        # Check the properties of the RunConfig to ensure they match as expected
        self.assertEqual(runconfig.filename, self.valid_config_no_sas)
        self._compare_runconfig_to_expected(runconfig)

        # Check that None was assigned for SAS config section
        self.assertIsNone(runconfig.sas_config)

        # Ensure empty ancillary fields are filtered out of list returned
        # from get_ancillary_filenames()
        ancillary_filenames = runconfig.get_ancillary_filenames()

        self.assertIn("input/input_dem.vrt", ancillary_filenames)
        self.assertNotIn(None, ancillary_filenames)

    def test_strict_mode_validation(self):
        """Test validation of a RunConfig with strict_mode both enabled and disabled"""
        # Parse a valid runconfig, but modify it with fields not in the base
        # PGE schema
        runconfig = RunConfig(self.valid_config_extra_fields)

        # Validation should fail due to added RunConfig.Groups.PGE.ExtraTestGroup
        # not present in base PGE schema
        with self.assertRaises(YamaleError):
            runconfig.validate(strict_mode=True)

        # Try validating again with strict_mode disabled, which makes Yamale
        # ignore extra fields
        try:
            runconfig.validate(strict_mode=False)
        except YamaleError as err:
            self.fail(str(err))

    def test_invalid_config_parse_and_validate(self):
        """
        Test validation of an invalid RunConfig to ensure common errors are
        captured.

        """
        # Test with an invalid file that does not conform to minimum standard
        # of a RunConfig (all entries keyed under top-level RunConfig tag)
        with tempfile.NamedTemporaryFile(mode='w', prefix='runconfig_', suffix='.yaml') as outfile:
            outfile.write('runconfig:\n    Name: Invalid RunConfig')
            outfile.flush()

            with self.assertRaises(RuntimeError):
                RunConfig(outfile.name)

        # Now Create a RunConfig with correct format, but invalid or missing
        # values assigned
        runconfig = RunConfig(self.invalid_config)

        try:
            runconfig.validate()
            self.fail()  # Should never get here
        except YamaleError as err:
            # Make sure Yamale caught the errors we expect
            self.assertIn("RunConfig.Groups.PGE.InputFilesGroup.InputFilePaths: 'None' is not a list.", str(err))
            self.assertIn("RunConfig.Groups.PGE.PrimaryExecutable.ProgramPath: Required field missing", str(err))
            self.assertIn("RunConfig.Groups.PGE.PrimaryExecutable.ProgramOptions: '--debug --restart' is not a list.",
                          str(err))
            self.assertIn("RunConfig.Groups.PGE.QAExecutable.ProgramOptions: '--debug' is not a list.", str(err))
            self.assertIn("RunConfig.Groups.PGE.PrimaryExecutable.DataValidityStartDate: '2001-01-01' is "
                          "not a int", str(err))


if __name__ == "__main__":
    unittest.main()
