#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

sys.path.insert(0, "tests")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "openwisp2.settings")

if __name__ == "__main__":
    from django.core.management import execute_from_command_line

    base_args = sys.argv[1:]
    args = [sys.argv[0], "test"]
    has_test_labels = any(not arg.startswith("-") for arg in base_args)
    if not has_test_labels:
        if not os.environ.get("SAMPLE_APP", False):
            args.append("openwisp_monitoring")
        else:
            args.append("openwisp2")
    args.extend(base_args)
    if os.environ.get("TIMESERIES_UDP", False):
        args.extend(["--exclude-tag", "timeseries_client"])
    execute_from_command_line(args)
