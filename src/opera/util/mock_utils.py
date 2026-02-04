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
                'SPACECRAFT_NAME': 'Sentinel-1',
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
                "algo_config_path": "/home/ops/runconfig/opera_pge_dist_s1_r4_calval_algorithm_parameters.yaml",
                "apply_despeckling": "True",
                "apply_logit_to_inputs": "True",
                "apply_water_mask": "True",
                "batch_size_for_norm_param_estimation": "32",
                "bucket": "None",
                "bucket_prefix": "None",
                "confirmation_confidence_upper_lim": "32000",
                "confirmation_confidence_threshold": "31.5",
                "delta_lookback_days_mw": "1095,730,365",
                "device": "cpu",
                "dst_dir": "/home/ops/scratch_dir",
                "exclude_consecutive_no_dist": "1",
                "high_confidence_alert_threshold": "5.5",
                "input_data_dir": "/home/ops/input_dir/out_1",
                "interpolation_method": "bilinear",
                "lookback_strategy": "multi_window",
                "low_confidence_alert_threshold": "3.5",
                "max_obs_num_year": "253",
                "max_pre_imgs_per_burst_mw": "3,3,4",
                "memory_strategy": "high",
                "metric_value_upper_lim": "100.0",
                "mgrs_tile_id": "11SLT",
                "model_cfg_path": "None",
                "model_compilation": "False",
                "model_dtype": "float32",
                "model_source": "transformer_optimized",
                "model_wts_path": "None",
                "no_count_reset_thresh": "7",
                "no_day_limit": "30",
                "n_anniversaries_for_mw": "3",
                "n_workers_for_despeckling": "8",
                "n_workers_for_norm_param_estimation": "8",
                "percent_reset_thresh": "10",
                "post_date_buffer_days": "1",
                "post_rtc_opera_ids": "OPERA_L2_RTC-S1_T071-151226-IW2_20250121T135246Z_20250121T180333Z_S1A_30_v1.0,"
                                      "OPERA_L2_RTC-S1_T071-151226-IW3_20250121T135247Z_20250121T180333Z_S1A_30_v1.0,"
                                      "OPERA_L2_RTC-S1_T071-151227-IW2_20250121T135249Z_20250121T180333Z_S1A_30_v1.0,"
                                      "OPERA_L2_RTC-S1_T071-151227-IW3_20250121T135250Z_20250121T180333Z_S1A_30_v1.0,"
                                      "OPERA_L2_RTC-S1_T071-151228-IW2_20250121T135252Z_20250121T180333Z_S1A_30_v1.0",
                "pre_rtc_opera_ids": "OPERA_L2_RTC-S1_T071-151226-IW2_20220101T135243Z_20241217T000016Z_S1A_30_v1.0,"
                                     "OPERA_L2_RTC-S1_T071-151226-IW2_20220113T135242Z_20241219T014436Z_S1A_30_v1.0,"
                                     "OPERA_L2_RTC-S1_T071-151226-IW3_20220101T135244Z_20241217T000824Z_S1A_30_v1.0,"
                                     "OPERA_L2_RTC-S1_T071-151226-IW3_20220113T135243Z_20241219T014249Z_S1A_30_v1.0,"
                                     "OPERA_L2_RTC-S1_T071-151227-IW2_20220101T135245Z_20241217T000824Z_S1A_30_v1.0",
                "prior_dist_s1_product": "/home/ops/input_dir/product_0/"
                                         "OPERA_L3_DIST-ALERT-S1_T11SLT_20250109T135247Z_20250818T224409Z_S1_30_v0.1",
                "prior_product_name": "OPERA_L3_DIST-ALERT-S1_T11SLT_20250109T135247Z_20250818T224409Z_S1_30_v0.1",
                "product_dst_dir": "/home/ops/output_dir",
                "sensor": "S1A",
                "stride_for_norm_param_estimation": "16",
                "tqdm_enabled": "True",
                "use_date_encoding": "False",
                "version": "dist-s1-2.0.6.dev0+g36f541fb7.d20250904",
                "src_water_mask_path": "/home/ops/input_dir/out_1/11SLT_water_mask.tif",
                "water_mask_path": "/home/ops/input_dir/out_1/11SLT_water_mask.tif",
                "AREA_OR_POINT": "Area"
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
                'ACQUISITION_MODE': 'IW',
                'ACQUISITION_MODE_DESCRIPTION': 'Radar acquisition mode for input products',
                'AREA_OR_POINT': 'Area',
                'CEOS_ANALYSIS_READY_DATA_DOCUMENT_IDENTIFIER': 'https://ceos.org/ard/files/PFS/SAR/v1.2/CEOS-ARD_PFS_Synthetic_Aperture_Radar_v1.2.pdf',
                'CEOS_ANALYSIS_READY_DATA_DOCUMENT_IDENTIFIER_DESCRIPTION': 'CEOS Analysis Ready Data (CARD) document '
                                                                            'identifier',
                'CONTACT_INFORMATION': 'opera-sds-ops@jpl.nasa.gov',
                'CONTACT_INFORMATION_DESCRIPTION': 'Contact information for producer of this '
                                                   'product',
                'DISP_S1_SOFTWARE_VERSION': '0.5.9',
                'DISP_S1_SOFTWARE_VERSION_DESCRIPTION': 'Version of the disp-s1 software used '
                                                        'to generate the product.',
                'FRAME_ID': '11115',
                'FRAME_ID_DESCRIPTION': 'OPERA DISP-S1 Frame ID of the processed frame',
                'IMAGING_GEOMETRY': 'Geocoded',
                'IMAGING_GEOMETRY_DESCRIPTION': 'Imaging geometry of input coregistered SLCs '
                                                'and Static Layer products',
                'INSTITUTION': 'NASA JPL',
                'INSTRUMENT_NAME': 'Sentinel-1 CSAR',
                'INSTRUMENT_NAME_DESCRIPTION': 'Name of the instrument used to collect the '
                                               'remote sensing data',
                'LOOK_DIRECTION': 'right',
                'LOOK_DIRECTION_DESCRIPTION': 'Look direction (left or right) for input '
                                              'products',
                'ORBIT_DIRECTION': 'Descending',
                'ORBIT_DIRECTION_DESCRIPTION': 'Orbit direction of the processed frame '
                                               '(ascending or descending)',
                'PLATFORM': 'Sentinel-1',
                'PLATFORM_DESCRIPTION': 'Platform name',
                'PROCESSING_DATETIME': '2025-07-02T00:22:27.883367Z',
                'PROCESSING_FACILITY': 'NASA Jet Propulsion Laboratory on AWS',
                'PRODUCT_DATA_ACCESS': 'https://search.asf.alaska.edu/#/?dataset=OPERA-S1&productTypes=DISP-S1-STATIC',
                'PRODUCT_DATA_ACCESS_DESCRIPTION': 'Location from where this product can be '
                                                   'retrieved, expressed as a URL or DOI.',
                'PRODUCT_LANDING_PAGE_DOI': 'https://doi.org/10.5067/SNWG/OPL3DISPS1-V1',
                'PRODUCT_SAMPLE_SPACING': '30',
                'PRODUCT_SAMPLE_SPACING_DESCRIPTION': 'Spacing between adjacent X/Y samples '
                                                      'of product in UTM coordinates',
                'PRODUCT_SPECIFICATION_VERSION': '1.0',
                'PRODUCT_VERSION': '1.0',
                'PROJECT': 'OPERA',
                'RADAR_BAND': 'C',
                'RADAR_BAND_DESCRIPTION': 'Acquired radar frequency band',
                'SOURCE_DATA_ACCESS': 'https://search.asf.alaska.edu/#/?dataset=OPERA-S1&productTypes=CSLC-S1-STATIC,RTC-S1-STATIC',
                'SOURCE_DATA_ACCESS_DESCRIPTION': 'Location from where the source data can be '
                                                  'retrieved, expressed as a URL or DOI.',
                'SOURCE_DATA_ORIGINAL_INSTITUTION': 'European Space Agency Copernicus Program',
                'SOURCE_DATA_ORIGINAL_INSTITUTION_DESCRIPTION': 'Original processing '
                                                                'institution of Sentinel-1 '
                                                                'SLC data',
                'TRACK_NUMBER': '42',
                'TRACK_NUMBER_DESCRIPTION': 'Track Number/Relative orbit number of source '
                                            'data of the processed frame',
                'dem_egm_model': 'Earth Gravitational Model 2008 (EGM2008)',
                'dem_interpolation_algorithm': 'biquintic',
                'input_dem_source': 'Copernicus GLO-30 DEM for OPERA'
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
