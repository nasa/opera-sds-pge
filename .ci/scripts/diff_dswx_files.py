#   diff_dswx_files.py
#
#   For: OPERA project
#
#   11-03-2023 - Ray Bambery
#       initial release
#
#   Description: Python program to perform Quality Assurance Test
#       on a directory of NETcdf4 files - searches for files with
#       a .tif file extension.
#       This script calls a subprocess script,  dswx_comparison.py
#       located in the dswx_s1_x.y.z directory shown as <DSWX-S1_DIR>
#       in the wiki page 
#       https://github.com/nasa/opera-sds-pge/wiki/DWSX_S1_Beta-Acceptance-Test-Instruuctions
#       which ensures there are matching files in each input directory
##
#   Arguments:
#       expected_output_dir output_dir dir
#
#   Outputs: A terminal stream of  results of the tests showing 
#       PASS (in GREEN) or FAIL (in RED)
#   
#   Calls:  
#       dswx_comparison.py
#
import os
import sys
import subprocess
import argparse
import glob
#import netCDF4 as nc

##################################################################
def _parse_args():
    parser = argparse.ArgumentParser(
        description='2 directories for comparison of files'
    )
    parser.add_argument('input dirs',
        type=str,
        nargs=2,
        help='Input dir1 Input_dir2')

    print ("len(sys.argv) = ",len(sys.argv))
    if len(sys.argv) == 1:
        parser.print_help()
#        print ("options are ",options)
        sys.exit(0)
    else:
        if len(sys.argv) == 2:
            print ("Missing second input directory")
            sys.exit(-1)
        else:
            print ("sys.argv[1] = ",sys.argv[1])
            print ("sys.argv[2] = ",sys.argv[2])
#           options = parser.parse_args()
#           print ("options are ", options)

    return sys.argv
#################################################################
def get_files(options):


#     print ("options1 = ",options[1])
#     print ("options2 = ",options[2])

    expected_dir = options[1]
    output_dir = options[2]

    # list to store files
    exp = [os.path.basename(f) for f in sorted(glob.glob(os.path.join(expected_dir, '*.tif')))]
#    print (exp)
    expected_file_count = len(exp)
    print("expected_file_count = ",len(exp))

    ecnt = 0
    for x in exp:
#        print ("expected = ",x)
        exp[ecnt] = x
#         print ("ecnt = ",ecnt," exp[ecnt] = ",expected_dir + exp[ecnt])
        ecnt += 1


    # list to store files
    out = [os.path.basename(f) for f in sorted(glob.glob(os.path.join(output_dir, '*.tif')))]
#    print (out)
    output_file_count = len(out)
    print("output_file_count = ",len(out))


#    for x in out:
#        print ("out = ",x)

    ocnt = 0
    for x in out:
#        print ("out = ",x)
        out[ocnt] = x
#        print ("ocnt = ",ocnt," out[ocnt] = ",output_dir + out[ocnt])
        ocnt += 1
        #print ("cnt = ",cnt," out[cnt] = ",out[cnt])


    if expected_file_count == 0:
        print ("[FAIL]  expected file_count == 0")
        print ("    Expected file count of 0 usually implies a typo in directory name")
        sys.exit(-1)
    if output_file_count == 0:
        print ("[FAIL]  output file_count == 0")
        print ("    Output file count of 0 usually implies a typo in directory name")
        sys.exit(-1)

    if output_file_count > expected_file_count:
        print ("[FAIL]  output_file_count ",output_file_count," exceeds expected_file_count ",expected_file_count)
        sys.exit(-1)
    if expected_file_count > output_file_count:
        print ("[FAIL]  expected_file_count ",expected_file_count," exceeds output_file_count ",output_file_count)
        sys.exit(-1)

#$ could be ocnt
    for i in range(0, ecnt):
#        print (i)
        print ("python3 dswx_comparison.py  {}  {}".format(expected_dir + '/' + exp[i],output_dir + '/' + out[i]))
        os.system("python3 dswx_comparison.py  {}  {}".format(expected_dir + '/' + exp[i],output_dir + '/' + out[i]))



#    print ("stop")
#################################################################
def main():

    options = _parse_args()

    get_files(options)

#################################################################
if __name__ == '__main__':

    main()


