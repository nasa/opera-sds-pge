#!/usr/bin/env python3
"""
==================
diff_dswx_files.py
==================

Python program to perform Quality Assurance Test on a directory of NetCDF4 files.
This script searches for files with a .tif file extension and calls a subprocess
script, dswx_comparison.py, located in the dswx_s1_x.y.z directory shown as <DSWX-S1_DIR>
in the wiki page  https://github.com/nasa/opera-sds-pge/wiki/DWSX_S1_Beta-Acceptance-Test-Instruuctions
which ensures there are matching files in each input directory.

"""

import argparse
import glob
import os
import sys


def _parse_args():
    """
    This function gets the two directory names that are arguments to the module.
    If no arguments are given, it prints a help message and exits,
    if only one argument is given, it gives a warning message and aborts.

    Returns
    --------
    result : <-1 if FAIL>
             <0 if HELP>
             <list - string if PASS>
        Returns a list of 2 directory names to the calling function.

    """
    parser = argparse.ArgumentParser(
        description='Compares sets DSWx-S1 products with the dswx_comparison.py script'
    )
    parser.add_argument('input dirs',
                        type=str,
                        nargs=2,
                        help='Expected_dir Output_dir')

    print("len(sys.argv) = ", len(sys.argv))
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)
    else:
        if len(sys.argv) == 2:
            print("Missing Output_dir")
            sys.exit(-1)
        else:
            print("sys.argv[1] = ", sys.argv[1])
            print("sys.argv[2] = ", sys.argv[2])

    return sys.argv


def get_files(options):
    """
    This function determines the number of files in each directory and, if equal,
    compares them file by file.

    Notes
    ------
    Calls external python script, dswx_comparison.py, to perform the file comparison.

    Parameters
    ------------
    options : <list - string>
       Directory names of expected_dir and output

    Returns
    --------
    result : <-1 if FAIL>
         FAILS if number of files in 2 directories are 0, or unequal.

    """
    expected_dir = options[1]
    output_dir = options[2]

    # list to store files
    exp = [os.path.basename(f) for f in sorted(glob.glob(os.path.join(expected_dir, '*.tif')))]
    expected_file_count = len(exp)
    print("expected_file_count = ", len(exp))

    expected_count = 0
    for x in exp:
        exp[expected_count] = x
        expected_count += 1

    # list to store files
    out = [os.path.basename(f) for f in sorted(glob.glob(os.path.join(output_dir, '*.tif')))]
    output_file_count = len(out)
    print("output_file_count = ", len(out))

    output_count = 0
    for x in out:
        out[output_count] = x
        output_count += 1

    if expected_file_count == 0:
        print("[FAIL]  expected file_count == 0")
        print("    Expected file count of 0 usually implies a typo in directory name")
        sys.exit(-1)
    if output_file_count == 0:
        print("[FAIL]  output file_count == 0")
        print("    Output file count of 0 usually implies a typo in directory name")
        sys.exit(-1)

    if output_file_count > expected_file_count:
        print("[FAIL]  output_file_count ", output_file_count, " exceeds expected_file_count ", expected_file_count)
        sys.exit(-1)
    if expected_file_count > output_file_count:
        print("[FAIL]  expected_file_count ", expected_file_count, " exceeds output_file_count ", output_file_count)
        sys.exit(-1)

    # could also be output_count
    for i in range(0, expected_count):
        expected_path = os.path.join(expected_dir, exp[i])
        output_path = os.path.join(output_dir, out[i])
        cmd1 = "python3"
        cmd2 = "dswx_comparison.py"
        command = cmd1 + ' ' + cmd2 + ' ' + expected_path + ' ' + output_path
        print(command)
        os.system(command)


def main():
    options = _parse_args()
    get_files(options)


if __name__ == '__main__':
    main()
