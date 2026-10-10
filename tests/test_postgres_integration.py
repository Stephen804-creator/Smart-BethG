"""Smoke tests for the production PostgreSQL adapter (run by CI's PG service)."""
import os
import uuid
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from cryptography.fernet import Fernet

import config
from database import _run_postgres_migrations, get_connection, initialize_database
from repositories.conversation_repository import ConversationRepository
from services.approval_service import ApprovalService
from services.auth_service import create_user
from services.artifact_service import ArtifactService
from services.credential_vault import CredentialVault
from services.social_campaign_service import SocialCampaignService
from workers.social_publisher import SocialPublisherWorker
from services.file_service import FileService
from services.rate_limiter import check_rate_limit
from services.usage_budget_service import BudgetExceededError, UsageBudgetService


@unittest.skipUnless(
    os.getenv("SMART_BETHG_RUN_POSTGRES_TESTS") == "1",
    "Requires the dedicated PostgreSQL integration-test job",
)
class TestPostgreSQLIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialize_database()

    def test_versioned_baseline_migration_is_recorded_and_idempotent(self):
        conn = get_connection()
        try:
            version = "0001_initial_schema.sql"
            row = conn.execute(
                "SELECT version FROM schema_migrations WHERE version=?",
                (version,),
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["version"], version)
            columns = conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema=current_schema() AND table_name='users' "
                "AND column_name='session_version'"
            ).fetchone()
            self.assertIsNotNone(columns)

            # Simulate a pre-versioned database missing a column added by
            # the baseline migration. Re-running the migration must upgrade it.
            conn.execute("ALTER TABLE users DROP COLUMN IF EXISTS session_version")
            conn.execute("DELETE FROM schema_migrations WHERE version=?", (version,))
            conn.commit()
            _run_postgres_migrations(conn)
            adopted = conn.execute(
                "SELECT version FROM schema_migrations WHERE version=?", (version,)
            ).fetchone()
            self.assertIsNotNone(adopted)
            restored_column = conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema=current_schema() AND table_name='users' "
                "AND column_name='session_version'"
            ).fetchone()
            self.assertIsNotNone(restored_column)
        finally:
            conn.close()

    def test_concurrent_app_startup_serializes_schema_migrations(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: initialize_database(), range(4)))
        self.assertEqual(results, [None, None, None, None])

    def test_user_conversation_and_approval_round_trip(self):
        suffix = uuid.uuid4().hex[:12]
        user = create_user("pg-" + suffix, "test-password-123")
        self.assertIsNotNone(user)
        self.assertGreater(user["id"], 0)

        repo = ConversationRepository()
        conversation_id = repo.create(user["id"], "PostgreSQL integration")
        self.assertGreater(conversation_id, 0)
        repo.add_message(conversation_id, "user", "hello")
        messages = repo.list_messages(conversation_id)
        self.assertEqual(messages[0]["content"], "hello")

        approvals = ApprovalService()
        pending = approvals.create(user["id"], "git.write", "workspace:default")
        decided = approvals.decide(pending["id"], user["id"], True)
        self.assertEqual(decided["status"], "approved")

    def test_database_backed_usage_budget_reservation(self):
        suffix = uuid.uuid4().hex[:12]
        user = create_user("pg-budget-" + suffix, "test-password-123")
        budget = UsageBudgetService()
        reservation = budget.reserve(user["id"], "openrouter", "openrouter/free", 100, 100)
        self.assertTrue(budget.reconcile(reservation["id"], 90, 80))
        usage = budget.get_usage(user["id"])
        self.assertEqual(usage["actual_tokens"], 170)
        self.assertEqual(usage["requests"], 1)

    def test_file_storage_round_trip_and_owner_isolation(self):
        suffix = uuid.uuid4().hex[:12]
        owner = create_user("pg-file-owner-" + suffix, "test-password-123")
        other = create_user("pg-file-other-" + suffix, "test-password-123")
        service = FileService()
        record = service.save_upload(owner["id"], "note.txt", b"PostgreSQL file round trip\n", "text/plain")
        self.assertIsNotNone(record)
        self.assertEqual(service.list_files(owner["id"])[0]["id"], record["id"])

        data, owned_record = service.read_bytes(owner["id"], record["id"])
        self.assertEqual(data, b"PostgreSQL file round trip\n")
        self.assertIsNotNone(owned_record)

        foreign_data, foreign_record = service.read_bytes(other["id"], record["id"])
        self.assertIsNone(foreign_data)
        self.assertIsNone(foreign_record)
        self.assertTrue(service.delete_file(owner["id"], record["id"]))
        self.assertIsNone(service.get_file(owner["id"], record["id"]))

    def test_social_campaign_credential_vault_and_postgres_worker_claim(self):
        suffix = uuid.uuid4().hex[:12]
        user = create_user("pg-social-" + suffix, "test-password-123")
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=2)).isoformat(timespec="seconds")
        end = (now + timedelta(days=3)).isoformat(timespec="seconds")
        service = SocialCampaignService()
        campaign = service.create(
            user["id"], name="PG social " + suffix, objective="Verify durable queue",
            platforms=["facebook"], timezone_name="Africa/Lagos",
            start_at=start, end_at=end, daily_post_limit=2,
        )
        service.add_posts(user["id"], campaign["id"], [{
            "platform": "facebook", "title": "Post", "content": "Post content",
            "scheduled_at": start,
        }])

        vault = CredentialVault(key=Fernet.generate_key())
        credential_ref = vault.store(user["id"], "meta", "integration-test-token")
        self.assertEqual(vault.resolve(credential_ref, user["id"], "meta"), "integration-test-token")

        conn = get_connection()
        try:
            conn.execute(
                "UPDATE social_campaigns SET status='active' WHERE id=? AND user_id=?",
                (campaign["id"], user["id"]),
            )
            conn.execute(
                "UPDATE social_content SET status='approved' WHERE campaign_id=? AND user_id=?",
                (campaign["id"], user["id"]),
            )
            conn.execute(
                "INSERT INTO social_connections(user_id, platform, external_account_id, display_name, "
                "credential_ref, scopes_json, status, connected_at) "
                "VALUES (?, 'facebook', ?, 'PG Page', ?, '[]', 'active', CURRENT_TIMESTAMP)",
                (user["id"], "pg-page-" + suffix, credential_ref),
            )
            connection = conn.execute(
                "SELECT id FROM social_connections WHERE user_id=? AND platform='facebook' "
                "AND external_account_id=?",
                (user["id"], "pg-page-" + suffix),
            ).fetchone()
            job = conn.execute(
                "SELECT id FROM social_publish_jobs WHERE user_id=? AND campaign_id=?",
                (user["id"], campaign["id"]),
            ).fetchone()
            conn.execute(
                "UPDATE social_publish_jobs SET status='queued', connection_id=? WHERE id=? AND user_id=?",
                (connection["id"], job["id"], user["id"]),
            )
            conn.commit()
        finally:
            conn.close()

        worker = SocialPublisherWorker(registry=object())
        claimed = worker.claim_due_jobs()
        self.assertIn(job["id"], claimed)
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE social_publish_jobs SET status='blocked', lease_until=NULL, "
                "error_code='test_cleanup' WHERE id=?",
                (job["id"],),
            )
            conn.commit()
        finally:
            conn.close()

    def test_artifact_storage_round_trip_and_owner_isolation(self):
        suffix = uuid.uuid4().hex[:12]
        owner = create_user("pg-artifact-owner-" + suffix, "test-password-123")
        other = create_user("pg-artifact-other-" + suffix, "test-password-123")
        service = ArtifactService()
        payload = bytes([137]) + b"PNG" + bytes([13, 10, 26, 10]) + b"postgres-artifact"
        artifact = service.create_bytes(owner["id"], "pg-image.png", payload, "image/png")
        try:
            stored, record = service.read_bytes(owner["id"], artifact["id"])
            self.assertEqual(stored, payload)
            self.assertEqual(record["content_type"], "image/png")
            foreign, foreign_record = service.read_bytes(other["id"], artifact["id"])
            self.assertIsNone(foreign)
            self.assertIsNone(foreign_record)
        finally:
            service.delete(owner["id"], artifact["id"])

    def test_database_backed_rate_limiter(self):
        key = "pg-integration:" + uuid.uuid4().hex
        self.assertTrue(check_rate_limit(key))


    def test_concurrent_user_budget_reservations_cannot_overspend(self):
        suffix = uuid.uuid4().hex[:12]
        user = create_user("pg-budget-race-" + suffix, "test-password-123")
        service = UsageBudgetService()
        names = (
            "USER_DAILY_TOKEN_BUDGET",
            "GLOBAL_DAILY_TOKEN_BUDGET",
            "USER_DAILY_SPEND_USD",
            "GLOBAL_DAILY_SPEND_USD",
            "USER_DAILY_REQUEST_BUDGET",
            "GLOBAL_DAILY_REQUEST_BUDGET",
        )
        original = {name: getattr(config, name) for name in names}
        try:
            config.USER_DAILY_TOKEN_BUDGET = 200
            config.GLOBAL_DAILY_TOKEN_BUDGET = 100000
            config.USER_DAILY_SPEND_USD = 100.0
            config.GLOBAL_DAILY_SPEND_USD = 1000.0
            config.USER_DAILY_REQUEST_BUDGET = 100
            config.GLOBAL_DAILY_REQUEST_BUDGET = 1000

            def reserve_one(_):
                try:
                    service.reserve(user["id"], "openrouter", "openrouter/free", 50, 50)
                    return True
                except BudgetExceededError:
                    return False

            with ThreadPoolExecutor(max_workers=12) as pool:
                outcomes = list(pool.map(reserve_one, range(12)))
            self.assertEqual(sum(outcomes), 2)
            usage = service.get_usage(user["id"])
            self.assertLessEqual(
                usage["tokens_reserved_or_used"],
                config.USER_DAILY_TOKEN_BUDGET,
            )
        finally:
            for name, value in original.items():
                setattr(config, name, value)

    def test_database_rate_limiter_is_atomic_under_concurrency(self):
        key = "pg-concurrency:" + uuid.uuid4().hex
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(
                lambda _: check_rate_limit(key, max_attempts=5, window_seconds=60),
                range(24),
            ))
        self.assertEqual(sum(results), 5)


if __name__ == "__main__":
    unittest.main()
