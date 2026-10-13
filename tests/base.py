"""
Shared PostgreSQL test infrastructure.

Each test receives a unique PostgreSQL schema so it cannot share application
tables or records with another test or a developer's database. Tests refuse to
fall back to SQLite and require an explicitly named test database URL.
"""
import os
import shutil
import tempfile
import unittest
import uuid

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

import config
import database


class SmartBethGTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.mkdtemp(prefix="smart_bethg_test_")
        self._original_database_url = config.DATABASE_URL
        self._base_database_url = os.getenv("SMART_BETHG_TEST_DATABASE_URL", "").strip()
        if not self._base_database_url:
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
            self.fail(
                "SMART_BETHG_TEST_DATABASE_URL must point to a disposable local "
                "PostgreSQL test database. Tests never use SQLite or production DATABASE_URL."
            )
        if not self._base_database_url.startswith(("postgres://", "postgresql://", "postgresql+psycopg://")):
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
            self.fail("SMART_BETHG_TEST_DATABASE_URL must be a PostgreSQL connection URL.")

        self._schema = "sb_test_" + uuid.uuid4().hex
        try:
            with psycopg.connect(self._base_database_url, autocommit=True) as admin:
                admin.execute(
                    sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self._schema))
                )
            config.DATABASE_URL = make_conninfo(
                self._base_database_url,
                options=f"-csearch_path={self._schema}",
            )
            database.initialize_database()
        except Exception:
            config.DATABASE_URL = self._original_database_url
            try:
                with psycopg.connect(self._base_database_url, autocommit=True) as admin:
                    admin.execute(
                        sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                            sql.Identifier(self._schema)
                        )
                    )
            finally:
                shutil.rmtree(self._tmp_dir, ignore_errors=True)
            raise

    def tearDown(self):
        config.DATABASE_URL = self._original_database_url
        try:
            with psycopg.connect(self._base_database_url, autocommit=True) as admin:
                admin.execute(
                    sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                        sql.Identifier(self._schema)
                    )
                )
        finally:
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
