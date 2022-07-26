#!/usr/bin/env python3

import csv
import datetime
import os
import sys


"""
======================
process_metric_data.py
======================

Post process the csv file returned when metric data is collected

"""

prior_log_line = None


def remove_unwanted_lines(csv_file, file_name):
    """
    Remove all lines without data from docker stats
    Write results to a new file and delete the old file (cvs_file)

    Parameters
    ----------
    csv_file : cvs_file
       csv file containing docker stats or miscellaneous data

    file_name : csv_file
       filtered temporary csv_file with empty data removed.

    """
    new_data = []

    # Remove unwanted lines in raw .csv file and store in local 'new_data' list
    with open(csv_file) as file_obj:
        reader_obj = csv.reader(file_obj, delimiter=",")
        for row in reader_obj:
            if len(row) >> 2:
                new_data.append(row)

    # Write 'new_data' to temp file
    with open(file_name, mode='w') as opera_stats:
        stats_writer = csv.writer(opera_stats, delimiter=',')
        for row in new_data:
            stats_writer.writerow(list(row))


def get_mem_gb(mem_str):
    """
    Convert Docker stats memory values into number of GB rounded to 2 decimals.

        36.18MiB / 30.81GiB returns 0.03
        3.033GiB / 30.81GiB returns 3.03

    Parameters
    ----------
    mem_str : string
        Value found from docker stats

    Returns
    -------
    mem_val : float
        Numeric value of the number of gigabytes

    """
    mem_val = mem_str.split(' ')[0]
    if "KiB" in mem_val:
        mem_val = mem_val.replace("KiB", "")
        mem_val = float(mem_val)/1000000
    elif "MiB" in mem_val:
        mem_val = mem_val.replace("MiB", "")
        mem_val = float(mem_val)/1000
    elif "GiB" in mem_val:
        mem_val = float(mem_val.replace("GiB", ""))
    elif mem_val.startswith("0B"):
        mem_val = float(0)
    else:
        raise ValueError(f"Unexpected units value for memory: {mem_val}")
    return round(mem_val, 2)


def get_disk_gb(d_str):
    """Convert 1K block values into GB."""
    return float(d_str.split()[2])*1024/1000000000


def conv_to_gb(meas_str):
    """Convert various measurements to gigabytes"""
    if "kB" in meas_str:
        numeric_val = float(meas_str.split("kB")[0]) / 1000000
    elif "MB" in meas_str:
        numeric_val = float(meas_str.split("MB")[0]) / 1000
    elif "GB" in meas_str:
        numeric_val = float(meas_str.split("GB")[0])
    elif "TB" in meas_str:
        numeric_val = float(meas_str.split("TB")[0]) * 1000
    elif "B" in meas_str:
        numeric_val = float(meas_str.split("B")[0]) / 1000000000
    else:
        print(f"unexpected string value {meas-str}")
        numeric_val = meas_str
    return numeric_val


def get_net_send_recv(net_str):
    """Split into blocks sent and received."""
    s, r = net_str.split(' / ')
    s = conv_to_gb(s)
    r = conv_to_gb(r)
    return s, r


def get_disk_read_write(block_str):
    """Split into blocks read and written."""
    r, w = block_str.split(' / ')
    r = conv_to_gb(r)
    w = conv_to_gb(w)
    return r, w


def format_out_row_misc(misc_row):
    """
       Return a formatted, comma separated row of docker miscellaneous data.

       Parameters
       ----------
       misc_row : dictionary
           row from the data collection of miscellaneous stats

       Returns
       -------
       formatted, comma separated string

       """

    secs = misc_row['SECONDS']
    disk = get_disk_gb(misc_row['disk_used'])
    # swap = dr['swap_used'].split()[2]
    threads = misc_row['total_threads']
    # Todo fix this code so we get the last line stuff: right now it's blank
    # only update last line if it has changed
    global prior_log_line
    if prior_log_line is not None and misc_row['last_line'] == prior_log_line:
        last_line = ""
    else:
        last_line = misc_row['last_line']
        prior_log_line = last_line
    return f"{secs},{disk},{threads},{last_line}"


def format_out_row_docker(stats_row):
    """
    Return a formatted, comma separated row of docker stats data.

    Parameters
    ----------
    stats_row : dictionary
        row from data collection of docker stats

    Returns : string
    -------
        formatted, comma separated string

    """

    secs = stats_row['SECONDS']
    name = stats_row['{{.Name}}']
    pids = stats_row['{{.PIDs}}']
    cpu = stats_row['{{.CPUPerc}}'].replace("%", "")
    mem = get_mem_gb(stats_row['{{.MemUsage}}'])
    mem_p = stats_row['{{.MemPerc}}'].replace("%", "")
    net_s, net_r = get_net_send_recv(stats_row['{{.NetIO}}'])
    disk_r, disk_w = get_disk_read_write(stats_row['{{.BlockIO}}'])
    return f"{secs},{name},{pids},{cpu},{mem},{mem_p},{net_s},{net_r},{disk_r},{disk_w}"


def make_lists(csv_file):
    """
    Makes a list of dictionaries for each row of the csv file captured during the docker run

    Parameters
    ----------
    csv_file : file
        file used to capture either docker stats or miscellaneous OS measurements

    Returns
    -------
    csv_to_list : list
        List that is now ready to be formatted

    """
    csv_to_list = []
    with open(csv_file) as csv_handle:
        reader = csv.DictReader(csv_handle)
        for row in reader:
            csv_to_list.append(row)
    return csv_to_list


def main():
    """ main program in process_metric_data.py"""

    container_info = sys.argv[1]
    stats_file = sys.argv[2]
    misc_file = sys.argv[3]

    temp_stats = "temp_opera_docker_stats.csv"
    temp_misc = "temp_opera_misc_stats.csv"

    # Remove lines that may have been recorded before Docker stated.
    remove_unwanted_lines(stats_file, temp_stats)
    remove_unwanted_lines(misc_file, temp_misc)

    current_time = datetime.datetime.today().strftime('%Y%m%d_%H%M%S')

    # For now make two formatted files
    docker_report_file = f"docker_metrics_{container_info}_{current_time}.csv"
    misc_report_file = f"misc_metrics_{container_info}_{current_time}.csv"

    # read files into lists
    stats_list = make_lists(temp_stats)
    misc_list = make_lists(temp_misc)

    # Write out the docker stats file
    docker_columns = "SECONDS, Name, PIDs, CPU, Memory, MemoryP, NetSend, NetRecv, DiskRead, DiskWrite"
    # Todo - used to convert non-string data to numbers
    # convert = {'SECONDS': int(), 'Name': str(), 'PIDs': int(), 'CPU': float(), 'Memory': float(), 'MemoryP': float(),
    #            'NetSend': float(), 'NetRecv': float(), 'DiskRead': float(), 'DiskWrite': float()}
    with open(docker_report_file, 'w') as out_file:
        out_file.write(f"{docker_columns}\n")
        for stats_row in stats_list:
            row = format_out_row_docker(stats_row)
            out_file.write(f"{row}\n")

    # Write out the miscellaneous file
    # Todo - divide out mac OS runs and linux runs - Swap will work on linux
    # misc_columns = "SECONDS, Disk, Swap, Threads, LastLogLine"
    misc_columns = "SECONDS, Disk, Threads, LastLogLine"
    with open(misc_report_file, 'w') as out_file:
        out_file.write(f"{misc_columns}\n")
        for stats_row in misc_list:
            row = format_out_row_misc(stats_row)
            out_file.write(f"{row}\n")

    # Remove temporary files
    os.remove(temp_stats)
    os.remove(temp_misc)


if __name__ == "__main__":
    main()
