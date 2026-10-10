from tests.base import SmartBethGTestCase
import config
import database


class TestDatabaseSchema(SmartBethGTestCase):
    EXPECTED_TABLES = {
        "users", "agents", "tasks", "approvals", "audit_events", "tools",
        "providers", "conversations", "messages", "missions", "mission_runs",
        "files", "memory", "research", "evidence", "workflows", "artifacts",
        "social_content", "projects", "logs",
    }

    def test_all_expected_tables_exist(self):
        conn = database.get_connection()
        try:
            names = {
                row["name"]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        finally:
            conn.close()
        missing = self.EXPECTED_TABLES - names
        self.assertEqual(missing, set(), f"Missing tables: {missing}")

    def test_initialize_is_idempotent(self):
        # Running it again must not raise or duplicate/lose anything.
        database.initialize_database()
        database.initialize_database()
        conn = database.get_connection()
        try:
            count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        finally:
            conn.close()
        self.assertEqual(count, 0)

    def test_users_migration_adds_oauth_columns(self):
        conn = database.get_connection()
        try:
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
        finally:
            conn.close()
        self.assertIn("oauth_provider", cols)
        self.assertIn("oauth_subject", cols)

    def test_production_refuses_sqlite_or_missing_database_url(self):
        original_production = config.IS_PRODUCTION
        original_url = config.DATABASE_URL
        try:
            config.IS_PRODUCTION = True
            for invalid_url in ("", "sqlite:///should-not-be-used.db"):
                config.DATABASE_URL = invalid_url
                with self.subTest(database_url=invalid_url):
                    with self.assertRaisesRegex(RuntimeError, "requires DATABASE_URL.*PostgreSQL"):
                        database.get_connection()
        finally:
            config.IS_PRODUCTION = original_production
            config.DATABASE_URL = original_url

    def test_messages_migration_adds_token_columns(self):
        conn = database.get_connection()
        try:
            cols = {r["name"] for r in conn.execute("PRAGMA table_info(messages)").fetchall()}
        finally:
            conn.close()
        self.assertIn("tokens_in", cols)
        self.assertIn("tokens_out", cols)
