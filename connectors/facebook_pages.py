"""Facebook Pages text-post publisher using the official Meta Graph API."""
import os
import re

import requests

from connectors.social import SocialConnectorInfo
from services.credential_vault import CredentialVault, CredentialVaultError


class FacebookPagesPublisher:
    info = SocialConnectorInfo(
        platform="facebook",
        display_name="Facebook Pages",
        supports_text=True,
        supports_media=False,
        requires_provider_app_review=True,
        status="configured",
        setup_notes="Text posts to an explicitly connected Page. Requires approved Meta permissions and a verified app configuration.",
    )

    def __init__(self, vault=None, api_version=None, timeout=20):
        self.vault = vault or CredentialVault()
        self.api_version = (api_version or os.getenv("SMART_BETHG_META_API_VERSION", "v26.0")).strip()
        if not re.fullmatch(r"v\d+\.\d+", self.api_version):
            raise ValueError("SMART_BETHG_META_API_VERSION must look like v26.0.")
        self.timeout = max(5, min(int(timeout), 60))

    def publish(self, *, account, content, idempotency_key):
        user_id = account.get("user_id")
        page_id = str(account.get("external_account_id") or "").strip()
        credential_ref = account.get("credential_ref")
        if not user_id or not page_id or not credential_ref:
            raise ValueError("Facebook publishing requires an owner, Page ID, and credential reference.")
        token = self.vault.resolve(credential_ref, user_id, "meta")
        message_parts = []
        title = (content.get("title") or "").strip()
        body = (content.get("content") or "").strip()
        if title:
            message_parts.append(title)
        if body and body != title:
            message_parts.append(body)
        tags = content.get("hashtags") or []
        normalized_tags = []
        for tag in tags:
            if not isinstance(tag, str):
                continue
            clean = re.sub(r"[^\w]", "", tag, flags=re.UNICODE).strip("_")
            if clean:
                normalized_tags.append("#" + clean)
        if normalized_tags:
            message_parts.append(" ".join(normalized_tags[:8]))
        message = "\n\n".join(message_parts).strip()
        if not message:
            raise ValueError("Facebook Page post content cannot be empty.")
        if len(message) > 63206:
            raise ValueError("Facebook Page text exceeds the supported message limit.")

        # Meta does not provide a general idempotency key for this endpoint.
        # The worker therefore marks timeouts indeterminate and never blindly
        # retries a potentially accepted post.
        response = requests.post(
            f"https://graph.facebook.com/{self.api_version}/{page_id}/feed",
            data={"message": message},
            headers={"Authorization": "Bearer " + token},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        external_post_id = payload.get("id") if isinstance(payload, dict) else None
        if not external_post_id:
            raise RuntimeError("Meta returned no post ID; publication outcome must be reconciled.")
        return {"external_post_id": str(external_post_id)}
