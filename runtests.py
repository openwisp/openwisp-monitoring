#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

sys.path.insert(0, "tests")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "openwisp2.settings")

if __name__ == "__main__":
    from django.core.management import execute_from_command_line

    args = sys.argv
    args.insert(1, "test")
    if not os.environ.get("SAMPLE_APP", False):
        args.insert(2, "openwisp_monitoring")
    else:
        args.insert(2, "openwisp2")
    if os.environ.get("TIMESERIES_UDP", False):
        args.extend(["--exclude-tag", "timeseries_client"])
        # these tests read back data right after writing it (for example the
        # automatic threshold check that runs inside Metric.write), which is not
        # reliably queryable under asynchronous UDP writes; they are fully
        # covered by the TCP test runs
        args.extend(["--exclude-tag", "flaky_with_udp_writes"])
    execute_from_command_line(args)
