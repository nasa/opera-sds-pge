#!/usr/bin/env python3
"""Compare DIST products"""
import argparse

from dist_s1.data_models.output_models import ProductDirectoryData


def _get_parser():
    parser = argparse.ArgumentParser(
        description="Compare two DIST-S1 products",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        'expected_product',
        type=str,
        help='DIST-S1 expected output product'
    )

    parser.add_argument(
        'test_product',
        type=str,
        help='DIST-S1 test output product to compare to expected'
    )

    return parser


def main():
    """Compare two DIST-S1 products provided on command line"""

    parser = _get_parser()

    args = parser.parse_args()

    expected_product = ProductDirectoryData.from_product_path(args.expected_product)
    test_product = ProductDirectoryData.from_product_path(args.test_product)

    if expected_product == test_product:
        print('[OK] Products are equal')
    else:
        print('[FAIL] Products are not equal')


if __name__ == '__main__':
    main()
