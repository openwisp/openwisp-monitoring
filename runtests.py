#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

sys.path.insert(0, 'tests')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'openwisp2.settings')

if __name__ == '__main__':
    from django.core.management import execute_from_command_line
    from django.conf import settings

    args = sys.argv
    args.insert(1, 'test')
    if not os.environ.get('SAMPLE_APP', False):
        setattr(settings, 'TEST_RUNNER' ,'openwisp_monitoring.measure_speed.TimeLoggingTestRunner')
        args.insert(2, 'openwisp_monitoring')
    else:
        args.insert(2, 'openwisp2')
        # Add this to sample tests
        args.insert(3, 'openwisp_monitoring.monitoring.tests.test_notifications')
    execute_from_command_line(args)
