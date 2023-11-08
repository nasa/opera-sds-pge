#!/usr/bin/env python3

"""
===========
h5_utils.py
===========

Utilities used for working with HD5F files

"""
# flake8: noqa F841

import h5py

import numpy as np

from opera.util.mock_utils import MockOsr

S1_SLC_HDF5_PREFIX = ""
"""Prefix used to index metadata within SLC-based HDF5 products"""

# When running a PGE within a Docker image delivered from ADT, the gdal import
# below should work. When running in a dev environment, the import will fail
# resulting in the MockGdal class being substituted instead.

# pylint: disable=import-error,invalid-name
try:
    from osgeo import osr

    osr.UseExceptions()
except (ImportError, ModuleNotFoundError):  # pragma: no cover
    osr = MockOsr                           # pragma: no cover
# pylint: enable=import-error,invalid-name


def get_hdf5_group_as_dict(file_name, group_path, ignore_keys=None):
    """
    Returns HDF5 group variable data as a python dict for a given file and group
    path.

    Group attributes are not included.

    Parameters
    ----------
    file_name : str
        File system path and filename for the HDF5 file to use.
    group_path : str
        Group path within the HDF5 file.
    ignore_keys : iterable, optional
        Keys within the group to not include in the returned dict.

    Returns
    -------
    group_dict : dict
        Python dict containing variable data from the group path location.

    """
    with h5py.File(file_name, 'r') as h5file:
        group_object = h5file.get(group_path)

        if group_object is None:
            raise RuntimeError(f"An error occurred retrieving object '{group_path}' "
                               f"from file '{file_name}'.")
        elif isinstance(group_object, h5py.Dataset):
            result = convert_h5py_dataset(group_object)
        else:
            result = convert_h5py_group_to_dict(group_object, ignore_keys)

    return result


def convert_h5py_group_to_dict(group_object, ignore_keys=None):
    """
    Returns HDF5 group variable data as a python dict for a given h5py group object.
    Recursively calls itself to process subgroups.

    Group attributes are not included.

    Notes
    -----
    Byte sequences are converted to python strings which will probably cause
    issues with non-text data.

    Parameters
    ----------
    group_object : h5py._hl.group.Group
        h5py Group object to be converted to a dict.
    ignore_keys : iterable, optional
        Keys within the group to not include in the returned dict.

    Returns
    -------
    converted_dict : dict
        Python dict containing variable data from the group object.
        data is copied from the h5py group object to a python dict.

    """
    converted_dict = {}
    for key, val in group_object.items():

        if ignore_keys and key in ignore_keys:
            continue

        if isinstance(val, h5py.Dataset):
            converted_dict[key] = convert_h5py_dataset(val)
        elif isinstance(val, h5py.Group):
            converted_dict[key] = convert_h5py_group_to_dict(val)

    return converted_dict


def convert_h5py_dataset(dataset_object):
    """
    Converts an instance of h5.Dataset to a native Python type.

    Parameters
    ----------
    dataset_object : h5py.Dataset
        The HDF5 Dataset object to convert.

    Returns
    -------
    result : object
        The result of the conversion to native Python type.

    """
    if type(dataset_object[()]) is np.ndarray:  # pylint: disable=C0123
        if isinstance(dataset_object[0], (bytes, np.bytes_)):
            # decode bytes to str
            result = dataset_object.asstr()[()]
        else:
            result = dataset_object[()]
    else:
        if isinstance(dataset_object[()], (bytes, np.bytes_)):
            # decode bytes to str
            result = dataset_object.asstr()[()]
        else:
            result = dataset_object[()]

    return result


def get_rtc_s1_product_metadata(file_name):
    """
    Returns a python dict containing the RTC-S1 product_output metadata
    which will be used with the ISO metadata template.

    Parameters
    ----------
    file_name : str
        the RTC-S1 product file to obtain metadata from.

    Returns
    -------
    product_output : dict
        python dict containing the HDF5 file metadata which is used in the
        ISO template.
    """
    product_output = {
        'data': get_hdf5_group_as_dict(file_name, f"{S1_SLC_HDF5_PREFIX}/data"),
        'processingInformation': get_hdf5_group_as_dict(file_name,
                                                        f"{S1_SLC_HDF5_PREFIX}/metadata/processingInformation"),
        'orbit': get_hdf5_group_as_dict(file_name, f"{S1_SLC_HDF5_PREFIX}/metadata/orbit"),
        'identification': get_hdf5_group_as_dict(file_name, f"{S1_SLC_HDF5_PREFIX}/identification")
    }

    return product_output


def create_test_rtc_metadata_product(file_path):
    # pylint: disable=unused-variable,invalid-name,too-many-locals,too-many-statements,too-many-boolean-expressions
    """
    Creates a dummy RTC HDF5 product with expected metadata fields.
    This function is intended for use with unit tests, but is included in this
    module, so it will be importable from within a built container.

    Parameters
    ----------
    file_path : str
        Full path to write the dummy RTC HDF5 product to.

    """
    with h5py.File(file_path, 'w') as outfile:
        data_grp = outfile.create_group(f"{S1_SLC_HDF5_PREFIX}/data")
        xCoordinateSpacing_dset = data_grp.create_dataset("xCoordinateSpacing", data=30.0, dtype='float64')
        xCoordinates_dset = data_grp.create_dataset("xCoordinates", data=np.zeros((10,)), dtype='float64')
        yCoordinateSpacing_dset = data_grp.create_dataset("yCoordinateSpacing", data=30.0, dtype='float64')
        yCoordinates_dset = data_grp.create_dataset("yCoordinates", data=np.zeros((10,)), dtype='float64')
        projection_dset = data_grp.create_dataset("projection", data=32718, dtype='int')
        listOfPolarizations_dset = data_grp.create_dataset("listOfPolarizations", data=np.array([b'VV', b'VH']))

        orbit_grp = outfile.create_group(f"{S1_SLC_HDF5_PREFIX}/metadata/orbit")
        orbitType_dset = orbit_grp.create_dataset("orbitType", data=b'POE')
        interpMethod_dest = orbit_grp.create_dataset("interpMethod", data=b'Hermite')
        referenceEpoch_dset = orbit_grp.create_dataset("referenceEpoch", data=b'2018-05-02T10:45:07.581333000')

        processingInformation_inputs_grp = outfile.create_group(f"{S1_SLC_HDF5_PREFIX}"
                                                                f"/metadata/processingInformation/inputs")
        demSource_dset = processingInformation_inputs_grp.create_dataset("demSource", data=b'dem.tif')
        annotationFiles = np.array([b'calibration-s1b-iw1-slc-vv-20180504t104508-20180504t104533-010770-013aee-004.xml',
                                    b'noise-s1b-iw1-slc-vv-20180504t104508-20180504t104533-010770-013aee-004.xml'])
        annotationFiles_dset = processingInformation_inputs_grp.create_dataset("annotationFiles", data=annotationFiles)
        l1SlcGranules = np.array([b'S1B_IW_SLC__1SDV_20180504T104507_20180504T104535_010770_013AEE_919F.zip'])
        l1SlcGranules_dset = processingInformation_inputs_grp.create_dataset("l1SlcGranules", data=l1SlcGranules)
        orbitFiles = np.array([b'S1B_OPER_AUX_POEORB_OPOD_20180524T110543_V20180503T225942_20180505T005942.EOF'])
        orbitFiles_dset = processingInformation_inputs_grp.create_dataset("orbitFiles", data=orbitFiles)

        processingInformation_algorithms_grp = outfile.create_group(
            f"{S1_SLC_HDF5_PREFIX}/metadata/processingInformation/algorithms")
        demEgmModel_dset = processingInformation_algorithms_grp.create_dataset("demEgmModel",
                                                                               data=b'Earth Gravitational Model EGM08')
        demInterpolation_dset = processingInformation_algorithms_grp.create_dataset("demInterpolation",
                                                                                    data=b'biquintic')
        geocoding_dset = processingInformation_algorithms_grp.create_dataset("geocoding", data=b'area_projection')
        geocodingAlgoRef_dset = processingInformation_algorithms_grp.create_dataset(
            "geocodingAlgorithmReference", data=b'Geocoding Algorithm Reference')
        isceVersion_dset = processingInformation_algorithms_grp.create_dataset("isce3Version", data=b'0.13.0')
        noiseCorrectionAlgoRef_dset = processingInformation_algorithms_grp.create_dataset(
            "noiseCorrectionAlgorithmReference", data=b'Noise Correction Algorithm Reference')
        radiometricTerrainCorrection_dset = processingInformation_algorithms_grp.create_dataset(
            "radiometricTerrainCorrection", data=b'area_projection')
        radiometricTerrainCorrectionAlgoRef_dset = processingInformation_algorithms_grp.create_dataset(
            "radiometricTerrainCorrectionAlgorithmReference",
            data=b'Radiometric Terrain Correction Algorithm Reference')
        s1ReaderVersion_dset = processingInformation_algorithms_grp.create_dataset("s1ReaderVersion", data=b'1.2.3')
        softwareVersion_dset = processingInformation_algorithms_grp.create_dataset("softwareVersion", data=b'0.4')

        processingInformation_parameters_grp = outfile.create_group(
            f"{S1_SLC_HDF5_PREFIX}/metadata/processingInformation/parameters")
        bistaticDelayCorrectionApplied_dset = processingInformation_parameters_grp.create_dataset(
            "bistaticDelayCorrectionApplied", data=True, dtype='bool')
        staticTroposphericGeolocationCorrectionApplied_dset = processingInformation_parameters_grp.create_dataset(
            "staticTroposphericGeolocationCorrectionApplied", data=True, dtype='bool')
        filteringApplied_dset = processingInformation_parameters_grp.create_dataset(
            "filteringApplied", data=False, dtype='bool')
        geocoding_grp = processingInformation_parameters_grp.create_group("geocoding")
        burstGeogridSnapX_dset = geocoding_grp.create_dataset("burstGeogridSnapX", data=30, dtype='int')
        burstGeogridSnapY_dset = geocoding_grp.create_dataset("burstGeogridSnapY", data=30, dtype='int')
        inputBackscatterNormalizationConvention_dset = processingInformation_parameters_grp.create_dataset(
            "inputBackscatterNormalizationConvention", data=b'beta0')
        noiseCorrectionApplied_dset = processingInformation_parameters_grp.create_dataset(
            "noiseCorrectionApplied", data=True, dtype='bool')
        outputBackscatterDecibelConversionEquation_dset = processingInformation_parameters_grp.create_dataset(
            "outputBackscatterDecibelConversionEquation", data=b'backscatter_dB = 10*log10(backscatter_linear)')
        outputBackscatterExpressionConvention_dset = processingInformation_parameters_grp.create_dataset(
            "outputBackscatterExpressionConvention", data=b'linear backscatter intensity')
        outputBackscatterNormalizationConvention_dset = processingInformation_parameters_grp.create_dataset(
            "outputBackscatterNormalizationConvention", data=b'gamma0')
        preprocessingMultilookingApplied_dset = processingInformation_parameters_grp.create_dataset(
            "preprocessingMultilookingApplied", data=False, dtype='bool')
        radiometricTerrainCorrectionApplied_dset = processingInformation_parameters_grp.create_dataset(
            'radiometricTerrainCorrectionApplied', data=True, dtype='bool')
        wetTroposphericGeolocationCorrectionApplied_dset = processingInformation_parameters_grp.create_dataset(
            "wetTroposphericGeolocationCorrectionApplied", data=True, dtype='bool')

        identification_grp = outfile.create_group(f"{S1_SLC_HDF5_PREFIX}/identification")
        absoluteOrbitNumber_dset = identification_grp.create_dataset("absoluteOrbitNumber", data=10770, dtype='int64')
        acquisitionMode_dset = identification_grp.create_dataset("acquisitionMode",
                                                                 data=np.string_('Interferometric Wide (IW)'))
        beamID_dset = identification_grp.create_dataset("beamID", data=np.string_('iw1'))
        boundingBox_dset = identification_grp.create_dataset("boundingBox", data=np.array([200700.0, 9391650.0,
                                                                                           293730.0, 9440880.0]))
        boundingPolygon_dset = identification_grp.create_dataset(
            "boundingPolygon", data=b'POLYGON ((399015 3859970, 398975 3860000, ..., 399015 3859970))')
        burstID_dset = identification_grp.create_dataset("burstID", data=b't069_147170_iw1')
        contactInformation_dset = identification_grp.create_dataset("contactInformation", data=b'operasds@jpl.nasa.gov')
        ceosAnalysisReadyDataDocumentIdentifier_dset = identification_grp.create_dataset(
            "ceosAnalysisReadyDataDocumentIdentifier", data=True, dtype='bool')
        ceosAnalysisReadyDataProductType_dset = identification_grp.create_dataset("ceosAnalysisReadyDataProductType",
                                                                                  data=b'Normalized Radar Backscatter')
        dataAccess_dset = identification_grp.create_dataset("dataAccess", data=b'(NOT PROVIDED)')
        diagnosticModeFlag_dset = identification_grp.create_dataset("diagnosticModeFlag", data=False, dtype='bool')
        institution_dset = identification_grp.create_dataset("institution", data=b'NASA JPL')
        instrumentName_dset = identification_grp.create_dataset("instrumentName", data=b'Sentinel-1B CSAR')
        isGeocodedFlag = identification_grp.create_dataset("isGeocoded", data=True, dtype='bool')
        lookDirection_dset = identification_grp.create_dataset("lookDirection", data=b'Right')
        orbitPassDirection_dset = identification_grp.create_dataset("orbitPassDirection", data=b'Descending')
        platform_dset = identification_grp.create_dataset("platform", data=b'Sentinel-1B')
        processingDateTime_dset = identification_grp.create_dataset("processingDateTime",
                                                                    data=np.string_('2023-03-23T20:32:18.962836Z'))
        processingType_dset = identification_grp.create_dataset("processingType", data=b'UNDEFINED')
        productLevel_dset = identification_grp.create_dataset("productLevel", data=b'L2')
        productSpecificationVersion_dset = identification_grp.create_dataset("productSpecificationVersion", data=b'0.1')
        productType_dset = identification_grp.create_dataset("productType", data=b'SLC')
        productVersion_dset = identification_grp.create_dataset("productVersion", data=b'1.0')
        project_dset = identification_grp.create_dataset("project", data=b'OPERA')
        radarBand_dset = identification_grp.create_dataset("radarBand", data=b'C')
        staticLayersDataAccess_dset = identification_grp.create_dataset("staticLayersDataAccess",
                                                                        data=b'(NOT PROVIDED)')
        subSwathID_dset = identification_grp.create_dataset("subSwathID", data=b'IW3')
        trackNumber_dset = identification_grp.create_dataset("trackNumber", data=147170, dtype='int64')
        zeroDopplerEndTime_dset = identification_grp.create_dataset("zeroDopplerEndTime",
                                                                    data=b'2018-05-04T10:45:11.501279')
        zeroDopplerStartTime_dset = identification_grp.create_dataset("zeroDopplerStartTime",
                                                                      data=b'2018-05-04T10:45:08.436445')


def get_cslc_s1_product_metadata(file_name):
    """
    Returns a python dict containing the CSLC S1 metadata
    which will be used with the ISO metadata template.

    Parameters
    ----------
    file_name : str
        the CSLC S1 metadata file.

    Returns
    -------
    cslc_metadata : dict
        python dict containing the HDF5 file metadata which is used in the
        ISO template.
    """
    # Ignore some larger arrays from the metadata, so we don't use
    # too much memory when caching the metadata for each burst
    cslc_ignore_list = [
        'azimuth_carrier_phase', 'flattening_phase',
        'layover_shadow_mask', 'local_incidence_angle',
        'los_east', 'los_north',
        'VV', 'VH', 'HH', 'HV'
    ]
    cslc_metadata = {
        'identification': get_hdf5_group_as_dict(file_name, f"{S1_SLC_HDF5_PREFIX}/identification"),
        'data': get_hdf5_group_as_dict(file_name, f"{S1_SLC_HDF5_PREFIX}/data", cslc_ignore_list),
        'processing_information': get_hdf5_group_as_dict(file_name,
                                                         f"{S1_SLC_HDF5_PREFIX}/metadata/processing_information"),
        'orbit': get_hdf5_group_as_dict(file_name, f"{S1_SLC_HDF5_PREFIX}/metadata/orbit"),
        'quality_assurance': get_hdf5_group_as_dict(file_name, f"{S1_SLC_HDF5_PREFIX}/quality_assurance")
    }

    return cslc_metadata


def create_test_cslc_metadata_product(file_path):
    # pylint: disable=unused-variable,invalid-name,too-many-locals,too-many-statements,too-many-boolean-expressions
    """
    Creates a dummy CSLC h5 metadata file with expected groups and datasets.
    This function is intended for use with unit tests, but is included in this
    module, so it will be importable from within a built container.
    The pylint test R0195 was disabled: 'Too many statements (120/100)
    (too-many-statements)'

    Parameters
    ----------
    file_path : str
        Full path to write the dummy CSLC H5 metadata file to.

    """
    with h5py.File(file_path, 'w') as outfile:
        identification_grp = outfile.create_group(f"{S1_SLC_HDF5_PREFIX}/identification")
        absolute_orbit_number_dset = identification_grp.create_dataset("absolute_orbit_number", data=43011,
                                                                       dtype='int64')
        bounding_polygon_dset = identification_grp.create_dataset(
            "bounding_polygon", data=np.string_("POLYGON ((-118.77 33.67, -118.72 33.68, ..., -118.77 33.67))"))
        burst_id_dset = identification_grp.create_dataset("burst_id", data=np.string_("t064_135518_iw1"))
        instrument_name_dset = identification_grp.create_dataset("instrument_name", data=np.string_('C-SAR'))
        is_geocoded_flag_dset = identification_grp.create_dataset("is_geocoded", data=True, dtype='bool')
        look_direction_dset = identification_grp.create_dataset("look_direction", data=np.string_("Right"))
        mission_id_dset = identification_grp.create_dataset("mission_id", data=np.string_("S1A"))
        orbit_pass_direction_dset = identification_grp.create_dataset("orbit_pass_direction",
                                                                      data=np.string_("Ascending"))
        processing_center_dset = identification_grp.create_dataset("processing_center",
                                                                   data=np.string_("Jet Propulsion Laboratory"))
        processing_date_time_dset = identification_grp.create_dataset("processing_date_time",
                                                                      data=np.string_("2023-06-05 21:43:21.317243"))
        product_level_dset = identification_grp.create_dataset("product_level", data=np.string_("L2"))
        product_specification_version_dset = identification_grp.create_dataset("product_specification_version",
                                                                               data=np.string_("3.2.1"))
        product_type_dset = identification_grp.create_dataset("product_type", data=np.string_("CSLC-S1"))
        product_version_dset = identification_grp.create_dataset("product_version", data=np.string_("1.0"))
        radar_band_dset = identification_grp.create_dataset("radar_band", data=np.string_("C"))
        track_number_dset = identification_grp.create_dataset("track_number", data=64, dtype="int64")
        zero_doppler_end_time_dset = identification_grp.create_dataset("zero_doppler_end_time",
                                                                       data=np.string_("2022-05-01 01:50:38.106185"))
        zero_doppler_start_time_dset = identification_grp.create_dataset("zero_doppler_start_time",
                                                                         data=np.string_("2022-05-01 01:50:35.031073"))

        data_grp = outfile.create_group(f"{S1_SLC_HDF5_PREFIX}/data")
        projection_dset = data_grp.create_dataset("projection", data=32611, dtype='int32')
        x_coordinates_dset = data_grp.create_dataset("x_coordinates", data=np.zeros((10,)), dtype='float64')
        x_spacing_dset = data_grp.create_dataset("x_spacing", data=5.0, dtype="float64")
        y_coordinates_dset = data_grp.create_dataset("y_coordinates", data=np.zeros((10,)), dtype='float64')
        y_spacing_dset = data_grp.create_dataset("y_spacing", data=-10.0, dtype='float64')

        processing_information_grp = outfile.create_group(f"{S1_SLC_HDF5_PREFIX}/metadata/processing_information")

        algorithms_grp = outfile.create_group(f"{S1_SLC_HDF5_PREFIX}/metadata/processing_information/algorithms")
        COMPASS_version_dset = algorithms_grp.create_dataset("COMPASS_version", data=np.string_("0.1.3"))
        ISCE3_version_dset = algorithms_grp.create_dataset("ISCE3_version", data=np.string_("0.9.0"))
        dem_interpolation_dset = algorithms_grp.create_dataset("dem_interpolation", data=np.string_("biquintic"))
        complex_data_geocoding_interpolator_dset = algorithms_grp.create_dataset("complex_data_geocoding_interpolator",
                                                                                 data=np.string_("sinc interpolation"))
        float_data_geocoding_interpolator_dset = algorithms_grp.create_dataset(
            "float_data_geocoding_interpolator", data=np.string_("biquintic interpolation"))
        topography_algorithm_dset = algorithms_grp.create_dataset("topography_algorithm",
                                                                  data=np.string_("isce3.geometry.topo"))
        uint_data_geocoding_interpolator = algorithms_grp.create_dataset(
            "uint_data_geocoding_interpolator", data=np.string_("nearest neighbor interpolation"))
        s1_reader_version_dset = algorithms_grp.create_dataset("s1_reader_version", data=np.string_("0.2.0"))

        inputs_grp = outfile.create_group(f"{S1_SLC_HDF5_PREFIX}/metadata/processing_information/inputs")
        calibration_files_dset = inputs_grp.create_dataset("calibration_files", data=np.string_(
            'calibration-s1a-iw1-slc-vv-20220501t015035-20220501t015102-043011-0522a4-004.xml'))
        dem_source_dset = inputs_grp.create_dataset("dem_source", data=np.string_('dem_4326.tiff'))
        l1_slc_files_dset = inputs_grp.create_dataset('l1_slc_files', data=np.string_(
            'S1A_IW_SLC__1SDV_20220501T015035_20220501T015102_043011_0522A4_42CC'))
        noise_files_dset = inputs_grp.create_dataset("noise_files", data=np.string_(
            'noise-s1a-iw1-slc-vv-20220501t015035-20220501t015102-043011-0522a4-004.xml'))
        orbit_files_dset = inputs_grp.create_dataset("orbit_files", data=np.array(
            [b'S1A_OPER_AUX_POEORB_OPOD_20220521T081912_V20220430T225942_20220502T005942.EOF']))

        burst_location_parameters_grp = outfile.create_group(
            f"{S1_SLC_HDF5_PREFIX}/metadata/processing_information/inputs/burst_location_parameters")
        burst_index_dset = burst_location_parameters_grp.create_dataset("burst_index", data=0, dtype='int64')
        first_valid_line_dset = burst_location_parameters_grp.create_dataset("first_valid_line", data=0, dtype='int64')
        first_valid_sample_dset = burst_location_parameters_grp.create_dataset("first_valid_sample", data=63,
                                                                               dtype='int64')
        last_valid_line_dset = burst_location_parameters_grp.create_dataset("last_valid_line", data=1477, dtype='int64')
        last_valid_sample_dset = burst_location_parameters_grp.create_dataset("last_valid_sample", data=20531,
                                                                              dtype='int64')
        tiff_path_dset = burst_location_parameters_grp.create_dataset("tiff_path", data=np.string_(
            "s1a-iw1-slc-vv-20220501t015035-20220501t015102-043011-0522a4-004.tiff"))
        processing_parameters_grp = outfile.create_group(
            f"{S1_SLC_HDF5_PREFIX}/metadata/processing_information/parameters")
        azimuth_fm_rate_applied_dset = processing_parameters_grp.create_dataset("azimuth_fm_rate_applied",
                                                                                data=True, dtype='bool')
        azimuth_solid_earth_tides_applied_dset = processing_parameters_grp.create_dataset(
            "azimuth_solid_earth_tides_applied", data=True, dtype='bool')
        bistatic_delay_applied_dset = processing_parameters_grp.create_dataset("bistatic_delay_applied", data=True,
                                                                               dtype='bool')
        dry_troposphere_weather_model_applied_dset = processing_parameters_grp.create_dataset(
            "dry_troposphere_weather_model_applied", data=True, dtype='bool')
        elevation_antenna_pattern_correction_applied_dset = processing_parameters_grp.create_dataset(
            "elevation_antenna_pattern_correction_applied", data=np.string_("ESA"))
        ellipsoidal_flattening_applied_dset = processing_parameters_grp.create_dataset("ellipsoidal_flattening_applied",
                                                                                       data=True, dtype='bool')
        geometry_doppler_applied_dset = processing_parameters_grp.create_dataset("geometry_doppler_applied", data=True,
                                                                                 dtype='bool')
        ionosphere_tec_applied_dset = processing_parameters_grp.create_dataset("ionosphere_tec_applied", data=True,
                                                                               dtype='bool')
        los_solid_earth_tides_applied_dset = processing_parameters_grp.create_dataset("los_solid_earth_tides_applied",
                                                                                      data=True, dtype='bool')
        static_troposphere_applied_dset = processing_parameters_grp.create_dataset("static_troposphere_applied",
                                                                                   data=True, dtype='bool')
        topographic_flattening_applied_dset = processing_parameters_grp.create_dataset("topographic_flattening_applied",
                                                                                       data=True, dtype='bool')
        wet_troposphere_weather_model_applied_dset = processing_parameters_grp.create_dataset(
            "wet_troposphere_weather_model_applied", data=True, dtype='bool')
        input_burst_metadata_grp = outfile.create_group(f"{S1_SLC_HDF5_PREFIX}"
                                                        f"/metadata/processing_information/input_burst_metadata")
        azimuth_fm_rate_grp = outfile.create_group(
            f"{S1_SLC_HDF5_PREFIX}/metadata/processing_information/input_burst_metadata/azimuth_fm_rate")
        azimuth_fm_rate_coeffs_dset = azimuth_fm_rate_grp.create_dataset("coeffs",
                                                                         data=np.array([-2.32880269e+03, 4.49603956e+05,
                                                                                        -7.86316555e+07]),
                                                                         dtype='float64')
        azimuth_fm_rate_mean_dset = azimuth_fm_rate_grp.create_dataset("mean", data=800082.3526126802, dtype='float64')
        azimuth_fm_rate_order_dset = azimuth_fm_rate_grp.create_dataset("order", data=2, dtype='int64')
        azimuth_fm_rate_std_dset = azimuth_fm_rate_grp.create_dataset("std", data=149896229.0, dtype='float64')
        azimuth_steering_rate_dset = input_burst_metadata_grp.create_dataset("azimuth_steering_rate",
                                                                             data=0.027757171601738514, dtype='float64')
        azimuth_time_interval_dset = input_burst_metadata_grp.create_dataset("azimuth_time_interval",
                                                                             data=0.002055556299999998, dtype='float64')
        center_dset = input_burst_metadata_grp.create_dataset("center", data=np.array([-118.30363047, 33.8399832]),
                                                              dtype='float64')
        doppler_grp = outfile.create_group(f"{S1_SLC_HDF5_PREFIX}"
                                           f"/metadata/processing_information/input_burst_metadata/doppler")
        doppler_coeffs_dset = doppler_grp.create_dataset("coeffs",
                                                         data=np.array([-3.356279e+01, 8.696714e+04, -8.216876e+07]),
                                                         dtype='float64')
        doppler_mean_dset = doppler_grp.create_dataset("mean", data=800229.7806151338, dtype='float64')
        doppler_order_dset = doppler_grp.create_dataset("order", data=2, dtype='int64')
        doppler_std_dset = doppler_grp.create_dataset("std", data=149896229.0, dtype='float64')
        ipf_version_dset = input_burst_metadata_grp.create_dataset("ipf_version", data=np.string_("3.51"))
        iw2_mid_range_dset = input_burst_metadata_grp.create_dataset("iw2_mid_range", data=876175.1695277416,
                                                                     dtype='float64')
        platform_id_dset = input_burst_metadata_grp.create_dataset("platform_id", data=np.string_("S1A"))
        polarization_dset = input_burst_metadata_grp.create_dataset("polarization", data=np.string_("VV"))
        prf_raw_data_dset = input_burst_metadata_grp.create_dataset("prf_raw_data", data=1717.128973878037,
                                                                    dtype='float64')
        radar_center_frequency_dset = input_burst_metadata_grp.create_dataset("radar_center_frequency",
                                                                              data=5405000454.33435, dtype='float64')
        range_bandwidth_dset = input_burst_metadata_grp.create_dataset("range_bandwidth", data=56500000.0,
                                                                       dtype='float64')
        range_chirp_rate_dset = input_burst_metadata_grp.create_dataset("range_chirp_rate", data=1078230321255.894,
                                                                        dtype='float64')
        range_pixel_spacing_dset = input_burst_metadata_grp.create_dataset("range_pixel_spacing",
                                                                           data=2.329562114715323, dtype='float64')
        range_sampling_rate_dset = input_burst_metadata_grp.create_dataset("range_sampling_rate",
                                                                           data=64345238.12571428, dtype='float64')
        range_window_coefficient_dset = input_burst_metadata_grp.create_dataset('range_window_coefficient', data=0.75,
                                                                                dtype='float64')
        range_window_type_dset = input_burst_metadata_grp.create_dataset("range_window_type",
                                                                         data=np.string_('Hamming'))
        rank_dset = input_burst_metadata_grp.create_dataset("rank", data=9, dtype='int64')
        sensing_start_dset = input_burst_metadata_grp.create_dataset("sensing_start",
                                                                     data=np.string_('2022-05-01 01:50:35.031073'))
        sensing_stop_dset = input_burst_metadata_grp.create_dataset("sensing_stop",
                                                                    data=np.string_('2022-05-01 01:50:38.106185'))
        shape_dset = input_burst_metadata_grp.create_dataset("shape", data=np.array([1497, 21576]), dtype='int64')
        slant_range_time_dset = input_burst_metadata_grp.create_dataset("slant_range_time",
                                                                        data=0.00533757492066515, dtype='float64')
        starting_range_dset = input_burst_metadata_grp.create_dataset("starting_range",
                                                                      data=800082.3526126802, dtype='float64')
        wavelength_dset = input_burst_metadata_grp.create_dataset("wavelength", data=0.05546576, dtype='float64')

        orbit_grp = outfile.create_group(f"{S1_SLC_HDF5_PREFIX}/metadata/orbit")
        orbit_direction_dset = orbit_grp.create_dataset("orbit_direction", data=np.string_("Ascending"))
        orbit_type_dset = orbit_grp.create_dataset("orbit_type", data=np.string_("POE"))
        position_x_dset = orbit_grp.create_dataset("position_x", data=np.zeros((12,)), dtype='float64')
        position_y_dset = orbit_grp.create_dataset("position_y", data=np.zeros((12,)), dtype='float64')
        position_z_dset = orbit_grp.create_dataset("position_z", data=np.zeros((12,)), dtype='float64')
        reference_epoch_dset = orbit_grp.create_dataset("reference_epoch",
                                                        data=np.string_('2022-04-29 01:50:35.031073000'))
        time_dset = orbit_grp.create_dataset("time", data=np.zeros(12,), dtype='float64')
        velocity_x_dset = orbit_grp.create_dataset("velocity_x", data=np.zeros(12,), dtype='float64')
        velocity_y_dset = orbit_grp.create_dataset("velocity_y", data=np.zeros(12, ), dtype='float64')
        velocity_z_dset = orbit_grp.create_dataset("velocity_z", data=np.zeros(12, ), dtype='float64')

        quality_assurance_grp = outfile.create_group(f"{S1_SLC_HDF5_PREFIX}/quality_assurance")
        orbit_information_grp = quality_assurance_grp.create_group('orbit_information')
        qa_orbit_type_dset = orbit_information_grp.create_dataset('orbit_type', data=np.string_('precise_orbit_file'))
        pixel_classification_grp = quality_assurance_grp.create_group('pixel_classification')
        percent_land_pixels_dset = pixel_classification_grp.create_dataset('percent_land_pixels',
                                                                           data=59.38486551338992, dtype='float64')
        percent_valid_pixels_dset = pixel_classification_grp.create_dataset('percent_valid_pixels', data=100.0,
                                                                            dtype='float64')
        statistics_grp = quality_assurance_grp.create_group('statistics')
        static_layers_grp = statistics_grp.create_group('static_layers')
        local_incidence_angle_grp = static_layers_grp.create_group('local_incidence_angle')
        max_dset = local_incidence_angle_grp.create_dataset('max', data=76.16073608398438, dtype='float64')
        mean_dset = local_incidence_angle_grp.create_dataset('mean', data=36.48636245727539, dtype='float64')
        min_dset = local_incidence_angle_grp.create_dataset('min', data=0.1674480438232422, dtype='float64')
        std_dest = local_incidence_angle_grp.create_dataset('std', data=3.5223963260650635, dtype='float64')


def get_disp_s1_product_metadata(file_name):
    """
    Returns a python dict containing the DISP S1 metadata
    which will be used with the ISO metadata template.

    Parameters
    ----------
    file_name : str
        the DISP S1 metadata file.

    Returns
    -------
    disp_metadata : dict
        python dict containing the HDF5 file metadata which is used in the
        ISO template.
    """
    disp_metadata = {
        'x': get_hdf5_group_as_dict(file_name, "/x"),
        'y': get_hdf5_group_as_dict(file_name, "/y"),
        'identification': get_hdf5_group_as_dict(file_name, "/identification"),
        'metadata': get_hdf5_group_as_dict(file_name, "/metadata")
    }

    return disp_metadata


def create_test_disp_metadata_product(file_path):
    # pylint: disable=unused-variable,invalid-name,too-many-locals,too-many-statements,too-many-boolean-expressions
    """
    Creates a dummy DISP-S1 h5 metadata file with expected groups and datasets.
    This function is intended for use with unit tests, but is included in this
    module, so it will be importable from within a built container.

    Parameters
    ----------
    file_path : str
        Full path to write the dummy DISP H5 metadata file to.

    """
    pge_runconfig_contents = """
    input_file_group:
        cslc_file_list:
          - input_slcs/compressed_slc_t087_185683_iw2_20180101_20180210.h5
          - input_slcs/t087_185683_iw2_20180222_VV.h5
        frame_id: 11114
    log_file: output/pge_logfile.log
    """

    with h5py.File(file_path, 'w') as outfile:
        x_dset = outfile.create_dataset("x", data=np.zeros(10,), dtype='float64')
        y_dset = outfile.create_dataset("y", data=np.zeros(10,), dtype='float64')

        identification_grp = outfile.create_group("/identification")
        frame_id_dset = identification_grp.create_dataset("frame_id", data=123, dtype='int64')
        product_version_dset = identification_grp.create_dataset("product_version",
                                                                 data=np.string_("0.2"))
        zero_doppler_start_time_dset = identification_grp.create_dataset("zero_doppler_start_time",
                                                                         data=np.string_("2022-12-13 14:07:50.748411"))
        zero_doppler_end_time_dset = identification_grp.create_dataset("zero_doppler_end_time",
                                                                       data=np.string_("2022-12-13 14:07:56.584135"))
        bounding_polygon_dset = identification_grp.create_dataset("bounding_polygon",
                                                                  data=np.string_("POLYGON ((-119.26 39.15, -119.32 39.16, -119.22 39.32, -119.26 39.15))"))
        radar_wavelength_dset = identification_grp.create_dataset("radar_wavelength",
                                                                  data=0.05546576, dtype='float64')

        metadata_grp = outfile.create_group("/metadata")
        disp_s1_software_version_dset = metadata_grp.create_dataset("disp_s1_software_version",
                                                                          data=np.string_("0.1.0"))
        dolphin_software_version_dset = metadata_grp.create_dataset("dolphin_software_version",
                                                                          data=np.string_("0.5.1"))
        pge_runconfig_dset = metadata_grp.create_dataset("pge_runconfig",
                                                         data=np.string_(pge_runconfig_contents))
