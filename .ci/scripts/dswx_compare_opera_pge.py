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
    else:
        # compare each band
        print('Comparing DSWx bands...')
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
                '''
                # Find the min and max differences using the numpy.isclose function
                # 0 <= (atol + rtol * absolute(b)) - absolute(a-b)
                a1 = image_1[~is_close_result]
                b2 = image_2[~is_close_result]
                atol = COMPARE_DSWX_HLS_PRODUCTS_ERROR_TOLERANCE_ATOL
                rtol = COMPARE_DSWX_HLS_PRODUCTS_ERROR_TOLERANCE_RTOL
                is_close_differences = abs((atol + rtol * abs(b2)) - abs(a1 - b2))
                '''
                is_close_differences = abs( image_1[~is_close_result] - image_2[~is_close_result])
                max_difference_band = np.max(is_close_differences)
                min_difference_band = np.min(is_close_differences)

                print(prefix + f"     * image band {b} difference count is {num_image_differences} "
                      f"with maximum difference of {max_difference_band} and minimum difference of "
                      f"{min_difference_band}.")
                differing_indices = np.where(~is_close_result)
                i, j = differing_indices[0][0], differing_indices[1][0]
                print(prefix + f'     * image band {b}, input 1 has value'
                                  f' "{image_1[i, j]}" in position'
                                  f' (i: {i}, j: {j})'
                                  f' whereas input 2 has value "{image_2[i, j]}"'
                                  ' in the same position.')
            else:
                flag_bands_are_equal = True

            flag_bands_are_equal_str = _get_prefix_str(flag_bands_are_equal,
                                                       flag_all_ok)
            print(f'{flag_bands_are_equal_str}     Band {b} -'
              f' {gdal_band_1.GetDescription()}"')

    # compare geotransforms
    flag_same_geotransforms = np.allclose(geotransform_1, geotransform_2,
                                     atol=COMPARE_DSWX_HLS_PRODUCTS_ERROR_TOLERANCE_ATOL,
                                     rtol=COMPARE_DSWX_HLS_PRODUCTS_ERROR_TOLERANCE_RTOL)
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
    flag_same_metadata = True
    metadata_error_message = ""
    for k2, v2, in metadata_2.items():
        if k2 not in metadata_1.keys():
            flag_same_metadata = False
            metadata_error_message += (
                f'* the metadata key {k2} is present in input 2'
                ' but it is not present in input 1\n')
    for k1, v1, in metadata_1.items():
        if k1 not in metadata_2.keys():
            flag_same_metadata = False
            metadata_error_message += (
                f'* the metadata key {k1} is present in input 1'
                ' but it is not present in input 2\n')
        else:
            # Currently these are string values otherwise the comparison below would need to change for floating point.
            if metadata_2[k1] != v1:
                msg = (f'* contents of metadata key {k1} from'
                       f' input 1 has value "{v1}" whereas the same key in'
                       f' input 2 metadata has value "{metadata_2[k1]}"')
                # Don't fail for metadata fields that are not required to be the same
                if k1 in ['PROCESSING_DATETIME', 'DEM_SOURCE', 'LANDCOVER_SOURCE',
                          'WORLDCOVER_SOURCE', 'TIFFTAG_YRESOLUTION']:
                    # We will just print the difference in the output
                    print(msg)
                else:
                    flag_same_metadata = False
                    metadata_error_message += msg + '\n'

    return metadata_error_message, flag_same_metadata


if __name__ == "__main__":

    file_1 = sys.argv[1]
    file_2 = sys.argv[2]
   
    result = compare_dswx_hls_products(file_1, file_2) 

    if result is True:
        print("Comparison succeeded")
    else:
        print("Comparison failed")
