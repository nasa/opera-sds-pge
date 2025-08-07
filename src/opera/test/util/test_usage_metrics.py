#!/usr/bin/env python

"""
=====================
test_usage_metrics.py
=====================

Unit tests for the util/usage_metrics.py module.
"""
import os
import re
import tempfile
import unittest
from os.path import abspath, join
from sys import platform

from opera.test import path

from opera.util.usage_metrics import get_os_metrics


class UsageMetricsTestCase(unittest.TestCase):
    """Base test class using unittest"""

    test_dir = None

    @classmethod
    def setUpClass(cls) -> None:
        """
        Set up class variables:
        Initialize the number of times to exercise the module (currently 1000)

        """
        cls.starting_dir = abspath(os.curdir)
        with path('opera.test', 'util') as test_dir_path:
            cls.test_dir = str(test_dir_path)
        cls.data_dir = join(cls.test_dir, os.pardir, "data")

        os.chdir(cls.test_dir)

        cls.config_file = join(cls.data_dir, "test_base_pge_config.yaml")
        cls.reps = 10000

    @classmethod
    def tearDownClass(cls) -> None:
        """
        At completion re-establish starting directory
        -------
        """
        os.chdir(cls.starting_dir)

    def setUp(self) -> None:
        """
        Use the temporary directory as the working directory
        -------
        """
        self.working_dir = tempfile.TemporaryDirectory(
            prefix="test_usage_metrics_", suffix='temp', dir=os.curdir
        )
        os.chdir(self.working_dir.name)

    def tearDown(self) -> None:
        """
        Return to starting directory
        -------
        """
        os.chdir(self.test_dir)
        self.working_dir.cleanup()

    def test_get_os_metrics(self):
        """
        Test the metrics returned from usage_metrics.py
        The module uses 2 calls to get the Parent and Child process results from resource.getrusage()
            > resource.getrusage(resource.RUSAGE_SELF)
            > resource.getrusage(resource.RUSAGE_CHILDREN)
        Statistics of interest:
            ru_stime - the total amount of time executing in kernel mode. (sec.ms)
            ru_utime - the total amount of time executing in user mode. (sec.ms)
            ru_inblock - the number of times the filesystem had to perform input.  (int)
            ru_outblock - the number of times the filesystem had to perform output. (int)
            ru_maxrss - is the maximum resident set size used. For RUSAGE_CHILDREN, this is
                        the 'high-water mark', that indicates the PEAk RAM use of this process.
                        NOTE: on Mac OS X the value returned is in 'BYTES', on Linux and BSD machines
                              the results are in 'KILOBYTES'.

            os.peak_vm_kb.main_process comes from a call to get_self_peak_vmm_kb().
        """
        cpu_regex = r'^\d*\.\d+$'  # match positive real numbers
        int_regex = r'^[0-9]*$'  # match positive integers
        # Get the results

        for index in range(self.reps):
            metrics = get_os_metrics()
            # Verify the format of the values and verify they are all positive
            self.assertEqual(str(metrics['os.cpu.seconds.sys']), re.match(cpu_regex,
                             str(metrics['os.cpu.seconds.sys'])).group())
            self.assertEqual(str(metrics['os.cpu.seconds.user']), re.match(cpu_regex,
                             str(metrics['os.cpu.seconds.user'])).group())
            self.assertEqual(str(metrics['os.filesystem.reads']), re.match(int_regex,
                             str(metrics['os.filesystem.reads'])).group())
            self.assertEqual(str(metrics['os.filesystem.writes']), re.match(int_regex,
                             str(metrics['os.filesystem.writes'])).group())
            self.assertEqual(str(metrics['os.max_rss_kb.largest_child_process']), re.match(int_regex,
                             str(metrics['os.max_rss_kb.largest_child_process'])).group())

            # Testing peak_vmm_kb requires the test to run in a Linux environment,
            # otherwise we expect -1 back, so test both
            if platform != "linux":
                self.assertEqual(metrics['os.peak_vm_kb.main_process'], -1)
            else:
                self.assertEqual(str(metrics['os.peak_vm_kb.main_process']), re.match(int_regex,
                                 str(metrics['os.peak_vm_kb.main_process'])).group())


if __name__ == "__main__":
    unittest.main()
