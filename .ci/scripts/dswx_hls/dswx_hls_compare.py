#!/usr/bin/env python3
"""Compare DSWX-HLS products"""
import argparse
import os

import numpy as np

from osgeo import gdal

COMPARE_DSWX_HLS_PRODUCTS_ERROR_TOLERANCE = 1e-6

DEFAULT_METADATA_EXCLUDE_LIST = ['PROCESSING_DATETIME', 'DEM_SOURCE', 'LANDCOVER_SOURCE',
                                 'WORLDCOVER_SOURCE', 'SOFTWARE_VERSION', 'SENSOR']
PREFIX = ' ' * 7


def _get_prefix_str(flag_same, flag_all_ok):
    flag_all_ok[0] = flag_all_ok[0] and flag_same
    return '[OK]   ' if flag_same else '[FAIL] '


def _print_first_value_diff(image_1, image_2, prefix):
    """
    Print first value difference between two images.

       Parameters
       ----------
       image_1 : numpy.ndarray
            First input image
       image_2: numpy.ndarray
            Second input image
       prefix: str
            Prefix to the message printed to the user
    """
    flag_error_found = False
    for i in range(image_1.shape[0]):
        for j in range(image_1.shape[1]):
            if (abs(image_1[i, j] - image_2[i, j]) <=
                    COMPARE_DSWX_HLS_PRODUCTS_ERROR_TOLERANCE):
                continue
            print(prefix + f'     * input 1 has value'
                  f' "{image_1[i, j]}" in position'
                  f' (x: {j}, y: {i})'
                  f' whereas input 2 has value "{image_2[i, j]}"'
                  ' in the same position.')
            flag_error_found = True
            break
        if flag_error_found:
            break


def compare_dswx_hls_products(file_1, file_2, metadata_exclude_list):
    if not os.path.isfile(file_1):
        print(f'ERROR file not found: {file_1}')
        return False

    if not os.path.isfile(file_2):
        print(f'ERROR file not found: {file_2}')
        return False

    print('Comparing files:')
    print(f'    file 1: {file_1}')
    print(f'    file 2: {file_2}')

    flag_all_ok = [True]

    # TODO: compare projections ds.GetProjection()
    layer_gdal_dataset_1 = gdal.Open(file_1, gdal.GA_ReadOnly)
    geotransform_1 = layer_gdal_dataset_1.GetGeoTransform()
    metadata_1 = layer_gdal_dataset_1.GetMetadata()
    nbands_1 = layer_gdal_dataset_1.RasterCount

    layer_gdal_dataset_2 = gdal.Open(file_2, gdal.GA_ReadOnly)
    geotransform_2 = layer_gdal_dataset_2.GetGeoTransform()
    metadata_2 = layer_gdal_dataset_2.GetMetadata()
    nbands_2 = layer_gdal_dataset_2.RasterCount

    # compare number of bands
    flag_same_nbands =  nbands_1 == nbands_2
    flag_same_nbands_str = _get_prefix_str(flag_same_nbands, flag_all_ok)
    prefix = ' ' * 7
    print(f'{flag_same_nbands_str}Comparing number of bands')
    if not flag_same_nbands:
        print(prefix + f'Input 1 has {nbands_1} bands and input 2'
              f' has {nbands_2} bands')
        return False

    # compare array values
    print('Comparing DSWx bands...')
    for b in range(1, nbands_1 + 1):
        gdal_band_1 = layer_gdal_dataset_1.GetRasterBand(b)
        gdal_band_2 = layer_gdal_dataset_2.GetRasterBand(b)
        image_1 = gdal_band_1.ReadAsArray()
        image_2 = gdal_band_2.ReadAsArray()
        flag_bands_are_equal = np.allclose(
            image_1, image_2, atol=COMPARE_DSWX_HLS_PRODUCTS_ERROR_TOLERANCE,
            equal_nan=True)
        flag_bands_are_equal_str = _get_prefix_str(flag_bands_are_equal,
                                                   flag_all_ok)
        print(f'{flag_bands_are_equal_str}     Band {b} -'
              f' {gdal_band_1.GetDescription()}"')
        if not flag_bands_are_equal:
            _print_first_value_diff(image_1, image_2, prefix)

    # compare geotransforms
    flag_same_geotransforms = np.array_equal(geotransform_1, geotransform_2)
    flag_same_geotransforms_str = _get_prefix_str(flag_same_geotransforms,
                                                  flag_all_ok)
    print(f'{flag_same_geotransforms_str}Comparing geotransform')
    if not flag_same_geotransforms:
        print(prefix + f'* input 1 geotransform with content "{geotransform_1}"'
              f' differs from input 2 geotransform with content'
              f' "{geotransform_2}".')

    # compare metadata
    metadata_error_message, flag_same_metadata = \
        _compare_dswx_hls_metadata(metadata_1, metadata_2, metadata_exclude_list)

    flag_same_metadata_str = _get_prefix_str(flag_same_metadata,
                                             flag_all_ok)
    print(f'{flag_same_metadata_str}Comparing metadata')

    if not flag_same_metadata:
        print(prefix + metadata_error_message)

    return flag_all_ok[0]


def _compare_dswx_hls_metadata(metadata_1, metadata_2, metadata_exclude_list):
    """
    Compare DSWx-HLS products' metadata

    Parameters
    ----------
    metadata_1 : dict
        Metadata of the first DSWx-HLS product
    metadata_2: dict
        Metadata of the second
    metadata_exclude_list: list
        List of metadata fields to ignore
    """
    metadata_error_message = None

    # Comparison of the "LICENSE" metadata field is skipped because it was
    # introduced later.
    for metadata_dict in [metadata_1, metadata_2]:
        if "LICENSE" in metadata_dict.keys():
            del metadata_dict["LICENSE"]

    flag_same_metadata = len(metadata_1.keys()) == len(metadata_2.keys())
    if not flag_same_metadata:
        metadata_error_message = (
            f'* input 1 metadata has {len(metadata_1.keys())} entries'
            f' whereas input 2 metadata has {len(metadata_2.keys())} entries.')

        set_1_m_2 = set(metadata_1.keys()) - set(metadata_2.keys())
        if len(set_1_m_2) > 0:
            metadata_error_message += (' Input 1 metadata has extra entries'
                                       ' with keys:'
                                       f' {", ".join(set_1_m_2)}.')
        set_2_m_1 = set(metadata_2.keys()) - set(metadata_1.keys())
        if len(set_2_m_1) > 0:
            metadata_error_message += (' Input 2 metadata has extra entries'
                                       ' with keys:'
                                       f' {", ".join(set_2_m_1)}.')
    else:
        for k1, v1, in metadata_1.items():
            if k1 not in metadata_2.keys():
                flag_same_metadata = False
                metadata_error_message = (
                    f'* the metadata key {k1} is present in'
                    ' but it is not present in input 2')
                break
            # Exclude metadata fields that are not required to be the same
            if k1 in metadata_exclude_list:
                continue
            if metadata_2[k1] != v1:
                flag_same_metadata = False
                metadata_error_message = (
                    f'* contents of metadata key {k1} from'
                    f' input 1 has value "{v1}" whereas the same key in'
                    f' input 2 metadata has value "{metadata_2[k1]}"')
                break
    return metadata_error_message, flag_same_metadata


if __name__ == "__main__":
    desc = "Compare two DSWx-HLS product files."
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('files', nargs=2, help="Product filenames to be compared.")
    parser.add_argument('--metadata-exclude-list', '-x',
                        nargs='+',
                        help=("Metadata field names to ignore for purposes "
                              "of determining comparison success or failure."))
    args = parser.parse_args()
    file_1 = args.files[0]
    file_2 = args.files[1]

    metadata_exclude_list = DEFAULT_METADATA_EXCLUDE_LIST

    if args.metadata_exclude_list:
        metadata_exclude_list.extend(args.metadata_exclude_list)

    result = compare_dswx_hls_products(file_1, file_2, metadata_exclude_list)

    if result is True:
        print("Comparison succeeded")
    else:
        print("Comparison failed")
