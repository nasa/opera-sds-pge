#!/usr/bin/env python3

import csv
import os
import pathlib
import sys


"""
======================
process_metric_data.py
======================

Post process the csv file returned when metric data is collected

"""


def remove_unwanted_lines(csv_file):
    """
    Remove all lines without data from docker stats
    Write results to a new file and delete the old file (cvs_file)

    Parameters
    ----------
    csv_file : cvs_file
       csv file containing docker stats data

    """
    new_data = []

    # Remove unwanted lines in raw .csv file and store in local 'new_data' list
    with open(csv_file) as file_obj:
        reader_obj = csv.reader(file_obj, delimiter=",")
        for row in reader_obj:
            if len(row) >> 2:
                new_data.append(row)

    # Write 'new_data' to 'opera_pge_statistics.csv'
    with open('opera_pge_statistics.csv', mode='w') as opera_stats:
        stats_writer = csv.writer(opera_stats, delimiter=',')
        for row in new_data:
            stats_writer.writerow(list(row))


def delete_temp_files(file_name):
    try:
        os.remove(file_name)
        print(f'Removing: {file_name} from {pathlib.Path().absolute()}')
    except OSError:
        print(f'OSError, could not remove {file_name}')


def main(csv_file):
    """ main program in process_metric_data.py"""
    remove_unwanted_lines(csv_file)
    delete_temp_files(csv_file)


if __name__ == "__main__":
    csv_file_raw = sys.argv[1]
    main(csv_file_raw)
