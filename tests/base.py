"""
Shared PostgreSQL test infrastructure.

Each test receives a unique PostgreSQL schema so it cannot share application
tables or records with another test or a developer's database. Tests refuse to
fall back to SQLite and require an explicitly named test database URL.
"""
import os
import re
import shutil
import tempfile
import unittest
import uuid
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import psycopg
from psycopg import sql

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
                "SMART_BETHG_TEST_DATABASE_URL must point to a disposable PostgreSQL "
                "test database. Tests never use SQLite or production DATABASE_URL."
            )
        if not self._base_database_url.startswith(
            ("postgres://", "postgresql://", "postgresql+psycopg://")
        ):
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
            self.fail("SMART_BETHG_TEST_DATABASE_URL must be a PostgreSQL connection URL.")

        # Fail closed before connecting or creating a schema if the database name
        # does not explicitly identify it as a test database. This reduces the
        # chance that a misconfigured test command touches a developer/prod DB.
        normalized_url = self._base_database_url.replace(
            "postgresql+psycopg://", "postgresql://", 1
        ).replace("postgres://", "postgresql://", 1)
        parsed = urlsplit(normalized_url)
        database_name = parsed.path.rsplit("/", 1)[-1].lower()
        if not re.search(r"(?:^|[_-])test(?:$|[_-])", database_name):
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
            self.fail(
                "SMART_BETHG_TEST_DATABASE_URL database name must explicitly contain "
                "'test' as a separate word (for example smartbethg_test). "
                "No connection or schema changes were attempted."
            )

        self._admin_database_url = normalized_url
        self._schema = "sb_test_" + uuid.uuid4().hex
        try:
            with psycopg.connect(self._admin_database_url, autocommit=True) as admin:
                admin.execute(
                    sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self._schema))
                )
            # Keep DATABASE_URL URL-shaped because the application validates its scheme.
            # libpq's options query parameter sets an isolated per-test search_path.
            query = parse_qsl(parsed.query, keep_blank_values=True)
            query.append(("options", f"-csearch_path={self._schema}"))
            config.DATABASE_URL = urlunsplit((
                parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment
            ))
            database.initialize_database()
        except Exception:
            config.DATABASE_URL = self._original_database_url
            try:
                with psycopg.connect(self._admin_database_url, autocommit=True) as admin:
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
            with psycopg.connect(self._admin_database_url, autocommit=True) as admin:
                admin.execute(
                    sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                        sql.Identifier(self._schema)
                    )
                )
        finally:
            shutil.rmtree(self._tmp_dir, ignore_errors=True)
