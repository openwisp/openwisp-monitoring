import os
from unittest import skipIf

from django.test import TestCase

from ..base.tests.test_db_creation import BaseTestDatabase


@skipIf(os.environ.get('SAMPLE_APP', False), 'Running tests on SAMPLE_APP')
class TestDatabase(BaseTestDatabase, TestCase):
    app_name = 'monitoring'
