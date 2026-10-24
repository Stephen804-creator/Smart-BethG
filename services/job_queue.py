"""Durable PostgreSQL job queue with leases, idempotency and bounded retries."""
import json, uuid, threading, time
from datetime import datetime,timedelta,timezone
from database import get_connection

def _now(): return datetime.now(timezone.utc)
def _iso(value): return value.isoformat(timespec="microseconds")

class JobQueue:
    VALID_TYPES={"mission.execute","workflow.execute"}
    def enqueue(self,user_id,job_type,payload,idempotency_key,priority=0,max_attempts=5):
        conn=get_connection()
        try:
            job=self.enqueue_in_transaction(conn,user_id,job_type,payload,idempotency_key,priority,max_attempts)
            conn.commit(); return job
        except Exception:
            conn.rollback(); raise
        finally: conn.close()
    def enqueue_in_transaction(self,conn,user_id,job_type,payload,idempotency_key,priority=0,max_attempts=5):
        if job_type not in self.VALID_TYPES: raise ValueError("Unsupported background job type.")
        if not isinstance(payload,dict) or len(json.dumps(payload,default=str))>100000: raise ValueError("Job payload must be an object no larger than 100 KB.")
        if not idempotency_key or len(str(idempotency_key))>200: raise ValueError("A bounded idempotency key is required.")
        if not 1<=int(max_attempts)<=10: raise ValueError("max_attempts must be between 1 and 10.")
        conn.execute("INSERT INTO background_jobs(id,user_id,job_type,payload_json,status,priority,idempotency_key,max_attempts,available_at) VALUES (?,?,?,?,'queued',?,?,?,?) ON CONFLICT(user_id,idempotency_key) DO NOTHING",
                     (str(uuid.uuid4()),user_id,job_type,json.dumps(payload,ensure_ascii=False),max(-10,min(10,int(priority))),str(idempotency_key),int(max_attempts),_iso(_now())))
        row=conn.execute("SELECT id,user_id,job_type,status,idempotency_key FROM background_jobs WHERE user_id=? AND idempotency_key=? LIMIT 1",(user_id,str(idempotency_key))).fetchone()
        if not row: raise RuntimeError("Could not persist background job.")
        return dict(row)
    def get_for_user(self,user_id,job_id):
        conn=get_connection()
        try:
            row=conn.execute("SELECT id,user_id,job_type,status,attempts,max_attempts,priority,available_at,started_at,completed_at,last_error,result_json,created_at FROM background_jobs WHERE id=? AND user_id=? LIMIT 1",(job_id,user_id)).fetchone()
            return self._decode(row) if row else None
        finally: conn.close()
    def list_for_user(self,user_id,limit=50):
        conn=get_connection()
        try:
            rows=conn.execute("SELECT id,user_id,job_type,status,attempts,max_attempts,priority,idempotency_key,available_at,started_at,completed_at,last_error,result_json,created_at FROM background_jobs WHERE user_id=? ORDER BY created_at DESC LIMIT ?",(user_id,max(1,min(100,int(limit))))).fetchall()
            return [self._decode(row) for row in rows]
        finally: conn.close()
    def claim(self,lease_seconds=90):
        now=_now(); token=str(uuid.uuid4()); conn=get_connection()
        try:
            conn.execute("BEGIN")
            conn.execute("UPDATE background_jobs SET status='failed',last_error='Worker lease expired after maximum attempts.',completed_at=?,updated_at=?,lease_token=NULL,lease_until=NULL WHERE status='running' AND lease_until<? AND attempts>=max_attempts",
                         (_iso(now), _iso(now), _iso(now)))
            row=conn.execute("WITH candidate AS (SELECT id FROM background_jobs WHERE ((status='queued' AND available_at<=?) OR (status='running' AND lease_until<?)) AND attempts<max_attempts ORDER BY priority DESC,available_at,created_at FOR UPDATE SKIP LOCKED LIMIT 1) UPDATE background_jobs AS job SET status='running',attempts=job.attempts+1,lease_token=?,lease_until=?,started_at=COALESCE(job.started_at,?),updated_at=? FROM candidate WHERE job.id=candidate.id RETURNING job.id,job.user_id,job.job_type,job.payload_json,job.attempts,job.max_attempts,job.idempotency_key,job.lease_token",
                            (_iso(now),_iso(now),token,_iso(now+timedelta(seconds=lease_seconds)),_iso(now),_iso(now))).fetchone()
            conn.commit()
            if not row: return None
            item=dict(row); item["payload"]=json.loads(item.pop("payload_json") or "{}"); return item
        except Exception:
            conn.rollback(); raise
        finally: conn.close()
    def heartbeat(self,job_id,lease_token,lease_seconds=90):
        conn=get_connection()
        try:
            cursor=conn.execute("UPDATE background_jobs SET lease_until=?,updated_at=? WHERE id=? AND status='running' AND lease_token=?",
                                (_iso(_now()+timedelta(seconds=lease_seconds)),_iso(_now()),job_id,lease_token))
            conn.commit(); return cursor.rowcount==1
        finally: conn.close()
    def complete(self,job,result):
        serialized=json.dumps(result,ensure_ascii=False,default=str)
        if len(serialized)>100000: serialized=json.dumps({"summary":"Result omitted because it exceeded 100 KB."})
        conn=get_connection()
        try:
            cursor=conn.execute("UPDATE background_jobs SET status='succeeded',result_json=?,completed_at=?,updated_at=?,lease_token=NULL,lease_until=NULL WHERE id=? AND status='running' AND lease_token=?",
                                (serialized,_iso(_now()),_iso(_now()),job["id"],job["lease_token"]))
            conn.commit(); return cursor.rowcount==1
        finally: conn.close()
    def fail(self,job,error,retryable=True):
        now=_now(); retry=retryable and int(job["attempts"])<int(job["max_attempts"])
        new_status="queued" if retry else "failed"; delay=min(300,2**min(int(job["attempts"]),8)); conn=get_connection()
        try:
            cursor=conn.execute("UPDATE background_jobs SET status=?,last_error=?,available_at=?,completed_at=?,updated_at=?,lease_token=NULL,lease_until=NULL WHERE id=? AND status='running' AND lease_token=?",
                                (new_status,str(error)[:4000],_iso(now+timedelta(seconds=delay)),None if retry else _iso(now),_iso(now),job["id"],job["lease_token"]))
            conn.commit(); return cursor.rowcount==1
        finally: conn.close()
    def cancel(self,user_id,job_id):
        conn=get_connection()
        try:
            cursor=conn.execute("UPDATE background_jobs SET status='cancelled',completed_at=?,updated_at=? WHERE id=? AND user_id=? AND status='queued'",
                                (_iso(_now()),_iso(_now()),job_id,user_id))
            conn.commit(); return cursor.rowcount==1
        finally: conn.close()
    @staticmethod
    def _decode(row):
        item=dict(row)
        if item.get("result_json"):
            try: item["result"]=json.loads(item.pop("result_json"))
            except (TypeError,json.JSONDecodeError): item["result"]=None; item.pop("result_json",None)
        else: item.pop("result_json",None)
        return item

class JobWorker:
    def __init__(self,queue=None,handlers=None):
        self.queue=queue or JobQueue(); self.handlers=dict(handlers or {})
    def run_once(self):
        job=self.queue.claim()
        if not job: return False
        handler=self.handlers.get(job["job_type"])
        if handler is None:
            self.queue.fail(job,"No trusted handler is registered for this job type.",retryable=False); return True
        stop=threading.Event()
        def renew_lease():
            while not stop.wait(20):
                try:
                    if not self.queue.heartbeat(job["id"],job["lease_token"],lease_seconds=90):
                        return
                except Exception:
                    # If the database is temporarily unavailable, the lease can
                    # expire and another worker may reclaim the job. Adapters
                    # must use the job's idempotency key for side effects.
                    return
        heartbeat=threading.Thread(target=renew_lease,daemon=True)
        heartbeat.start()
        try:
            result=handler(job)
            self.queue.complete(job,result)
        except Exception as exc:
            self.queue.fail(job,f"{type(exc).__name__}: {exc}",retryable=True)
        finally:
            stop.set()
            heartbeat.join(timeout=1)
        return True
