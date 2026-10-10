"""
Smart BethG - Model Evaluation (T0504)

Records every provider call attempt - including ones that failed and
got silently retried via fallback - not just the one that ultimately
answered. Without this, fallback (T0503) would be invisible: you'd
never know a provider was failing 30% of the time if the user only ever
sees the eventual successful reply.
"""
from database import get_connection


class ModelEvaluationService:
    def record_call(self, user_id, provider, model, success, latency_ms, error=None):
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO provider_calls(user_id, provider, model, success, latency_ms, error) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, provider, model, 1 if success else 0, latency_ms, error),
            )
            conn.commit()
        finally:
            conn.close()

    def stats(self):
        """
        Aggregated, global (not per-user) - reliability of a given
        provider+model is an operational fact, not private data. Returns
        one row per (provider, model) actually attempted at least once.
        """
        conn = get_connection()
        try:
            rows = conn.execute(
                """
                SELECT provider, model,
                       COUNT(*) AS attempts,
                       SUM(success) AS successes,
                       AVG(latency_ms) AS avg_latency_ms
                FROM provider_calls
                GROUP BY provider, model
                ORDER BY attempts DESC
                """
            ).fetchall()
            result = []
            for r in rows:
                attempts = r["attempts"]
                successes = r["successes"] or 0
                result.append({
                    "provider": r["provider"],
                    "model": r["model"],
                    "attempts": attempts,
                    "successes": successes,
                    "success_rate": round(successes / attempts, 4) if attempts else None,
                    "avg_latency_ms": round(r["avg_latency_ms"]) if r["avg_latency_ms"] is not None else None,
                })
            return result
        finally:
            conn.close()
