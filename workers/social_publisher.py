"""Durable social publication worker; run as a separate process.

The worker is provider-neutral. A job is marked indeterminate after an unknown
provider outcome; it is never blindly replayed because that could duplicate a
real external post. Platform adapters must provide their own idempotency and
provider reconciliation.
"""
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone

from connectors.social import ConnectorNotConfigured, SocialConnectorRegistry
from database import get_connection

logger = logging.getLogger("smart_bethg.social_worker")


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SocialPublisherWorker:
    def __init__(self, registry=None, batch_size=10, lease_seconds=120):
        self.registry = registry or SocialConnectorRegistry()
        self.batch_size = max(1, min(int(batch_size), 50))
        self.lease_seconds = max(30, min(int(lease_seconds), 900))

    def claim_due_jobs(self):
        now = _utc_now()
        lease_until = (datetime.now(timezone.utc) + timedelta(seconds=self.lease_seconds)).isoformat(timespec="seconds")
        conn = get_connection()
        try:
            if getattr(conn, "is_postgres", False):
                rows = conn.execute(
                    "WITH due AS ("
                    " SELECT j.id FROM social_publish_jobs j "
                    " JOIN social_campaigns c ON c.id=j.campaign_id AND c.user_id=j.user_id "
                    " WHERE j.status='queued' AND j.scheduled_at<=? AND c.status='active' "
                    " ORDER BY j.scheduled_at, j.id LIMIT ? FOR UPDATE OF j SKIP LOCKED"
                    ") "
                    "UPDATE social_publish_jobs j SET status='publishing', lease_until=?, "
                    "attempts=j.attempts+1, updated_at=CURRENT_TIMESTAMP "
                    "WHERE j.id IN (SELECT id FROM due) RETURNING j.id",
                    (now, self.batch_size, lease_until),
                ).fetchall()
                conn.commit()
                return [int(row["id"]) for row in rows]
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                "SELECT j.id FROM social_publish_jobs j "
                "JOIN social_campaigns c ON c.id=j.campaign_id AND c.user_id=j.user_id "
                "WHERE j.status='queued' AND j.scheduled_at<=? AND c.status='active' "
                "ORDER BY j.scheduled_at, j.id LIMIT ?",
                (now, self.batch_size),
            ).fetchall()
            ids = [int(row["id"]) for row in rows]
            for job_id in ids:
                conn.execute(
                    "UPDATE social_publish_jobs SET status='publishing', lease_until=?, "
                    "attempts=attempts+1, updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='queued'",
                    (lease_until, job_id),
                )
            conn.commit()
            return ids
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _load_job(self, job_id):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT j.*, c.status AS campaign_status, c.autonomy_mode, c.autopublish_authorized_at, "
                "s.status AS content_status, s.topic AS title, s.caption AS content, s.hashtags, "
                "sc.credential_ref, sc.status AS connection_status "
                "FROM social_publish_jobs j "
                "JOIN social_campaigns c ON c.id=j.campaign_id AND c.user_id=j.user_id "
                "JOIN social_content s ON s.id=j.content_id AND s.user_id=j.user_id "
                "LEFT JOIN social_connections sc ON sc.id=j.connection_id AND sc.user_id=j.user_id "
                "WHERE j.id=? LIMIT 1",
                (job_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def _update_job(self, job_id, status, *, error_code=None, error_message=None,
                    external_post_id=None, published_at=None):
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE social_publish_jobs SET status=?, error_code=?, error_message=?, "
                "external_post_id=?, published_at=?, lease_until=NULL, updated_at=CURRENT_TIMESTAMP "
                "WHERE id=? AND status='publishing'",
                (status, error_code, error_message, external_post_id, published_at, job_id),
            )
            if status == "published":
                row = conn.execute(
                    "SELECT content_id, user_id, external_post_id, published_at FROM social_publish_jobs WHERE id=?",
                    (job_id,),
                ).fetchone()
                if row:
                    conn.execute(
                        "UPDATE social_content SET status='published', external_post_id=?, published_at=?, "
                        "updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",
                        (row["external_post_id"], row["published_at"], row["content_id"], row["user_id"]),
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def run_once(self):
        claimed = self.claim_due_jobs()
        results = []
        for job_id in claimed:
            job = self._load_job(job_id)
            if not job:
                self._update_job(job_id, "indeterminate", error_code="job_record_missing",
                                 error_message="The claimed job could not be reloaded; inspect database state.")
                results.append({"job_id": job_id, "status": "indeterminate"})
                continue
            if job["campaign_status"] != "active":
                self._update_job(job_id, "blocked", error_code="campaign_not_active",
                                 error_message="Campaign was not active at execution time.")
                results.append({"job_id": job_id, "status": "blocked"})
                continue
            if job["content_status"] != "approved":
                self._update_job(job_id, "blocked", error_code="post_not_approved",
                                 error_message="The post is not approved for publication.")
                results.append({"job_id": job_id, "status": "blocked"})
                continue
            if not job.get("connection_id") or not job.get("credential_ref") or job.get("connection_status") != "active":
                self._update_job(job_id, "blocked", error_code="connection_required",
                                 error_message="No verified account credential reference is attached.")
                results.append({"job_id": job_id, "status": "blocked"})
                continue
            try:
                publisher = self.registry.get_publisher(job["platform"])
            except ConnectorNotConfigured as exc:
                self._update_job(job_id, "blocked", error_code="connector_not_configured",
                                 error_message=str(exc))
                results.append({"job_id": job_id, "status": "blocked"})
                continue
            try:
                try:
                    hashtags = json.loads(job.get("hashtags") or "[]")
                except (TypeError, json.JSONDecodeError):
                    hashtags = []
                outcome = publisher.publish(
                    account_ref=job["credential_ref"],
                    content={
                        "platform": job["platform"],
                        "title": job["title"],
                        "content": job["content"],
                        "hashtags": hashtags,
                    },
                    idempotency_key=job["idempotency_key"],
                )
                post_id = outcome.get("external_post_id") if isinstance(outcome, dict) else None
                if not post_id:
                    self._update_job(job_id, "indeterminate", error_code="missing_provider_post_id",
                                     error_message="Provider returned no external post ID; reconcile before retrying.")
                    results.append({"job_id": job_id, "status": "indeterminate"})
                    continue
                published_at = _utc_now()
                self._update_job(job_id, "published", external_post_id=str(post_id), published_at=published_at)
                results.append({"job_id": job_id, "status": "published"})
            except Exception:
                # Do not log tokens, provider response bodies, or post content.
                logger.exception("Social publish job outcome unknown: job_id=%s platform=%s", job_id, job["platform"])
                self._update_job(job_id, "indeterminate", error_code="provider_outcome_unknown",
                                 error_message="Provider outcome is unknown. Reconcile with the platform before retrying.")
                results.append({"job_id": job_id, "status": "indeterminate"})
        return results

    def recover_expired_leases(self):
        """Mark abandoned in-flight jobs indeterminate instead of replaying them."""
        now = _utc_now()
        conn = get_connection()
        try:
            cursor = conn.execute(
                "UPDATE social_publish_jobs SET status='indeterminate', lease_until=NULL, "
                "error_code='worker_lease_expired', "
                "error_message='Worker stopped after claiming this job; verify provider state before retrying.', "
                "updated_at=CURRENT_TIMESTAMP WHERE status='publishing' AND lease_until IS NOT NULL AND lease_until<?",
                (now,),
            )
            conn.commit()
            return cursor.rowcount
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def main():
    poll_seconds = max(1, min(int(os.getenv("SMART_BETHG_SOCIAL_WORKER_POLL_SECONDS", "5")), 60))
    worker = SocialPublisherWorker()
    logger.info("Smart BethG social publishing worker started; poll=%ss", poll_seconds)
    while True:
        try:
            recovered = worker.recover_expired_leases()
            if recovered:
                logger.warning("Marked %s expired publication leases indeterminate", recovered)
            results = worker.run_once()
            for result in results:
                logger.info("Social publication result: job_id=%s status=%s", result["job_id"], result["status"])
        except Exception:
            logger.exception("Social publishing worker iteration failed")
        time.sleep(poll_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    main()
