"""Compatibility checks for the Python versions supported by the project."""

import importlib
import unittest


class PythonCompatibilityTests(unittest.TestCase):
    def test_undetected_chromedriver_importable(self):
        """The Selenium backend must import on Python versions without distutils."""
        importlib.import_module("undetected_chromedriver")


if __name__ == "__main__":
    unittest.main()
