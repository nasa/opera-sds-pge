#!/usr/bin/env python

"""
======================
test_metadata_utils.py
======================

Unit tests for the util/metadata_utils.py module.

"""

import h5py
import tempfile
import numpy as np
import os
import unittest
from unittest import skipIf

from opera.util.metadata_utils import get_geographic_boundaries_from_mgrs_tile
from opera.util.metadata_utils import get_rtc_s1_product_metadata


def osr_is_available():
    """
    Helper function to check for a local installation of the Python bindings for
    the Geospatial Data Abstraction Library (GDAL).
    Used to skip tests that require GDAL if it is not available.
    """
    try:
        from osgeo import osr  # noqa: F401
        return True
    except (ImportError, ModuleNotFoundError):
        return False


def create_test_rtc_nc_product(file_path):
    """Creates a dummy RTC NetCDF product with expected metadata fields"""
    with h5py.File(file_path, 'w') as f:
        frequencyA_grp = f.create_group("/science/CSAR/RTC/grids/frequencyA")
        centerFrequency_dset = frequencyA_grp.create_dataset("centerFrequency", data=5405000454.33435, dtype='float64')
        centerFrequency_dset.attrs['description'] = np.string_("Center frequency of the processed image in Hz")
        xCoordinateSpacing_dset = frequencyA_grp.create_dataset("xCoordinateSpacing", data=30.0, dtype='float64')
        xCoordinates_dset = frequencyA_grp.create_dataset("xCoordinates", data=np.zeros((10,)), dtype='float64')
        yCoordinateSpacing_dset = frequencyA_grp.create_dataset("yCoordinateSpacing", data=30.0, dtype='float64')
        yCoordinates_dset = frequencyA_grp.create_dataset("yCoordinates", data=np.zeros((10,)), dtype='float64')
        listOfPolarizations_dset = frequencyA_grp.create_dataset("listOfPolarizations", data=np.array([b'VV', b'VH']))
        rangeBandwidth_dset = frequencyA_grp.create_dataset('rangeBandwidth', data=56500000.0, dtype='float64')
        azimuthBandwidth_dset = frequencyA_grp.create_dataset('azimuthBandwidth', data=56500000.0, dtype='float64')
        slantRangeSpacing_dset = frequencyA_grp.create_dataset('slantRangeSpacing', data=2.32956, dtype='float64')
        zeroDopplerTimeSpacing_dset = frequencyA_grp.create_dataset('zeroDopplerTimeSpacing', data=0.002055, dtype='float64')
        faradayRotationFlag_dset = frequencyA_grp.create_dataset('faradayRotationFlag', data=True, dtype='bool')
        noiseCorrectionFlag_dset = frequencyA_grp.create_dataset('noiseCorrectionFlag', data=True, dtype='bool')
        polarizationOrientationFlag_dset = frequencyA_grp.create_dataset('polarizationOrientationFlag', data=True, dtype='bool')
        radiometricTerrainCorrectionFlag_dset = frequencyA_grp.create_dataset('radiometricTerrainCorrectionFlag', data=True, dtype='bool')

        orbit_grp = f.create_group("/science/CSAR/RTC/metadata/orbit")
        orbitType_dset = orbit_grp.create_dataset("orbitType", data=b'POE')

        processingInformation_inputs_grp = f.create_group("/science/CSAR/RTC/metadata/processingInformation/inputs")
        demFiles_dset = processingInformation_inputs_grp.create_dataset("demFiles", data=np.array([b'dem.tif']))
        auxcalFiles = np.array([b'calibration-s1b-iw1-slc-vv-20180504t104508-20180504t104533-010770-013aee-004.xml',
                                b'noise-s1b-iw1-slc-vv-20180504t104508-20180504t104533-010770-013aee-004.xml'])
        auxcalFiles_dset = processingInformation_inputs_grp.create_dataset("auxcalFiles", data=auxcalFiles)
        configFiles_dset = processingInformation_inputs_grp.create_dataset("configFiles", data=b'rtc_s1.yaml')
        l1SlcGranules = np.array([b'S1B_IW_SLC__1SDV_20180504T104507_20180504T104535_010770_013AEE_919F.zip'])
        l1SlcGranules_dset = processingInformation_inputs_grp.create_dataset("l1SlcGranules", data=l1SlcGranules)
        orbitFiles = np.array([b'S1B_OPER_AUX_POEORB_OPOD_20180524T110543_V20180503T225942_20180505T005942.EOF'])
        orbitFiles_dset = processingInformation_inputs_grp.create_dataset("orbitFiles", data=orbitFiles)

        processingInformation_algorithms_grp = f.create_group(
            "/science/CSAR/RTC/metadata/processingInformation/algorithms")
        demInterpolation_dset = processingInformation_algorithms_grp.create_dataset("demInterpolation", data=b'biquintic')
        geocoding_dset = processingInformation_algorithms_grp.create_dataset("geocoding", data=b'area_projection')
        radiometricTerrainCorrection_dset = processingInformation_algorithms_grp.create_dataset("radiometricTerrainCorrection", data=b'area_projection')
        isceVersion_dset = processingInformation_algorithms_grp.create_dataset("ISCEVersion", data=b'0.8.0-dev')

        identification_grp = f.create_group("/science/CSAR/identification")
        absoluteOrbitNumber_dset = identification_grp.create_dataset("absoluteOrbitNumber", data=10770, dtype='int64')
        diagnosticModeFlag_dset = identification_grp.create_dataset("diagnosticModeFlag", data=False, dtype='bool')
        isGeocodedFlag = identification_grp.create_dataset("isGeocoded", data=True, dtype='bool')
        isUrgentObservation_dset = identification_grp.create_dataset("isUrgentObservation", data=np.array([False, True]), dtype='bool')
        lookDirection_dset = identification_grp.create_dataset("lookDirection", data=b'Right')
        listOfFrequencies_dset = identification_grp.create_dataset("listOfFrequencies", data=np.array([b'A']))
        missionId_dest = identification_grp.create_dataset("missionId", data=b'S1B')
        orbitPassDirection_dset = identification_grp.create_dataset("orbitPassDirection", data=b'Descending')
        plannedDatatakeId_dset = identification_grp.create_dataset("plannedDatatakeId", data=np.array([b'datatake1', b'datatake2']))
        plannedObservationId_dset = identification_grp.create_dataset("plannedObservationId", data=np.array([b'obs1', b'obs2']))
        processingType_dset = identification_grp.create_dataset("processingType", data=b'UNDEFINED')
        productType_dset = identification_grp.create_dataset("productType", data=b'SLC')
        productVersion_dset = identification_grp.create_dataset("productVersion", data=b'1.0')
        trackNumber_dset = identification_grp.create_dataset("trackNumber", data=147170, dtype='int64')
        zeroDopplerEndTime_dset = identification_grp.create_dataset("zeroDopplerEndTime", data=b'2018-05-04T10:45:11.501279')
        zeroDopplerStartTime_dset = identification_grp.create_dataset("zeroDopplerStartTime", data=b'2018-05-04T10:45:08.436445')


class MetadataUtilsTestCase(unittest.TestCase):
    """Unit test Metadata Utilities"""

    @skipIf(not osr_is_available(), reason="osgeo.osr is not installed on the local instance")
    def test_get_geographic_boundaries_from_mgrs_tile_nominal(self):
        """Reproduce ADT results from values provided with code"""
        lat_min, lat_max, lon_min, lon_max = get_geographic_boundaries_from_mgrs_tile('15SXR')

        self.assertAlmostEqual(lat_min, 31.616027943130398)
        self.assertAlmostEqual(lat_max, 32.6212369766609)
        self.assertAlmostEqual(lon_min, -91.94552881416524)
        self.assertAlmostEqual(lon_max, -90.76425651871281)

    @skipIf(not osr_is_available(), reason="osgeo.osr is not installed on the local instance")
    def test_get_geographic_boundaries_from_mgrs_tile_leading_T(self):
        """Test MGRS tile code conversion when code starts with T"""
        lat_min, lat_max, lon_min, lon_max = get_geographic_boundaries_from_mgrs_tile('T15SXR')

        self.assertAlmostEqual(lat_min, 31.616027943130398)
        self.assertAlmostEqual(lat_max, 32.6212369766609)
        self.assertAlmostEqual(lon_min, -91.94552881416524)
        self.assertAlmostEqual(lon_max, -90.76425651871281)

    @skipIf(not osr_is_available(), reason="osgeo.osr is not installed on the local instance")
    def test_get_geographic_boundaries_from_mgrs_tile_invalid_tile(self):
        """Test MGRS tile code conversion with an invalid code"""
        self.assertRaises(RuntimeError, get_geographic_boundaries_from_mgrs_tile, 'X15SXR')

    def test_get_rtc_s1_product_metadata(self):
        """Test retrieval of product metadata from HDF5 files"""
        file_name = os.path.join(tempfile.gettempdir(), "test_metadata_file.hdf5")
        create_test_rtc_nc_product(file_name)

        try:
            product_output = get_rtc_s1_product_metadata(file_name)

            self.assertAlmostEqual(product_output['frequencyA']['centerFrequency'], 5405000454.33435)
            self.assertEqual(product_output['orbit']['orbitType'], "POE")
            self.assertEqual(product_output['processingInformation']['inputs']['demFiles'], ['dem.tif'])
            for po,eo in zip(product_output['processingInformation']['inputs']['auxcalFiles'],
                             ['calibration-s1b-iw1-slc-vv-20180504t104508-20180504t104533-010770-013aee-004.xml',
                              'noise-s1b-iw1-slc-vv-20180504t104508-20180504t104533-010770-013aee-004.xml']):
                self.assertEqual(po, eo)
            self.assertEqual(product_output['processingInformation']['algorithms']['geocoding'], 'area_projection')
            self.assertEqual(product_output['identification']['trackNumber'], 147170)

        finally:
            os.remove(file_name)


if __name__ == "__main__":
    unittest.main()
