#!/usr/bin/env python3
"""Compare DIST products"""
import argparse
import os

import numpy as np


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

    print(f'Placeholder comparison between {args.expected_product} and {args.test_product}')

    print('[FAIL] Simulating comp failure')


if __name__ == '__main__':
    main()
