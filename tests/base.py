"""
Shared test infrastructure.

Every test gets its own throwaway SQLite file so tests never share state
or leak into each other or into a real deployment's database. This is
intentionally NOT pytest fixtures - the test suite uses the standard
library's unittest so it can run with zero extra dependencies beyond
what's already in requirements.txt (`python -m unittest discover`).
pytest, if installed, can also collect and run these directly.
"""
import os
import shutil
import tempfile
import unittest

import config
import database


class SmartBethGTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.mkdtemp(prefix="smart_bethg_test_")
        self._original_db_path = database.DB_PATH
        database.DB_PATH = os.path.join(self._tmp_dir, "test.db")
        database.initialize_database()

    def tearDown(self):
        database.DB_PATH = self._original_db_path
        shutil.rmtree(self._tmp_dir, ignore_errors=True)
