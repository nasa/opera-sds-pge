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
except ImportError:  # pragma: no cover
    osr = MockOsr                           # pragma: no cover
# pylint: enable=import-error,invalid-name

MEASURED_PARAMETER_PATH_SEPARATOR = '/'
"""Character used to delimit HDF5 metadata subgroup "paths" in measured parameter config YAML files"""


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

        result = convert_h5py_dataset(group_object) if isinstance(group_object, h5py.Dataset) else \
            convert_h5py_group_to_dict(group_object, ignore_keys)

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
    elif isinstance(dataset_object[()], (bytes, np.bytes_)):
        # decode bytes to str
        result = dataset_object.asstr()[()]
    else:
        result = dataset_object[()]

    return result


def get_hdf5_attrs_as_dict(file_name, group_path):
    """
    Returns HDF5 group attributes as a python dict for a given file and group
    path.

    Variable data are not included.

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

        result = {k:v.decode('UTF-8') for k,v in group_object.attrs.items()}

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
                                                                 data=np.bytes_('Interferometric Wide (IW)'))
        beamID_dset = identification_grp.create_dataset("beamID", data=np.bytes_('iw1'))
        boundingBox_dset = identification_grp.create_dataset("boundingBox", data=np.array([200700.0, 9391650.0,
                                                                                           293730.0, 9440880.0]))
        boundingPolygon_dset = identification_grp.create_dataset(
            "boundingPolygon", data=b'POLYGON ((399015 3859970, 398975 3860000, ..., 399015 3859970))')
        burstID_dset = identification_grp.create_dataset("burstID", data=b't069_147170_iw1')
        contactInformation_dset = identification_grp.create_dataset("contactInformation", data=b'operasds@jpl.nasa.gov')
        ceosAnalysisReadyDataDocumentIdentifier_dset = identification_grp.create_dataset(
            "ceosAnalysisReadyDataDocumentIdentifier",
            data=b'https://ceos.org/ard/files/PFS/NRB/v5.5/CARD4L-PFS_NRB_v5.5.pdf'
        )
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
                                                                    data=np.bytes_('2023-03-23T20:32:18.962836Z'))
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
        'processing_information': get_hdf5_group_as_dict(
            file_name,
            f"{S1_SLC_HDF5_PREFIX}/metadata/processing_information"
        ),
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
            "bounding_polygon", data=np.bytes_("POLYGON ((-118.77 33.67, -118.72 33.68, ..., -118.77 33.67))"))
        burst_id_dset = identification_grp.create_dataset("burst_id", data=np.bytes_("t064_135518_iw1"))
        instrument_name_dset = identification_grp.create_dataset("instrument_name", data=np.bytes_('C-SAR'))
        is_geocoded_flag_dset = identification_grp.create_dataset("is_geocoded", data=True, dtype='bool')
        look_direction_dset = identification_grp.create_dataset("look_direction", data=np.bytes_("Right"))
        mission_id_dset = identification_grp.create_dataset("mission_id", data=np.bytes_("S1A"))
        orbit_pass_direction_dset = identification_grp.create_dataset("orbit_pass_direction",
                                                                      data=np.bytes_("Ascending"))
        processing_center_dset = identification_grp.create_dataset("processing_center",
                                                                   data=np.bytes_("Jet Propulsion Laboratory"))
        processing_date_time_dset = identification_grp.create_dataset("processing_date_time",
                                                                      data=np.bytes_("2023-06-05 21:43:21.317243"))
        product_level_dset = identification_grp.create_dataset("product_level", data=np.bytes_("L2"))
        product_specification_version_dset = identification_grp.create_dataset("product_specification_version",
                                                                               data=np.bytes_("3.2.1"))
        product_type_dset = identification_grp.create_dataset("product_type", data=np.bytes_("CSLC-S1"))
        product_version_dset = identification_grp.create_dataset("product_version", data=np.bytes_("1.0"))
        radar_band_dset = identification_grp.create_dataset("radar_band", data=np.bytes_("C"))
        track_number_dset = identification_grp.create_dataset("track_number", data=64, dtype="int64")
        zero_doppler_end_time_dset = identification_grp.create_dataset("zero_doppler_end_time",
                                                                       data=np.bytes_("2022-05-01 01:50:38.106185"))
        zero_doppler_start_time_dset = identification_grp.create_dataset("zero_doppler_start_time",
                                                                         data=np.bytes_("2022-05-01 01:50:35.031073"))

        data_grp = outfile.create_group(f"{S1_SLC_HDF5_PREFIX}/data")
        projection_dset = data_grp.create_dataset("projection", data=32611, dtype='int32')
        x_coordinates_dset = data_grp.create_dataset("x_coordinates", data=np.zeros((10,)), dtype='float64')
        x_spacing_dset = data_grp.create_dataset("x_spacing", data=5.0, dtype="float64")
        y_coordinates_dset = data_grp.create_dataset("y_coordinates", data=np.zeros((10,)), dtype='float64')
        y_spacing_dset = data_grp.create_dataset("y_spacing", data=-10.0, dtype='float64')

        processing_information_grp = outfile.create_group(f"{S1_SLC_HDF5_PREFIX}/metadata/processing_information")

        algorithms_grp = outfile.create_group(f"{S1_SLC_HDF5_PREFIX}/metadata/processing_information/algorithms")
        COMPASS_version_dset = algorithms_grp.create_dataset("COMPASS_version", data=np.bytes_("0.1.3"))
        ISCE3_version_dset = algorithms_grp.create_dataset("ISCE3_version", data=np.bytes_("0.9.0"))
        dem_interpolation_dset = algorithms_grp.create_dataset("dem_interpolation", data=np.bytes_("biquintic"))
        complex_data_geocoding_interpolator_dset = algorithms_grp.create_dataset("complex_data_geocoding_interpolator",
                                                                                 data=np.bytes_("sinc interpolation"))
        float_data_geocoding_interpolator_dset = algorithms_grp.create_dataset(
            "float_data_geocoding_interpolator", data=np.bytes_("biquintic interpolation"))
        topography_algorithm_dset = algorithms_grp.create_dataset("topography_algorithm",
                                                                  data=np.bytes_("isce3.geometry.topo"))
        uint_data_geocoding_interpolator = algorithms_grp.create_dataset(
            "uint_data_geocoding_interpolator", data=np.bytes_("nearest neighbor interpolation"))
        s1_reader_version_dset = algorithms_grp.create_dataset("s1_reader_version", data=np.bytes_("0.2.0"))

        inputs_grp = outfile.create_group(f"{S1_SLC_HDF5_PREFIX}/metadata/processing_information/inputs")
        calibration_files_dset = inputs_grp.create_dataset("calibration_files", data=np.bytes_(
            'calibration-s1a-iw1-slc-vv-20220501t015035-20220501t015102-043011-0522a4-004.xml'))
        dem_source_dset = inputs_grp.create_dataset("dem_source", data=np.bytes_('dem_4326.tiff'))
        l1_slc_files_dset = inputs_grp.create_dataset('l1_slc_files', data=np.bytes_(
            'S1A_IW_SLC__1SDV_20220501T015035_20220501T015102_043011_0522A4_42CC'))
        noise_files_dset = inputs_grp.create_dataset("noise_files", data=np.bytes_(
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
        tiff_path_dset = burst_location_parameters_grp.create_dataset("tiff_path", data=np.bytes_(
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
            "elevation_antenna_pattern_correction_applied", data=np.bytes_("ESA"))
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
        ipf_version_dset = input_burst_metadata_grp.create_dataset("ipf_version", data=np.bytes_("3.51"))
        iw2_mid_range_dset = input_burst_metadata_grp.create_dataset("iw2_mid_range", data=876175.1695277416,
                                                                     dtype='float64')
        platform_id_dset = input_burst_metadata_grp.create_dataset("platform_id", data=np.bytes_("S1A"))
        polarization_dset = input_burst_metadata_grp.create_dataset("polarization", data=np.bytes_("VV"))
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
                                                                         data=np.bytes_('Hamming'))
        rank_dset = input_burst_metadata_grp.create_dataset("rank", data=9, dtype='int64')
        sensing_start_dset = input_burst_metadata_grp.create_dataset("sensing_start",
                                                                     data=np.bytes_('2022-05-01 01:50:35.031073'))
        sensing_stop_dset = input_burst_metadata_grp.create_dataset("sensing_stop",
                                                                    data=np.bytes_('2022-05-01 01:50:38.106185'))
        shape_dset = input_burst_metadata_grp.create_dataset("shape", data=np.array([1497, 21576]), dtype='int64')
        slant_range_time_dset = input_burst_metadata_grp.create_dataset("slant_range_time",
                                                                        data=0.00533757492066515, dtype='float64')
        starting_range_dset = input_burst_metadata_grp.create_dataset("starting_range",
                                                                      data=800082.3526126802, dtype='float64')
        wavelength_dset = input_burst_metadata_grp.create_dataset("wavelength", data=0.05546576, dtype='float64')

        orbit_grp = outfile.create_group(f"{S1_SLC_HDF5_PREFIX}/metadata/orbit")
        orbit_direction_dset = orbit_grp.create_dataset("orbit_direction", data=np.bytes_("Ascending"))
        orbit_type_dset = orbit_grp.create_dataset("orbit_type", data=np.bytes_("POE"))
        position_x_dset = orbit_grp.create_dataset("position_x", data=np.zeros((12,)), dtype='float64')
        position_y_dset = orbit_grp.create_dataset("position_y", data=np.zeros((12,)), dtype='float64')
        position_z_dset = orbit_grp.create_dataset("position_z", data=np.zeros((12,)), dtype='float64')
        reference_epoch_dset = orbit_grp.create_dataset("reference_epoch",
                                                        data=np.bytes_('2022-04-29 01:50:35.031073000'))
        time_dset = orbit_grp.create_dataset("time", data=np.zeros(12,), dtype='float64')
        velocity_x_dset = orbit_grp.create_dataset("velocity_x", data=np.zeros(12,), dtype='float64')
        velocity_y_dset = orbit_grp.create_dataset("velocity_y", data=np.zeros(12, ), dtype='float64')
        velocity_z_dset = orbit_grp.create_dataset("velocity_z", data=np.zeros(12, ), dtype='float64')

        quality_assurance_grp = outfile.create_group(f"{S1_SLC_HDF5_PREFIX}/quality_assurance")
        orbit_information_grp = quality_assurance_grp.create_group('orbit_information')
        qa_orbit_type_dset = orbit_information_grp.create_dataset('orbit_type', data=np.bytes_('precise_orbit_file'))
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


def create_test_disp_metadata_product(
        file_path,
        omit_cslc_measured_parameters=False
):
    # pylint: disable=unused-variable,invalid-name,too-many-locals,too-many-statements,too-many-boolean-expressions
    # pylint: disable=line-too-long
    """
    Creates a dummy DISP-S1 h5 metadata file with expected groups and datasets.
    This function is intended for use with unit tests, but is included in this
    module, so it will be importable from within a built container.

    Parameters
    ----------
    file_path : str
        Full path to write the dummy DISP H5 metadata file to.
    omit_cslc_measured_parameters : bool
        If true, do not create dummy datasets for datasets copied from the input CSLC
        (https://github.com/opera-adt/disp-s1/blob/fa562e194f26ebdadfdbe6f0defe80b55f212b4a/src/disp_s1/product.py#L1614-L1647)

    """
    # pylint: enable=line-too-long
    pge_runconfig_contents = """
    input_file_group:
        cslc_file_list:
          - input_slcs/compressed_slc_t087_185683_iw2_20180101_20180210.h5
          - input_slcs/t087_185683_iw2_20180222_VV.h5
        frame_id: 11114
    log_file: output/pge_logfile.log
    """

    algorithm_parameters_contents = """
    dummy yaml data
    """

    dolphin_workflow_config_contents = """
    dummy yaml data
    """

    with h5py.File(file_path, 'w') as outfile:
        x_dset = outfile.create_dataset("x", data=np.zeros(10, ), dtype='float64')
        y_dset = outfile.create_dataset("y", data=np.zeros(10, ), dtype='float64')

        identification_grp = outfile.create_group("/identification")
        frame_id_dset = identification_grp.create_dataset("frame_id", data=123, dtype='int64')
        product_version_dset = identification_grp.create_dataset("product_version",
                                                                 data=np.bytes_("0.2"))
        reference_zero_doppler_start_time_dset = identification_grp.create_dataset("reference_zero_doppler_start_time",
                                                                                   data=np.bytes_(
                                                                                       "2017-02-17 13:27:50.139658"))
        reference_zero_doppler_end_time_dset = identification_grp.create_dataset("reference_zero_doppler_end_time",
                                                                                 data=np.bytes_(
                                                                                     "2017-02-17 13:27:55.979493"))
        secondary_zero_doppler_start_time_dset = identification_grp.create_dataset("secondary_zero_doppler_start_time",
                                                                                   data=np.bytes_(
                                                                                       "2017-04-30 13:27:52.049224"))
        secondary_zero_doppler_end_time_dset = identification_grp.create_dataset("secondary_zero_doppler_end_time",
                                                                                 data=np.bytes_(
                                                                                     "2017-04-30 13:27:57.891116"))
        bounding_polygon_dset = identification_grp.create_dataset(
              "bounding_polygon",
              data=np.bytes_(
                  "POLYGON ((-119.26 39.15, -119.32 39.16, -119.22 39.32, -119.26 39.15))")
        )
        radar_wavelength_dset = identification_grp.create_dataset("radar_wavelength",
                                                                  data=0.05546576, dtype='float64')
        reference_datetime_dset = identification_grp.create_dataset("reference_datetime",
                                                                    data=np.bytes_("2022-11-07 00:00:00.000000"))
        secondary_datetime_dset = identification_grp.create_dataset("secondary_datetime",
                                                                    data=np.bytes_("2022-12-13 00:00:00.000000"))
        average_temporal_coherence_dset = identification_grp.create_dataset("average_temporal_coherence",
                                                                            data=0.9876175064678105, dtype='float64')
        ceos_analysis_ready_data_document_identifier_dset = identification_grp.create_dataset(
            "ceos_analysis_ready_data_document_identifier",
            data=np.bytes_("https://ceos.org/ard/files/PFS/NRB/v5.5/CARD4L-PFS_NRB_v5.5.pdf"))
        source_data_processing_facility_dset = identification_grp.create_dataset(
            "source_data_processing_facility",
            data=np.bytes_("NASA Jet Propulsion Laboratory on AWS")
        )
        source_data_imaging_geometry_dset = identification_grp.create_dataset(
            "source_data_imaging_geometry",
            data=np.bytes_("Geocoded")
        )
        source_data_acquisition_polarization_dset = identification_grp.create_dataset(
            "source_data_acquisition_polarization",
            data=np.bytes_("VV/VH")
        )
        source_data_access_dset = identification_grp.create_dataset(
            "source_data_access",
            data=np.bytes_(
                "OPERA_L2_CSLC-S1_T027-056725-IW1_20170217T132750Z_20240625T060850Z_S1A_VV_v1.1,"
                "OPERA_L2_CSLC-S1_T027-056726-IW1_20170217T132752Z_20240625T060850Z_S1A_VV_v1.1")
        )
        source_data_x_spacing_dset = identification_grp.create_dataset("source_data_x_spacing", data=5, dtype='int64')
        source_data_y_spacing_dset = identification_grp.create_dataset("source_data_y_spacing", data=10, dtype='int64')
        near_range_incidence_angle_dset = identification_grp.create_dataset("near_range_incidence_angle", data=30.9,
                                                                            dtype='float32')
        far_range_incidence_angle_dset = identification_grp.create_dataset("far_range_incidence_angle", data=36.8,
                                                                           dtype='float32')
        product_sample_spacing_dset = identification_grp.create_dataset("product_sample_spacing", data=30,
                                                                        dtype='int64')
        nodata_pixel_count_dset = identification_grp.create_dataset("nodata_pixel_count", data=65399573,
                                                                    dtype='int64')
        product_bounding_box_dset = identification_grp.create_dataset("product_bounding_box", data=np.bytes_(
            "280230.0,3555240.0,572310.0,3767970.0"))
        product_pixel_coordinate_convention_dset = identification_grp.create_dataset(
            "product_pixel_coordinate_convention", data=np.bytes_("center"))
        mission_id_dset = identification_grp.create_dataset("mission_id", data=np.bytes_("S1A"))
        if not omit_cslc_measured_parameters:
            instrument_name_dset = identification_grp.create_dataset("instrument_name", data=np.bytes_("C-SAR"))
            look_direction_dset = identification_grp.create_dataset("look_direction", data=np.bytes_("Right"))
            track_number_dset = identification_grp.create_dataset("track_number", data=27, dtype='int64')
            orbit_pass_direction_dset = identification_grp.create_dataset("orbit_pass_direction",
                                                                          data=np.bytes_("Descending"))
            absolute_orbit_number_dset = identification_grp.create_dataset("absolute_orbit_number", data=15324,
                                                                           dtype="int64")

        acquisition_mode_dset = identification_grp.create_dataset("acquisition_mode", data=np.bytes_("IW"))
        ceos_analysis_ready_data_product_type_dset = identification_grp.create_dataset(
            "ceos_analysis_ready_data_product_type", data=np.bytes_("InSAR"))
        ceos_number_of_input_granules_dset = identification_grp.create_dataset("ceos_number_of_input_granules",
                                                                               data=14, dtype="int64")
        processing_facility_dset = identification_grp.create_dataset("processing_facility", data=np.bytes_(
            "NASA Jet Propulsion Laboratory on AWS"))
        processing_start_datetime_dset = identification_grp.create_dataset("processing_start_datetime",
                                                                           data=np.bytes_("2025-01-17 22:47:38"))
        product_data_polarization_dset = identification_grp.create_dataset("product_data_polarization",
                                                                           data=np.bytes_("VV"))
        product_data_access_dset = identification_grp.create_dataset("product_data_access", data=np.bytes_(
            "https://search.asf.alaska.edu/#/?dataset=OPERA-S1&productTypes=DISP-S1"))
        radar_center_frequency_dset = identification_grp.create_dataset("radar_center_frequency", data=5405000454.33435,
                                                                        dtype="float64")
        source_data_azimuth_resolutions_dset = identification_grp.create_dataset("source_data_azimuth_resolutions",
                                                                                 data=np.bytes_("[22.5, 22.7, 22.6]"))
        source_data_dem_name_dset = identification_grp.create_dataset("source_data_dem_name",
                                                                      data=np.bytes_("Copernicus GLO-30"))
        source_data_earliest_acquisition_dset = identification_grp.create_dataset("source_data_earliest_acquisition",
                                                                                  data=np.bytes_("2017-02-17T00:00:00"))
        source_data_earliest_processing_datetime_dset = identification_grp.create_dataset(
            "source_data_earliest_processing_datetime", data=np.bytes_("2024-06-25T00:00:00"))
        source_data_file_list_dset = identification_grp.create_dataset("source_data_file_list", data=np.bytes_(
            "OPERA_L2_CSLC-S1_T027-056725-IW1_20170217T132750Z_20240625T060850Z_S1A_VV_v1.1,"
            "OPERA_L2_CSLC-S1_T027-056726-IW1_20170217T132752Z_20240625T060850Z_S1A_VV_v1.1,"
            "OPERA_L2_CSLC-S1_T027-056725-IW1_20170301T132749Z_20240625T090210Z_S1A_VV_v1.1,"
            "OPERA_L2_CSLC-S1_T027-056726-IW1_20170301T132752Z_20240625T090210Z_S1A_VV_v1.1,"
            "OPERA_L2_CSLC-S1_T027-056725-IW1_20170313T132750Z_20240625T121542Z_S1A_VV_v1.1,"
            "OPERA_L2_CSLC-S1_T027-056726-IW1_20170313T132753Z_20240625T121542Z_S1A_VV_v1.1,"
            "OPERA_L2_CSLC-S1_T027-056725-IW1_20170325T132750Z_20240625T163704Z_S1A_VV_v1.1,"
            "OPERA_L2_CSLC-S1_T027-056726-IW1_20170325T132753Z_20240625T163704Z_S1A_VV_v1.1,"
            "OPERA_L2_CSLC-S1_T027-056725-IW1_20170406T132750Z_20240625T225442Z_S1A_VV_v1.1,"
            "OPERA_L2_CSLC-S1_T027-056726-IW1_20170406T132753Z_20240625T225442Z_S1A_VV_v1.1,"
            "OPERA_L2_CSLC-S1_T027-056725-IW1_20170418T132751Z_20240626T003055Z_S1A_VV_v1.1,"
            "OPERA_L2_CSLC-S1_T027-056726-IW1_20170418T132754Z_20240626T003055Z_S1A_VV_v1.1,"
            "OPERA_L2_CSLC-S1_T027-056725-IW1_20170430T132752Z_20240626T015700Z_S1A_VV_v1.1,"
            "OPERA_L2_CSLC-S1_T027-056726-IW1_20170430T132754Z_20240626T015700Z_S1A_VV_v1.1"))
        source_data_latest_acquisition_dset = identification_grp.create_dataset("source_data_latest_acquisition",
                                                                                data=np.bytes_("2017-04-30T00:00:00"))
        source_data_latest_processing_datetime_dset = identification_grp.create_dataset(
            "source_data_latest_processing_datetime", data=np.bytes_("2024-06-26T00:00:00"))
        source_data_max_noise_equivalent_sigma_zero_dset = identification_grp.create_dataset(
            "source_data_max_noise_equivalent_sigma_zero", data=-22.0, dtype="float64")
        source_data_original_institution_dset = identification_grp.create_dataset("source_data_original_institution",
                                                                                  data=np.bytes_(
                                                                                      "European Space Agency"))
        source_data_polarization_dset = identification_grp.create_dataset("source_data_polarization",
                                                                          data=np.bytes_("VV"))
        source_data_range_resolutions_dset = identification_grp.create_dataset("source_data_range_resolutions",
                                                                               data=np.bytes_("[2.7, 3.1, 3.5]"))
        source_data_reference_orbit_type_dset = identification_grp.create_dataset("source_data_reference_orbit_type",
                                                                                  data=np.bytes_("precise orbit file"))
        source_data_satellite_names_dset = identification_grp.create_dataset("source_data_satellite_names",
                                                                             data=np.bytes_("S1A"))
        source_data_secondary_orbit_type_dset = identification_grp.create_dataset("source_data_secondary_orbit_type",
                                                                                  data=np.bytes_("precise orbit file"))
        static_layers_data_access_dset = identification_grp.create_dataset(
           "static_layers_data_access",
           data=np.bytes_(
               "https://search.asf.alaska.edu/#/?dataset=OPERA-S1&productTypes=DISP-S1-STATIC&frame=7091")
        )
        radar_band_dset = identification_grp.create_dataset("radar_band", data=np.bytes_("C"))

        metadata_grp = outfile.create_group("/metadata")
        product_landing_page_doi_dset = metadata_grp.create_dataset(
            "product_landing_page_doi",
            data=np.bytes_("https://doi.org/10.5067/SNWG/OPL3DISPS1-V1")
        )
        disp_s1_software_version_dset = metadata_grp.create_dataset("disp_s1_software_version",
                                                                    data=np.bytes_("0.2.7"))
        dolphin_software_version_dset = metadata_grp.create_dataset("dolphin_software_version",
                                                                    data=np.bytes_("0.15.3"))
        pge_runconfig_dset = metadata_grp.create_dataset("pge_runconfig",
                                                         data=np.bytes_(pge_runconfig_contents))
        algorithm_parameters_yaml_dset = metadata_grp.create_dataset("algorithm_parameters_yaml",
                                                                     data=np.bytes_(algorithm_parameters_contents))
        dolphin_workflow_config_dset = metadata_grp.create_dataset("dolphin_workflow_config",
                                                                   data=np.bytes_(dolphin_workflow_config_contents))
        algorithm_theoretical_basis_document_doi_dset = metadata_grp.create_dataset(
            "algorithm_theoretical_basis_document_doi", data=np.bytes_("https://doi.org/10.5067/SNWG/OPL3DISPS1-V1"))
        ceos_product_measurement_projection_dset = metadata_grp.create_dataset(
            "ceos_product_measurement_projection", data=np.bytes_("line of sight"))
        ceos_atmospheric_phase_correction_dset = metadata_grp.create_dataset("ceos_atmospheric_phase_correction",
                                                                             data=np.bytes_("None"))
        ceos_gridding_convention_dset = metadata_grp.create_dataset("ceos_gridding_convention", data=np.bytes_("Yes"))
        ceos_insar_pair_baseline_criteria_information_dset = metadata_grp.create_dataset(
            "ceos_insar_pair_baseline_criteria_information", data=np.bytes_("All"))
        ceos_insar_azimuth_common_band_filtering_dset = metadata_grp.create_dataset(
            "ceos_insar_azimuth_common_band_filtering", data=np.bytes_("False"))
        ceos_insar_range_spectral_shift_filtering_dset = metadata_grp.create_dataset(
            "ceos_insar_range_spectral_shift_filtering", data=np.bytes_("False"))
        ceos_insar_orbital_baseline_refinement_dset = metadata_grp.create_dataset(
            "ceos_insar_orbital_baseline_refinement", data=np.bytes_("False"))
        ceos_shp_selection_selection_criteria_dset = metadata_grp.create_dataset(
            "ceos_shp_selection_selection_criteria", data=np.bytes_("glrt"))
        ceos_shp_selection_window_size = metadata_grp.create_dataset(
            "ceos_shp_selection_window_size", data=np.bytes_("11x23"))
        ceos_shp_selection_selection_threshold = metadata_grp.create_dataset(
            "ceos_shp_selection_selection_threshold", data=0.001, dtype="float64")
        ceos_ionospheric_phase_correction_dset = metadata_grp.create_dataset("ceos_ionospheric_phase_correction",
                                                                             data=np.bytes_("None"))
        ceos_noise_removal_dset = metadata_grp.create_dataset("ceos_noise_removal", data=np.bytes_("No"))
        ceos_absolute_geolocation_ground_range_bias_dset = metadata_grp.create_dataset(
            "ceos_absolute_geolocation_ground_range_bias", data=-0.06, dtype="float64")
        ceos_absolute_geolocation_ground_range_stddev_dset = metadata_grp.create_dataset(
            "ceos_absolute_geolocation_ground_range_stddev", data=0.38, dtype="float64")
        ceos_absolute_geolocation_azimuth_bias_dset = metadata_grp.create_dataset(
            "ceos_absolute_geolocation_azimuth_bias", data=-0.04, dtype="float64")
        ceos_absolute_geolocation_azimuth_stddev_dset = metadata_grp.create_dataset(
            "ceos_absolute_geolocation_azimuth_stddev", data=0.46, dtype="float64")
        ceos_persistent_scatterer_amplitude_dispersion_threshold_dset = metadata_grp.create_dataset(
            "ceos_persistent_scatterer_amplitude_dispersion_threshold", data=0.15, dtype="float64")
        ceos_persistent_scatterer_selection_criteria_dset = metadata_grp.create_dataset(
            "ceos_persistent_scatterer_selection_criteria", data=np.bytes_("Amplitude Dispersion"))
        ceos_persistent_scatterer_selection_criteria_doi_dset = metadata_grp.create_dataset(
            "ceos_persistent_scatterer_selection_criteria_doi", data=np.bytes_("https://doi.org/10.1109/36.898661"))
        ceos_phase_similarity_metric_doi_dset = metadata_grp.create_dataset(
            "ceos_phase_similarity_metric_doi",
            data=np.bytes_(
                "https://doi.org/10.1109/TGRS.2022.3210868")
        )
        ceos_estimated_phase_quality_metric_algorithm_dset = metadata_grp.create_dataset(
            "ceos_estimated_phase_quality_metric_algorithm", data=np.bytes_("Gaussian filtering"))
        ceos_phase_unwrapping_method_dset = metadata_grp.create_dataset("ceos_phase_unwrapping_method",
                                                                        data=np.bytes_("UnwrapMethod.SNAPHU"))
        ceos_phase_unwrapping_snaphu_doi_dset = metadata_grp.create_dataset(
            "ceos_phase_unwrapping_snaphu_doi",data=np.bytes_("https://doi.org/10.1364/JOSAA.18.000338"))
        ceos_phase_unwrapping_spurt_doi_dset = metadata_grp.create_dataset(
            "ceos_phase_unwrapping_spurt_doi", data=np.bytes_("'https://doi.org/10.1016/j.rse.2023.113456'"))
        ceos_phase_unwrapping_similarity_threshold_dset = metadata_grp.create_dataset(
            "ceos_phase_unwrapping_similarity_threshold", data=0.4, dtype="float64")
        product_pixel_coordinate_convention_dset = metadata_grp.create_dataset("product_pixel_coordinate_convention",
                                                                               data=np.bytes_("center"))
        product_specification_document_id_dset = metadata_grp.create_dataset("product_specification_document_id",
                                                                             data=np.bytes_("JPL D-108278"))

        if not omit_cslc_measured_parameters:
            platform_id_dset = metadata_grp.create_dataset("platform_id", data=np.bytes_("S1A"))
            slant_range_mid_swath_dset = metadata_grp.create_dataset("slant_range_mid_swath", data=875720.2393261964,
                                                                     dtype="float64")
            source_data_software_COMPASS_version_dset = metadata_grp.create_dataset(
                "source_data_software_COMPASS_version",
                data=np.bytes_("0.5.5")
            )
            source_data_software_ISCE3_version_dset = metadata_grp.create_dataset("source_data_software_ISCE3_version",
                                                                                  data=np.bytes_("0.15.1"))
            source_data_software_s1_reader_version_dset = metadata_grp.create_dataset(
                "source_data_software_s1_reader_version", data=np.bytes_("0.2.4"))


def get_tropo_product_metadata(file_name):
    """
    Returns a python dict containing the TROPO metadata
    which will be used with the ISO metadata template.

    Parameters
    ----------
    file_name : str
        the TROPO metadata file.

    Returns
    -------
    tropo_metadata : dict
        python dict containing the HDF5 file metadata which is used in the
        ISO template.
    """
    # TODO: replace dummy hardcoded metadata with call to get_hdf5_attrs_as_dict()
    # tropo_metadata = get_hdf5_attrs_as_dict(file_name, "/")
    
    dummy_tropo_metadata = {
        "Conventions": "CF-1.8",
        "title": "OPERA_L4_TROPO-ZENITH",
        "institution": "NASA Jet Propulsion Laboratory (JPL)",
        "contact": "opera-sds-ops@jpl.nasa.gov",
        "source": "ECMWF",
        "platform": "Model High Resolution 15-day Forecast (HRES)",
        "spatial_resolution": "~0.07deg",
        "temporal_resolution": "6h",
        "source_url": "https://www.ecmwf.int/en/forecasts/datasets/set-i",
        "references": "https://raider.readthedocs.io/en/latest/",
        "mission_name": "OPERA",
        "description": "OPERA One-way Tropospheric Zenith-integrated Delay for Synthetic Aperture Radar",
        "comment": "Intersect/interpolate with DEM, project to slant range and multiple with -4pi/radar wavelength (2 way) to get SAR correction",
        "software": "RAiDER",
        "software_version": "0.5.3",
        "reference_document": "TBD",
        "history": "Created on: 2025-03-24 21:28:42.426525+00:00",
        "reference_time": "2024-02-15 12:00:00"
    }
    return dummy_tropo_metadata