#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

sys.path.insert(0, "tests")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "openwisp2.settings")

if __name__ == "__main__":
    from django.core.management import execute_from_command_line
    from django.core.management.commands.test import Command

    base_args = sys.argv[1:]
    # The Django test command parser imports settings to discover runner
    # arguments. Prime argv first so settings that detect test mode from argv
    # are initialized consistently.
    sys.argv = [sys.argv[0], "test", *base_args]
    args = [sys.argv[0], "test"]
    parser = Command().create_parser(sys.argv[0], "test")
    parsed_args, _ = parser.parse_known_args(base_args)
    has_test_labels = bool(getattr(parsed_args, "args", []))
    default_target = (
        "openwisp2" if os.environ.get("SAMPLE_APP", False) else "openwisp_monitoring"
    )
    if not has_test_labels:
        args.append(default_target)
    args.extend(base_args)
    if os.environ.get("TIMESERIES_UDP", False):
        args.extend(["--exclude-tag", "timeseries_client"])
        # These tests read immediately after writing, sometimes inside product
        # code such as Metric.write(). That is unreliable with UDP writes, and
        # the same behavior is already covered by the TCP test runs.
        args.extend(["--exclude-tag", "flaky_with_udp_writes"])
    # Keep sys.argv aligned with the final Django command so settings that
    # inspect argv during import can detect test mode correctly.
    sys.argv = args[:]
    execute_from_command_line(args)
