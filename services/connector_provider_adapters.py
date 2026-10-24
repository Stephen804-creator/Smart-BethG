"""Live, bounded provider adapters for authorized OAuth installations."""
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import config
from services.connector_secrets import ConnectorSecretStore


class ProviderAdapter:
    def __init__(self, provider, secrets_store=None):
        self.provider = provider
        self.secrets = secrets_store or ConnectorSecretStore()

    def execute(self, action, arguments, context):
        stored = self.secrets.get(context["installation_id"])
        if not stored:
            return {"success": False, "status": "unavailable", "detail": "Provider credentials are missing."}
        credentials = stored["credentials"]
        expires = stored.get("expires_at")
        if isinstance(expires, str):
            try:
                expires = datetime.fromisoformat(expires.replace("Z", "+00:00"))
            except ValueError:
                expires = None
        if self.provider == "google_drive" and expires and expires <= datetime.now(timezone.utc) + timedelta(seconds=60):
            refresh_token = credentials.get("refresh_token")
            if not refresh_token:
                return {"success": False, "status": "reauthorization_required", "detail": "Reconnect Google Drive to renew access."}
            try:
                response = httpx.post("https://oauth2.googleapis.com/token", data={
                    "client_id": config.GOOGLE_OAUTH_CLIENT_ID,
                    "client_secret": config.GOOGLE_OAUTH_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                }, timeout=15.0)
                response.raise_for_status()
                renewed = response.json()
                if not renewed.get("access_token"):
                    raise ValueError("Missing refreshed access token.")
                credentials["access_token"] = renewed["access_token"]
                new_expiry = datetime.now(timezone.utc) + timedelta(seconds=int(renewed.get("expires_in", 3600)))
                self.secrets.put(context["installation_id"], credentials, stored.get("provider_account"),
                                 stored.get("scopes"), new_expiry)
                stored = self.secrets.get(context["installation_id"])
                credentials = stored["credentials"]
            except (httpx.RequestError, httpx.HTTPStatusError, ValueError):
                return {"success": False, "status": "reauthorization_required",
                        "detail": "Google Drive access could not be refreshed; reconnect the account."}
        token = credentials.get("access_token")
        if not token:
            return {"success": False, "status": "unavailable", "detail": "Provider credentials are missing."}
        try:
            if self.provider == "github":
                result = self._github(token, action, arguments, context)
            elif self.provider == "google_drive":
                result = self._drive(token, action, arguments)
            elif self.provider == "slack":
                result = self._slack(token, action, arguments, context)
            else:
                return {"success": False, "status": "unsupported"}
            return {"success": True, "status": "completed", "data": result}
        except httpx.HTTPStatusError as exc:
            return {"success": False, "status": "provider_error",
                    "detail": f"Provider returned HTTP {exc.response.status_code}."}
        except (httpx.RequestError, ValueError, KeyError):
            return {"success": False, "status": "provider_error", "detail": "Provider request failed."}

    def _github(self, token, action, args, context):
        headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                   "X-GitHub-Api-Version": "2022-11-28"}
        repo = args.get("repository", "").strip("/")
        if len(repo.split("/")) != 2 or any(not part or part in {".", ".."} for part in repo.split("/")):
            raise ValueError("Invalid repository.")
        if action == "issues.list":
            response = httpx.get(f"https://api.github.com/repos/{repo}/issues",
                params={"state": args.get("state", "open"), "per_page": max(1, min(50, args.get("limit", 10)))},
                headers=headers, timeout=15.0)
            response.raise_for_status()
            return [{"number": item["number"], "title": item["title"], "state": item["state"],
                     "url": item["html_url"], "is_pull_request": "pull_request" in item}
                    for item in response.json()]
        if action == "issues.create":
            title = args["title"].strip()
            if not title:
                raise ValueError("Issue title cannot be blank.")
            body = args.get("body", "")
            key = context.get("idempotency_key")
            marker = "<!-- smart-bethg-idempotency:" + str(key) + " -->" if key else None
            if marker:
                recent = httpx.get(f"https://api.github.com/repos/{repo}/issues",
                    params={"state": "all", "per_page": 100}, headers=headers, timeout=15.0)
                recent.raise_for_status()
                existing = next((item for item in recent.json() if marker in (item.get("body") or "")), None)
                if existing:
                    return {"number": existing["number"], "title": existing["title"],
                            "url": existing["html_url"], "deduplicated": True}
                body = (body + chr(10) * 2 + marker)[:60000]
            response = httpx.post(f"https://api.github.com/repos/{repo}/issues",
                json={"title": title, "body": body}, headers=headers, timeout=15.0)
            response.raise_for_status()
            issue = response.json()
            return {"number": issue["number"], "title": issue["title"], "url": issue["html_url"]}
        raise ValueError("Unsupported GitHub action.")

    def _drive(self, token, action, args):
        if action != "files.search":
            raise ValueError("Unsupported Google Drive action.")
        query = args["query"].replace(chr(92), chr(92) * 2).replace("'", chr(92) + "'")
        response = httpx.get("https://www.googleapis.com/drive/v3/files",
            params={"q": f"trashed = false and name contains '{query[:200]}'",
                    "pageSize": max(1, min(50, args.get("limit", 10))),
                    "fields": "files(id,name,mimeType,webViewLink,modifiedTime)",
                    "orderBy": "modifiedTime desc"},
            headers={"Authorization": "Bearer " + token}, timeout=15.0)
        response.raise_for_status()
        return response.json().get("files", [])

    def _slack(self, token, action, args, context):
        if action != "messages.send":
            raise ValueError("Unsupported Slack action.")
        message_text = args["text"].strip()
        if not message_text or len(message_text) > 40000:
            raise ValueError("Slack message length is invalid.")
        message = {"channel": args["channel"], "text": message_text}
        key = context.get("idempotency_key")
        if key:
            message["client_msg_id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, "smart-bethg:" + str(key)))
        response = httpx.post("https://slack.com/api/chat.postMessage", json=message,
            headers={"Authorization": "Bearer " + token}, timeout=15.0)
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise ValueError("Slack rejected the message.")
        return {"channel": data.get("channel"), "ts": data.get("ts"), "message_sent": True}
