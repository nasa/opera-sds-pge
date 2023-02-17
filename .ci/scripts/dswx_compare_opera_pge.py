from osgeo import gdal
import numpy as np
import os
import sys

COMPARE_DSWX_HLS_PRODUCTS_ERROR_TOLERANCE_ATOL = 1e-6
COMPARE_DSWX_HLS_PRODUCTS_ERROR_TOLERANCE_RTOL = 1e-5

def _get_prefix_str(flag_same, flag_all_ok):
    flag_all_ok[0] = flag_all_ok[0] and flag_same
    return '[OK]   ' if flag_same else '[FAIL] '


def compare_dswx_hls_products(file_1, file_2):
    if not os.path.isfile(file_1):
        print(f'ERROR file not found: {file_1}')
        return False

    if not os.path.isfile(file_2):
        print(f'ERROR file not found: {file_2}')
        return False

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
    total_image_differences = 0
    min_difference = 0
    max_difference = 0
    for b in range(1, nbands_1 + 1):
        gdal_band_1 = layer_gdal_dataset_1.GetRasterBand(b)
        gdal_band_2 = layer_gdal_dataset_2.GetRasterBand(b)
        image_1 = gdal_band_1.ReadAsArray()
        image_2 = gdal_band_2.ReadAsArray()
        is_close_result = np.isclose(image_1, image_2,
                                     atol=COMPARE_DSWX_HLS_PRODUCTS_ERROR_TOLERANCE_ATOL,
                                     rtol=COMPARE_DSWX_HLS_PRODUCTS_ERROR_TOLERANCE_RTOL)
        num_image_differences = np.sum(~is_close_result)
        if num_image_differences > 0:
            flag_bands_are_equal = False
            # Find the min and max differences using the numpy.isclose function
            # 0 <= (atol + rtol * absolute(b)) - absolute(a-b)
            a1 = image_1[~is_close_result]
            b2 = image_2[~is_close_result]
            atol = COMPARE_DSWX_HLS_PRODUCTS_ERROR_TOLERANCE_ATOL
            rtol = COMPARE_DSWX_HLS_PRODUCTS_ERROR_TOLERANCE_RTOL
            is_close_differences = abs((atol + rtol * abs(b2)) - abs(a1 - b2))
            max_difference_band = np.max(is_close_differences)
            if max_difference_band > max_difference:
                max_difference = max_difference_band
            min_difference_band = np.min(is_close_differences)
            if min_difference_band < min_difference:
                min_difference = min_difference_band
        else:
            flag_bands_are_equal = True

        total_image_differences += num_image_differences

        flag_bands_are_equal_str = _get_prefix_str(flag_bands_are_equal,
                                                   flag_all_ok)
        print(f'{flag_bands_are_equal_str}     Band {b} -'
              f' {gdal_band_1.GetDescription()}"')
        if not flag_bands_are_equal:
            _print_first_value_diff(image_1, image_2, prefix)

    if total_image_differences > 0:
        _print_image_differences(total_image_differences, min_difference, max_difference, prefix)

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
        _compare_dswx_hls_metadata(metadata_1, metadata_2)

    flag_same_metadata_str = _get_prefix_str(flag_same_metadata,
                                             flag_all_ok)
    print(f'{flag_same_metadata_str}Comparing metadata')

    if not flag_same_metadata:
        print(prefix + metadata_error_message)

    return flag_all_ok[0]


def _compare_dswx_hls_metadata(metadata_1, metadata_2):
    """
    Compare DSWx-HLS products' metadata
       Parameters
       ----------
       metadata_1 : dict
            Metadata of the first DSWx-HLS product
       metadata_2: dict
            Metadata of the second
    """
    metadata_error_message = None
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
            if k1 in ['PROCESSING_DATETIME', 'DEM_SOURCE', 'LANDCOVER_SOURCE',
                      'WORLDCOVER_SOURCE']:
                continue
            if metadata_2[k1] != v1:
                flag_same_metadata = False
                metadata_error_message = (
                    f'* contents of metadata key {k1} from'
                    f' input 1 has value "{v1}" whereas the same key in'
                    f' input 2 metadata has value "{metadata_2[k1]}"')
                break
    return metadata_error_message, flag_same_metadata


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
            # absolute(a-b) <= (atol + rtol * absolute(b))
            if (abs(image_1[i, j] - image_2[i, j]) <=
                    (COMPARE_DSWX_HLS_PRODUCTS_ERROR_TOLERANCE_ATOL + COMPARE_DSWX_HLS_PRODUCTS_ERROR_TOLERANCE_RTOL * abs(image_2[i, j]))):
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

def _print_image_differences(total_image_differences, min_difference, max_difference, prefix):
    """
    Print the number of image differences and the min/max differences.
        Parameters
        ----------
        total_image_differences : int
            Number of image elements that fail to meet numpy.isclose criteria.
        min_difference : float
            Minimum numpy.isclose difference between reference and test images.
        max_difference : float
            Maximum numpy.isclose difference between reference and test images.
        prefix : str
            Prefix t othe message printed to the user.
    """
    print(prefix + f"     * total image differences is {total_image_differences} "
          f"with maximum difference of {max_difference} and minimum difference of "
          f"{min_difference}.")


if __name__ == "__main__":

    file_1 = sys.argv[1]
    file_2 = sys.argv[2]
   
    result = compare_dswx_hls_products(file_1, file_2) 

    if result is True:
        print("Comparison succeeded")
    else:
        print("Comparison failed")