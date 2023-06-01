#!/usr/bin/env python

"""
=================
test_input_validation.py
=================

Unit tests for the util/input_validation.py module.
"""
import os
import tempfile
import unittest
from os.path import abspath, exists, getsize

from pkg_resources import resource_filename

from opera.util.input_validation import validate_disp_inputs
from opera.util.logger import PgeLogger

class MockRunConfig:
    """Mock runconfig for testing"""

    def __init__(self, sas_config):
        self._sas_config_dict = sas_config

    @property
    def sas_config(self):
        return self._sas_config_dict

class InputValidationTestCase(unittest.TestCase):
    """Base test class using unittest"""

    starting_dir = None
    working_dir = None
    test_dir = None
    logger = None

    @classmethod
    def setUpClass(cls) -> None:
        """
        Set up directories for testing
        Initialize other class variables

        """
        cls.starting_dir = abspath(os.curdir)
        cls.test_dir = resource_filename(__name__, "")

        os.chdir(cls.test_dir)

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
            prefix="test_input_validation_", suffix='_temp', dir=os.curdir
        )
        os.chdir(self.working_dir.name)

    def tearDown(self) -> None:
        """
        Return to starting directory
        -------
        """
        os.chdir(self.test_dir)
        self.working_dir.cleanup()

    def test_validate_disp_inputs(self):
        """
        """

        # Test non-existent file detection
        test_filename = 'non_existent_input_file'
        sas_config = {
            'runconfig' : {
                'groups' : {
                    'input_file_group' : {
                        'cslc_file_list' : [
                            test_filename
                        ]
                    }
                }
            }
        }
        runconfig = MockRunConfig(sas_config)
        logger = PgeLogger()
        with self.assertRaises(RuntimeError):
            validate_disp_inputs(runconfig, logger, "DISP-S1")

        # Check to see that the RuntimeError is as expected
        logger.close_log_stream()
        log_file = logger.get_file_name()
        self.assertTrue(exists(log_file))
        with open(log_file, 'r', encoding='utf-8') as lfile:
            log = lfile.read()
        self.assertIn(f'Could not locate specified input {test_filename}.', log)
        
        # Test invalid file extension
        logger = PgeLogger()
        test_filename = "test invalid extension.inv"
        with open(test_filename, 'w') as ief:
            ief.write("\n")
        sas_config['runconfig']['groups']['input_file_group']['cslc_file_list'] = [test_filename]
        runconfig = MockRunConfig(sas_config)
        with self.assertRaises(RuntimeError):
            validate_disp_inputs(runconfig, logger, "DISP-S1")

        # Check to see that the RuntimeError is as expected
        logger.close_log_stream()
        log_file = logger.get_file_name()
        self.assertTrue(exists(log_file))
        with open(log_file, 'r', encoding='utf-8') as lfile:
            log = lfile.read()
        self.assertIn(f'Input file {test_filename} does not have an expected file extension', log)
        os.remove(test_filename)

        # Test for non-zero file size
        logger = PgeLogger()
        test_filename = "zero size file.h5"
        open(test_filename, 'w').close()
        self.assertTrue(exists(test_filename))
        sas_config['runconfig']['groups']['input_file_group']['cslc_file_list'] = [test_filename]
        runconfig = MockRunConfig(sas_config)
        with self.assertRaises(RuntimeError):
            validate_disp_inputs(runconfig, logger, "DISP-S1")

        # Check to see that the RuntimeError is as expected
        logger.close_log_stream()
        log_file = logger.get_file_name()
        self.assertTrue(exists(log_file))
        with open(log_file, 'r', encoding='utf-8') as lfile:
            log = lfile.read()
        self.assertIn(f'Input file {test_filename} size is 0. Size must be greater than 0.', log)
        os.remove(test_filename)

        # Test all input files with valid files
        cslc_file_list = ['t087_185678_iw2_20180222_VV.h5', 't087_185687_iw1_20180716_VV.h5']
        for f in cslc_file_list:
            with open(f, 'w') as wf:
                wf.write('\n')
        sas_config['runconfig']['groups']['input_file_group']['cslc_file_list'] = cslc_file_list

        sas_config['runconfig']['groups']['dynamic_ancillary_file_group'] = {}
        amplitude_dispersion_files = ['t087_185678_iw2_amp_dispersion.tif', 't087_185687_iw1_amp_dispersion.tif']
        for f in amplitude_dispersion_files:
            with open(f, 'w') as wf:
                wf.write('\n')
        sas_config['runconfig']['groups']['dynamic_ancillary_file_group']['amplitude_dispersion_files'] = amplitude_dispersion_files

        amplitude_mean_files = ['t087_185678_iw2_amp_mean.tif', 't087_185687_iw1_amp_mean.tif']
        for f in amplitude_mean_files:
            with open(f, 'w') as wf:
                wf.write('\n')
        sas_config['runconfig']['groups']['dynamic_ancillary_file_group']['amplitude_mean_files'] = amplitude_mean_files

        geometry_files = ['t087_185678_iw2_topo.h5', 't087_185687_iw1_topo.h5']
        for f in geometry_files:
            with open(f, 'w') as wf:
                wf.write('\n')
        sas_config['runconfig']['groups']['dynamic_ancillary_file_group']['geometry_files'] = geometry_files

        mask_files = ['water_mask.tif']
        for f in mask_files:
            with open(f, 'w') as wf:
                wf.write('\n')
        sas_config['runconfig']['groups']['dynamic_ancillary_file_group']['mask_file'] = mask_files

        dem_file = 'dem.tif'
        with open(dem_file, 'w') as wf:
            wf.write('\n')
        sas_config['runconfig']['groups']['dynamic_ancillary_file_group']['dem_file'] = dem_file

        tec_files = ['jplg0410.18i.Z', 'jplg1970.18i.Z']
        for f in tec_files:
            with open(f, 'w') as wf:
                wf.write('\n')
        sas_config['runconfig']['groups']['dynamic_ancillary_file_group']['tec_files'] = tec_files

        weather_model_files = ['GMAO_tropo_20180210T000000_ztd.nc', 'GMAO_tropo_20180716T000000_ztd.nc']
        for f in weather_model_files:
            with open(f, 'w') as wf:
                wf.write('\n')
        sas_config['runconfig']['groups']['dynamic_ancillary_file_group']['weather_model_files'] = weather_model_files

        logger = PgeLogger()
        runconfig = MockRunConfig(sas_config)
        # with self.assertRaises(RuntimeError):
        validate_disp_inputs(runconfig, logger, "DISP-S1")

        logger.close_log_stream()
        log_file = logger.get_file_name()
        self.assertTrue(exists(log_file))
        with open(log_file, 'r', encoding='utf-8') as lfile:
            log = lfile.read()
        print("begin log contents")
        print(log)
        print("end log contents")
        self.assertIn('overall.log_messages.debug: 0', log)
        self.assertIn('overall.log_messages.info: 0', log)
        self.assertIn('overall.log_messages.warning: 0', log)
        self.assertIn('overall.log_messages.critical: 0', log)

        files_to_remove = (cslc_file_list + amplitude_dispersion_files +
                          amplitude_mean_files + geometry_files + mask_files +
                          tec_files + weather_model_files)
        files_to_remove.append(dem_file)
        for f in files_to_remove:
            os.remove(f)
