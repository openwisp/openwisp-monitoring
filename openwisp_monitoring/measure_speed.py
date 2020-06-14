from time import time
from unittest import TextTestResult

from django.test.runner import DiscoverRunner


class TimeLoggingTestResult(TextTestResult):
    def __init__(self, *args, **kwargs):
        self.slow_test_threshold = 0.3
        self.test_timings = []
        super().__init__(*args, **kwargs)

    def startTest(self, test):
        self._start_time = time()
        super().startTest(test)

    def addSuccess(self, test):
        elapsed = time() - self._start_time
        name = self.getDescription(test)
        self.test_timings.append((name, elapsed))
        super().addSuccess(test)

    def display_slow_tests(self):
        print(
            '\n\033[12;0;1mThese are your \033[33;1;1mculprit\033[12;0;1m '
            f'slow tests (>{self.slow_test_threshold}s) \033[0m\n'
        )
        self._module = None
        slow_tests_counter = 0
        for name, elapsed in self.test_timings:
            if elapsed > self.slow_test_threshold:
                slow_tests_counter += 1
                name, module = name.split()
                if module != self._module:
                    self._module = module
                    print(f'\033[92m{module}\033[0m')
                color = (
                    '\033[91m' if elapsed > self.slow_test_threshold * 2 else '\033[93m'
                )
                print(f'  ({color}{elapsed:.2f}s\033[0m) {name}\033[0m')
        print(f'\n\033[12;0;1mTotal slow tests detected: {slow_tests_counter}\033[0m')
        return self.test_timings

    def stopTestRun(self):
        self.display_slow_tests()
        super().stopTestRun()


class TimeLoggingTestRunner(DiscoverRunner):
    def get_resultclass(self):
        return TimeLoggingTestResult
