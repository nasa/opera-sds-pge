#!/usr/bin/env python3

"""
=============
mock_utils.py
=============

Utilities used to simulate extensive libraries, such as the Geospatial Data
Abstraction Library (GDAL), which may not be present in all environments

"""

from copy import deepcopy
from os.path import exists

import mgrs


class MockGdal:  # pragma: no cover
    """
    Mock class for the osgeo.gdal module.

    This class is defined so the opera-sds-pge project does not require the
    Geospatial Data Abstraction Library (GDAL) as an explicit dependency for
    developers. When PGE code is eventually run from within a Docker container,
    osgeo.gdal should always be installed and importable.

    """

    # pylint: disable=all
    class MockDSWxHLSGdalDataset:
        """Mock class for gdal.Dataset objects, as returned from an Open call."""

        def __init__(self):
            self.dummy_metadata = {
                'ACCODE': 'LaSRC', 'AEROSOL_CLASS_REMAPPING_ENABLED': 'TRUE',
                'AEROSOL_NOT_WATER_TO_HIGH_CONF_WATER_FMASK_VALUES': '224,160,96',
                'AEROSOL_PARTIAL_SURFACE_AGGRESSIVE_TO_HIGH_CONF_WATER_FMASK_VALUES': '224,192,160,128,96',
                'AEROSOL_PARTIAL_SURFACE_WATER_CONSERVATIVE_TO_HIGH_CONF_WATER_FMASK_VALUES': '224,192,160,128,96',
                'AEROSOL_WATER_MODERATE_CONF_TO_HIGH_CONF_WATER_FMASK_VALUES': '224,160,96',
                'AREA_OR_POINT': 'Area', 'CLOUD_COVERAGE': '43',
                'DEM_COVERAGE': 'FULL', 'DEM_SOURCE': 'dem.tif',
                'FOREST_MASK_LANDCOVER_CLASSES': '20,50,111,113,115,116,121,123,125,126',
                'HLS_DATASET': 'HLS.L30.T22VEQ.2021248T143156.v2.0',
                'INPUT_HLS_PRODUCT_CLOUD_COVERAGE': '4',
                'INPUT_HLS_PRODUCT_SPATIAL_COVERAGE': '84',
                'LANDCOVER_COVERAGE': 'FULL', 'LANDCOVER_SOURCE': 'landcover.tif',
                'MASK_ADJACENT_TO_CLOUD_MODE': 'mask',
                'MAX_SUN_LOCAL_INC_ANGLE': '40',
                'MEAN_SUN_AZIMUTH_ANGLE': '145.002203258435',
                'MEAN_SUN_ZENITH_ANGLE': '30.7162834439185',
                'MEAN_VIEW_AZIMUTH_ANGLE': '100.089770731169',
                'MEAN_VIEW_ZENITH_ANGLE': '4.6016561116873',
                'MIN_SLOPE_ANGLE': '-5',
                'NBAR_SOLAR_ZENITH': '31.7503071022442',
                'OCEAN_MASKING_ENABLED': 'FALSE',
                'OCEAN_MASKING_SHORELINE_DISTANCE_KM': 'NOT_USED',
                'PROCESSING_DATETIME': '2022-01-31T21:54:26',
                'PRODUCT_ID': 'dswx_hls', 'PRODUCT_LEVEL': '3',
                'PRODUCT_SOURCE': 'HLS', 'PRODUCT_TYPE': 'DSWx-HLS',
                'PRODUCT_VERSION': '0.1', 'PROJECT': 'OPERA',
                'SENSING_TIME': '2021-09-05T14:31:56.9300799Z; 2021-09-05T14:32:20.8126470Z',
                'SENSOR': 'MSI',
                'SENSOR_PRODUCT_ID': 'S2A_MSIL1C_20210907T163901_N0301_R126_T15SXR_20210907T202434.SAFE',
                'SHADOW_MASKING_ALGORITHM': 'SUN_LOCAL_INC_ANGLE',
                'SHORELINE_SOURCE': 'shoreline.shp', 'SOFTWARE_VERSION': '0.1',
                'SPACECRAFT_NAME': 'Sentinel-2A', 'SPATIAL_COVERAGE': '99',
                'SPATIAL_COVERAGE_EXCLUDING_MASKED_OCEAN': '99',
                'WORLDCOVER_COVERAGE': 'FULL',
                'WORLDCOVER_SOURCE': 'worldcover.tif',
            }

        def GetMetadata(self):
            """
            Returns a subset of dummy metadata expected by the PGE.
            This function should be updated as needed for requisite metadata fields.
            """
            return deepcopy(self.dummy_metadata)

    # pylint: disable=all
    class MockRtcS1GdalDataset:
        """
        Mock class for gdal.Dataset objects, as returned from an Open call.
        For use when mocking metadata from RTC-S1 static layer GeoTIFF products
        """

        def __init__(self):
            self.dummy_metadata = {
                'BOUNDING_BOX': '[200700.0, 9391650.0, 293730.0, 9440880.0]',
                'BOUNDING_BOX_EPSG_CODE': '32718',
                'BOUNDING_BOX_PIXEL_COORDINATE_CONVENTION': 'UPPER LEFT CORNER (ULC)',
                'BURST_ID': "T069-147170-IW1",
            }

        def GetMetadata(self):
            """
            Returns a subset of dummy metadata expected by the PGE.
            This function should be updated as needed for requisite metadata fields.
            """
            return deepcopy(self.dummy_metadata)

    # pylint: disable=all
    class MockDSWxS1GdalDataset:
        """
        Mock class for gdal.Dataset objects, as returned from an Open call.
        DSWx-S1 metadata consists of 4 sections:
            1) Product Identification and Processing Information
            2) Sentinel-1 A/B product metadata.
            3) input ancillary datasets
            4) S1 product metadata
        """

        def __init__(self):
            self.dummy_metadata = {
                'AREA_OR_POINT': 'Area',
                'CONTACT_INFORMATION': 'operasds@jpl.nasa.gov',
                'DSWX_PRODUCT_VERSION': '1.0',
                'INPUT_DEM_SOURCE': 'Copernicus DEM GLO-30 2021 WGS84',
                'INPUT_GLAD_CLASSIFICATION_SOURCE': 'GLAD Global Land Cover 2020',
                'INPUT_HAND_SOURCE': 'ASF HAND GLO30',
                'INPUT_REFERENCE_WATER_SOURCE': 'JRC Global Surface Water - collection from 1984 to 2021',
                'INPUT_SHORELINE_SOURCE': 'NOAA GSHHS Level 1 resolution f - GSHHS_f_L1',
                'INPUT_WORLDCOVER_SOURCE': 'ESA WorldCover 10m 2020 v1.0',
                'INSTITUTION': 'NASA JPL',
                'LAYOVER_SHADOW_COVERAGE': '0.37',
                'MGRS_COLLECTION_ACTUAL_NUMBER_OF_BURSTS': '40',
                'MGRS_COLLECTION_EXPECTED_NUMBER_OF_BURSTS': '40',
                'MGRS_COLLECTION_MISSING_NUMBER_OF_BURSTS': '0',
                'MGRS_POL_MODE': 'DV_POL',
                'POLARIZATION': "['VV', 'VH']",
                'PROCESSING_DATETIME': '2024-07-17T19:40:25Z',
                'PROCESSING_INFORMATION_FILTER': 'bregman',
                'PROCESSING_INFORMATION_FILTER_ENABLED': 'True',
                'PROCESSING_INFORMATION_FILTER_OPTION': "{'lambda': 20}",
                'PROCESSING_INFORMATION_FUZZY_VALUE_AREA': '[0, 40]',
                'PROCESSING_INFORMATION_FUZZY_VALUE_DARK_AREA': '[-18, -24]',
                'PROCESSING_INFORMATION_FUZZY_VALUE_HAND': '[0, 15]',
                'PROCESSING_INFORMATION_FUZZY_VALUE_HIGH_FREQUENT_AREA': '[0.1, 0.9]',
                'PROCESSING_INFORMATION_FUZZY_VALUE_REFERENCE_WATER': '[0.8, 0.95]',
                'PROCESSING_INFORMATION_FUZZY_VALUE_SLOPE': '[0.5, 15]',
                'PROCESSING_INFORMATION_INUNDATED_VEGETATION': 'True',
                'PROCESSING_INFORMATION_INUNDATED_VEGETATION_AREA_DATA_TYPE': 'GLAD',
                'PROCESSING_INFORMATION_INUNDATED_VEGETATION_CROSS_POL_MIN': '-26',
                'PROCESSING_INFORMATION_INUNDATED_VEGETATION_DUAL_POL_RATIO_MAX': '12',
                'PROCESSING_INFORMATION_INUNDATED_VEGETATION_DUAL_POL_RATIO_MIN': '7',
                'PROCESSING_INFORMATION_INUNDATED_VEGETATION_DUAL_POL_RATIO_THRESHOLD': '8',
                'PROCESSING_INFORMATION_INUNDATED_VEGETATION_FILTER': 'lee',
                'PROCESSING_INFORMATION_INUNDATED_VEGETATION_TARGET_CLASS': "['112-124', '200-207', '19-24', "
                                                                            "'125-148', '19']",
                'PROCESSING_INFORMATION_MASKING_ANCILLARY_CO_POL_THRESHOLD': '-14.6',
                'PROCESSING_INFORMATION_MASKING_ANCILLARY_CROSS_POL_THRESHOLD': '-22.8',
                'PROCESSING_INFORMATION_MASKING_ANCILLARY_WATER_THRESHOLD': '0.05',
                'PROCESSING_INFORMATION_REFINE_BIMODALITY_MINIMUM_PIXEL': '4',
                'PROCESSING_INFORMATION_REFINE_BIMODALITY_THRESHOLD': '[1.5, 0.97, 0.7, 0.1]',
                'PROCESSING_INFORMATION_REGION_GROWING_INITIAL_SEED': '0.81',
                'PROCESSING_INFORMATION_REGION_GROWING_RELAXED_THRESHOLD': '0.51',
                'PROCESSING_INFORMATION_THRESHOLDING': 'Kittler-Illingworth',
                'PROCESSING_INFORMATION_THRESHOLD_BIMODALITY': '0.7',
                'PROCESSING_INFORMATION_THRESHOLD_BOUNDS': '[[-28, -11], [-28, -18]]',
                'PROCESSING_INFORMATION_THRESHOLD_MULTI_THRESHOLD': 'True',
                'PROCESSING_INFORMATION_THRESHOLD_TILE_AVERAGE': 'True',
                'PROCESSING_INFORMATION_THRESHOLD_TILE_SELECTION': "['chini', 'bimodality']",
                'PROCESSING_INFORMATION_THRESHOLD_TWELE': '[0.09, 0.8, 0.97]',
                'PRODUCT_LEVEL': '3',
                'PRODUCT_SOURCE': 'OPERA_RTC_S1',
                'PRODUCT_TYPE': 'DSWx-S1',
                'PROJECT': 'OPERA',
                'RTC_ABSOLUTE_ORBIT_NUMBER': '51636',
                'RTC_BURST_ID': 't114_243013_iw1, t114_243014_iw1, t114_243015_iw1, t114_243016_iw1',
                'RTC_INPUT_L1_SLC_GRANULES': 'S1A_IW_SLC__1SDV_20231213T121214_20231213T121243_051636_063C28_8D5C.zip',
                'RTC_INPUT_LIST':
                    "['OPERA_L2_RTC-S1_T114-243016-IW1_20231213T121235Z_20231213T184607Z_S1A_30_v1.0_VV.tif', "
                    "'OPERA_L2_RTC-S1_T114-243015-IW1_20231213T121233Z_20231213T184607Z_S1A_30_v1.0_VV.tif', "
                    "'OPERA_L2_RTC-S1_T114-243013-IW1_20231213T121227Z_20231213T184607Z_S1A_30_v1.0_VV.tif', "
                    "'OPERA_L2_RTC-S1_T114-243014-IW1_20231213T121230Z_20231213T184607Z_S1A_30_v1.0_VV.tif']",
                'RTC_ORBIT_PASS_DIRECTION': 'ascending',
                'RTC_PRODUCT_VERSION': '1.0',
                'RTC_QA_RFI_INFO_AVAILABLE': 'True',
                'RTC_QA_RFI_NUMBER_OF_BURSTS': '4',
                'RTC_SENSING_END_TIME': '2023-12-13T12:12:39Z',
                'RTC_SENSING_START_TIME': '2023-12-13T12:12:27Z',
                'RTC_TRACK_NUMBER': '114',
                'SENSOR': 'IW',
                'SOFTWARE_VERSION': '1.0',
                'SPACECRAFT_NAME': 'Sentinel-1A/B',
                'SPATIAL_COVERAGE': '0.2502'
            }

        def GetMetadata(self):
            """
            Returns a subset of dummy metadata expected by the PGE.
            This function should be updated as needed for requisite metadata fields.
            """
            return deepcopy(self.dummy_metadata)

    # pylint: disable=all
    class MockDSWxNIGdalDataset:
        """
        Mock class for gdal.Dataset objects, as returned from an Open call.
        For use when mocking metadata from DSWx-NI GeoTIFF products
        """

        def __init__(self):
            self.dummy_metadata = {
                "ABSOLUTE_ORBIT_NUMBER": "[0]",
                "CONTACT_INFORMATION": "operasds@jpl.nasa.gov",
                "DSWX_PRODUCT_VERSION": "0.1",
                "FRAME_NUMBER": "[0]",
                "INPUT_DEM_SOURCE": "Copernicus DEM GLO-30 2021 WGS84",
                "INPUT_GLAD_CLASSIFICATION_SOURCE": "glad.vrt",
                "INPUT_HAND_SOURCE": "ASF HAND GLO30",
                "INPUT_L1_SLC_GRANULES":
                    "['NISAR_L1_PR_RSLC_001_001_A_000_2000_SHNA_A_20240404T075706_20240404T075716_T00888_M_F_J_888.h5',"
                    "'NISAR_L1_PR_RSLC_001_001_A_000_2000_SHNA_A_20240404T075658_20240404T075708_T00888_M_F_J_888.h5']",
                "INPUT_REFERENCE_WATER_SOURCE": "JRC Global Surface Water - collection from 1984 to 2021",
                "INPUT_SHORELINE_SOURCE": "NOT_PROVIDED_OR_NOT_USED",
                "INPUT_WORLDCOVER_SOURCE": "ESA WorldCover 10m 2020 v1.0",
                "INSTITUTION": "NASA JPL",
                "LAYOVER_SHADOW_COVERAGE": "0.0",
                "LOOK_DIRECTION": "['Right']",
                "MGRS_COLLECTION_ACTUAL_NUMBER_OF_FRAMES": "1",
                "MGRS_COLLECTION_EXPECTED_NUMBER_OF_FRAMES": "2",
                "MGRS_COLLECTION_MISSING_NUMBER_OF_FRAMES": "2",
                "MGRS_POL_MODE": "DH_SV_POL",
                "ORBIT_PASS_DIRECTION": "['Ascending']",
                "POLARIZATION": "['HH', 'HV']",
                "PROCESSING_DATETIME": "2025-04-22T20:46:43Z",
                "PROCESSING_INFORMATION_FILTER": "bregman",
                "PROCESSING_INFORMATION_FILTER_ENABLED": "True",
                "PROCESSING_INFORMATION_FILTER_OPTION": "{'lambda': 20}",
                "PROCESSING_INFORMATION_FUZZY_VALUE_AREA": "[0, 40]",
                "PROCESSING_INFORMATION_FUZZY_VALUE_DARK_AREA": "[-18, -24]",
                "PROCESSING_INFORMATION_FUZZY_VALUE_HAND": "[0, 15]",
                "PROCESSING_INFORMATION_FUZZY_VALUE_HIGH_FREQUENT_AREA": "[0.1, 0.9]",
                "PROCESSING_INFORMATION_FUZZY_VALUE_REFERENCE_WATER": "[0.8, 0.95]",
                "PROCESSING_INFORMATION_FUZZY_VALUE_SLOPE": "[0.5, 15]",
                "PROCESSING_INFORMATION_INUNDATED_VEGETATION": "True",
                "PROCESSING_INFORMATION_INUNDATED_VEGETATION_AREA_DATA_TYPE": "GLAD",
                "PROCESSING_INFORMATION_INUNDATED_VEGETATION_CROSS_POL_MIN": "-26",
                "PROCESSING_INFORMATION_INUNDATED_VEGETATION_DUAL_POL_RATIO_MAX": "12",
                "PROCESSING_INFORMATION_INUNDATED_VEGETATION_DUAL_POL_RATIO_MIN": "7",
                "PROCESSING_INFORMATION_INUNDATED_VEGETATION_DUAL_POL_RATIO_THRESHOLD": "8",
                "PROCESSING_INFORMATION_INUNDATED_VEGETATION_FILTER": "lee",
                "PROCESSING_INFORMATION_INUNDATED_VEGETATION_TARGET_CLASS": "['112-124', '200-207', '125-148']",
                "PROCESSING_INFORMATION_MASKING_ANCILLARY_CO_POL_THRESHOLD": "-14.6",
                "PROCESSING_INFORMATION_MASKING_ANCILLARY_CROSS_POL_THRESHOLD": "-22.8",
                "PROCESSING_INFORMATION_MASKING_ANCILLARY_WATER_THRESHOLD": "0.05",
                "PROCESSING_INFORMATION_REFINE_BIMODALITY_MINIMUM_PIXEL": "4",
                "PROCESSING_INFORMATION_REFINE_BIMODALITY_THRESHOLD": "[1.5, 0.97, 0.7, 0.1]",
                "PROCESSING_INFORMATION_REGION_GROWING_INITIAL_SEED": "0.81",
                "PROCESSING_INFORMATION_REGION_GROWING_RELAXED_THRESHOLD": "0.51",
                "PROCESSING_INFORMATION_THRESHOLDING": "Kittler-Illingworth",
                "PROCESSING_INFORMATION_THRESHOLD_BIMODALITY": "0.7",
                "PROCESSING_INFORMATION_THRESHOLD_BOUNDS": "[[-28, -11], [-28, -18]]",
                "PROCESSING_INFORMATION_THRESHOLD_MULTI_THRESHOLD": "True",
                "PROCESSING_INFORMATION_THRESHOLD_TILE_AVERAGE": "True",
                "PROCESSING_INFORMATION_THRESHOLD_TILE_SELECTION": "['chini', 'bimodality']",
                "PROCESSING_INFORMATION_THRESHOLD_TWELE": "[0.09, 0.8, 0.97]",
                "PRODUCT_LEVEL": "3",
                "PRODUCT_SOURCE": "NISAR_GCOV",
                "PRODUCT_TYPE": "DSWx-NI",
                "PRODUCT_VERSION": "['0.1.0']",
                "PROJECT": "OPERA",
                "SENSOR": "LSAR",
                "SOFTWARE_VERSION": "1.1",
                "SPACECRAFT_NAME": "NISAR",
                "SPATIAL_COVERAGE": "30.4512",
                "TRACK_NUMBER": "[0]",
                "ZERO_DOPPLER_END_TIME": "['2024-04-04T07:57:08.314230', '2024-04-04T07:57:16.416542']",
                "ZERO_DOPPLER_START_TIME": "['2024-04-04T07:57:06.415452', '2024-04-04T07:56:58.313688']",
                "AREA_OR_POINT": "Area"
            }

        def GetMetadata(self):
            """
            Returns a subset of dummy metadata expected by the PGE.
            This function should be updated as needed for requisite metadata fields.
            """
            return deepcopy(self.dummy_metadata)

    class MockDistS1GdalDataset:
        """
        Mock class for gdal.Dataset objects, as returned from an Open call.
        For use when mocking metadata from DIST-S1 GeoTIFF products
        """

        def __init__(self):
            self.dummy_metadata = {
                'apply_water_mask': 'False',
                'bucket': 'None',
                'dst_dir': '/home/ops/scratch_dir',
                'high_confidence_threshold': '5.5',
                'memory_strategy': 'high',
                'mgrs_tile_id': '10SGD',
                'moderate_confidence_threshold': '3.5',
                'n_lookbacks': '3',
                'n_workers_for_despeckling': '5',
                'post_rtc_opera_ids': 'OPERA_L2_RTC-S1_T137-292318-IW1_20250102T015857Z_20250102T190143Z_S1A_30_v1.0,'
                                      'OPERA_L2_RTC-S1_T137-292318-IW2_20250102T015858Z_20250102T190143Z_S1A_30_v1.0,'
                                      'OPERA_L2_RTC-S1_T137-292319-IW1_20250102T015900Z_20250102T190143Z_S1A_30_v1.0,'
                                      'OPERA_L2_RTC-S1_T137-292319-IW2_20250102T015901Z_20250102T190143Z_S1A_30_v1.0,'
                                      'OPERA_L2_RTC-S1_T137-292320-IW1_20250102T015903Z_20250102T190143Z_S1A_30_v1.0',
                'pre_rtc_opera_ids': 'OPERA_L2_RTC-S1_T137-292318-IW1_20240904T015900Z_20240904T150822Z_S1A_30_v1.0,'
                                     'OPERA_L2_RTC-S1_T137-292318-IW1_20240916T015901Z_20240916T114330Z_S1A_30_v1.0,'
                                     'OPERA_L2_RTC-S1_T137-292318-IW1_20240928T015901Z_20240929T005548Z_S1A_30_v1.0,'
                                     'OPERA_L2_RTC-S1_T137-292318-IW1_20241010T015902Z_20241010T101259Z_S1A_30_v1.0,'
                                     'OPERA_L2_RTC-S1_T137-292318-IW1_20241022T015902Z_20241022T180854Z_S1A_30_v1.0',
                'product_dst_dir': '/home/ops/output_dir',
                'tqdm_enabled': 'True',
                'version': '0.0.6',
                'water_mask_path': 'None'
            }

        def GetMetadata(self):
            """
            Returns a subset of dummy metadata expected by the PGE.
            This function should be updated as needed for requisite metadata fields.
            """
            return deepcopy(self.dummy_metadata)

    class MockDispS1StaticGdalDataset:
        """
        Mock class for gdal.Dataset objects, as returned from an Open call.
        For use when mocking metadata from DISP-S1-STATIC GeoTIFF products
        """

        def __init__(self):
            self.dummy_metadata = {
                'AREA_OR_POINT': 'Area',
            }

        def GetMetadata(self):
            """
            Returns a subset of dummy metadata expected by the PGE.
            This function should be updated as needed for requisite metadata fields.
            """
            return deepcopy(self.dummy_metadata)

        @property
        def RasterXSize(self):
            """Return the width of the mock raster"""
            return 9600

        @property
        def RasterYSize(self):
            """Return the width of the mock raster"""
            return 6867

    @staticmethod
    def Open(filename):
        """Mock implementation for gdal.Open. Returns an instance of the mock Dataset."""
        if not exists(filename):
            # Return None since that's what GDAL does. The utility functions need
            # to be aware of this and handle a None return accordingly.
            return None

        file_name = filename.split('/')[-1].lower()

        if 'dswx_s1' in file_name or 'dswx-s1' in file_name:
            return MockGdal.MockDSWxS1GdalDataset()
        elif 'dswx_ni' in file_name or 'dswx-ni' in file_name:
            return MockGdal.MockDSWxNIGdalDataset()
        elif 'rtc_s1' in file_name or 'rtc-s1' in file_name:
            return MockGdal.MockRtcS1GdalDataset()
        elif 'dist_alert_s1' in file_name or 'dist-alert-s1' in file_name:
            return MockGdal.MockDistS1GdalDataset()
        elif 'dswx_hls' in file_name or 'dswx-hls' in file_name:
            return MockGdal.MockDSWxHLSGdalDataset()
        elif 'disp_s1_static' in file_name or 'disp-s1-static' in file_name:
            return MockGdal.MockDispS1StaticGdalDataset()
        else:
            raise ValueError('Filename does not appear to match existing mock GDAL datasets')


def mock_gdal_edit(args):
    """Mock implementation of osgeo_utils.gdal_edit that always returns success"""
    return 0  # pragma: no cover


def mock_save_as_cog(filename, scratch_dir='.', logger=None,
                     flag_compress=True, resamp_algorithm=None):
    """Mock implementation of proteus.core.save_as_cog"""
    return  # pragma: no cover


class MockOsr:  # pragma: no cover
    # pylint: disable=unused-variable,invalid-name,too-many-locals,too-many-statements,too-many-boolean-expressions
    """
    Mock class for the osgeo.osr module.

    This class is defined so the opera-sds-pge project does not require the
    Geospatial Data Abstraction Library (GDAL) as an explicit dependency for
    developers. When PGE code is eventually run from within a Docker container,
    osgeo.osr should always be installed and importable.
    """

    class MockSpatialReference:
        """Mock class for the osgeo.osr module"""

        def __init__(self):
            self.zone = 1
            self.hemi = 'N'

        def SetWellKnownGeogCS(self, name):
            """Mock implementation for osr.SetWellKnownGeogCS"""
            pass

        def SetUTM(self, zone, north=True):
            """Mock implementation for osr.SetUTM"""
            self.zone = zone
            self.hemi = "N" if north else "S"

        def ImportFromEPSG(self, epsgCode):
            """Mock implementation for osr.ImportFromEPSG"""
            return 0

    class MockCoordinateTransformation:
        """Mock class for the osgeo.osr.CoordinateTransformation class"""

        def __init__(self, src, dest):
            self.src = src
            self.dest = dest

        def TransformPoint(self, x, y, z):
            """Mock implementation for CoordinateTransformation.TransformPoint"""
            # Use mgrs to convert UTM back to a tile ID, then covert to rough
            # lat/lon, this should be accurate enough for development testing
            mgrs_obj = mgrs.MGRS()
            try:
                mgrs_tile = mgrs_obj.UTMToMGRS(self.src.zone, self.src.hemi, x, y)
                lat, lon = mgrs_obj.toLatLon(mgrs_tile)
                return lat, lon, z
            except:
                # Fallback to returning inputs if calls to MGRS library fail on
                # fake inputs
                return x, y, z

    @staticmethod
    def SpatialReference():
        """Mock implementation for osgeo.osr.SpatialReference"""
        return MockOsr.MockSpatialReference()

    @staticmethod
    def CoordinateTransformation(src, dest):
        """Mock implementation for osgeo.osr.CoordinateTransformation"""
        return MockOsr.MockCoordinateTransformation(src, dest)
