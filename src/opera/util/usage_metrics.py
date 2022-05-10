#!/usr/bin/env python3
#

"""
================
usage_metrics.py
================

OS-level metrics gathering functions for use with OPERA PGEs.

This module is adapted for OPERA from the NISAR PGE R2.0.0 util/usage_metrics.py
Original Author: David White
Adapted By: Scott Collins

"""

import os
import resource
from sys import platform


def get_os_metrics():
    """
    Gets metrics related to machine resource usage, both by the current process
    as well as all of its children processes.

    Returns
    -------
    metrics : dict
        Dictionary containing metrics mapped to the following keys
            os.cpu.seconds.sys -
                System CPU time, in seconds, consumed by the current process and
                its children
            os.cpu.seconds.user -
                User CPU time, in seconds, consumed by the current process and
                its children
            os.filesystem.reads -
                Number of file system reads performed by the current process and
                its children
            os.filesystem.writes -
                Number of file system writes performed by the current process
                and its children
            os.max_rss_kb.main_process -
                Maximum resident set size (physical memory consumption), in
                kilobytes, of the current process
            os.max_rss_kb.largest_child_process -
                Maximum resident set size (physical memory consumption), in
                kilobytes, of the largest child process
            os.peak_vm_kb.main_process -
                Peak virtual memory usage, in kilobytes, of the current process.

    """
    rusage_self = resource.getrusage(resource.RUSAGE_SELF)
    rusage_children = resource.getrusage(resource.RUSAGE_CHILDREN)

    metrics = {
        # these metrics include the current process and "all children
        # of the calling process that have terminated and been waited for";
        # see the Linux man page for getrusage()
        'os.cpu.seconds.sys': rusage_self.ru_stime + rusage_children.ru_stime,
        'os.cpu.seconds.user': rusage_self.ru_utime + rusage_children.ru_utime,
        'os.filesystem.reads': rusage_self.ru_inblock + rusage_children.ru_inblock,
        'os.filesystem.writes': rusage_self.ru_oublock + rusage_children.ru_oublock,
        # unfortunately the max_rss does not account for all child processes;
        # see the Linux man page for getrusage()
        'os.max_rss_kb.main_process': rusage_self.ru_maxrss,
        'os.max_rss_kb.largest_child_process': rusage_children.ru_maxrss,
        'os.peak_vm_kb.main_process': get_self_peak_vmm_kb()
    }

    return metrics


def get_self_peak_vmm_kb():  # pylint: disable=missing-raises-doc
    """
    Attempt to get the peak virtual memory by looking into the /proc/self/status

    Note that this accounts for the peak virtual memory of just the current
    process, not the sum of the current process and all its children.

    Returns
    -------
    vm_peak_kb : int
        Peak virtual memory usage, in kilobytes, of the current process. If
        this value cannot be obtained for any reason, -1 is returned instead.

    """
    vm_peak_kb = 0

    status_file = os.path.join(os.sep, 'proc', 'self', 'status')

    try:
        if platform != "linux" or not os.path.exists(status_file):  # pragma no cover
            raise EnvironmentError

        with open(status_file, "r", encoding='utf-8') as infile:  # pragma no cover
            for line in infile.readlines():
                if line.startswith("VmPeak:"):
                    vm_peak_str = line.replace("VmPeak:", "").replace("kB", "")
                    vm_peak_kb = int(vm_peak_str)
                    break

    except EnvironmentError:
        vm_peak_kb = -1

    return vm_peak_kb
