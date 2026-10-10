"""Safe, provider-neutral social publishing connector contract.

Concrete platform adapters must implement OAuth/token refresh, scope validation,
provider-specific media rules, idempotency/reconciliation, and publish(). Tokens
must be stored in a secret manager, never in this database or source code.
"""
from dataclasses import dataclass
from typing import Any, Protocol


class ConnectorNotConfigured(RuntimeError):
    """No production-ready publishing adapter is configured for this platform."""


class ConnectorActionRejected(RuntimeError):
    """Provider explicitly rejected an action; it should not be blindly retried."""


class ConnectorOutcomeUnknown(RuntimeError):
    """Provider outcome cannot be confirmed; reconcile before any retry."""


@dataclass(frozen=True)
class SocialConnectorInfo:
    platform: str
    display_name: str
    supports_text: bool
    supports_media: bool
    requires_provider_app_review: bool
    status: str
    setup_notes: str


class SocialPublisher(Protocol):
    info: SocialConnectorInfo

    def publish(self, *, account: dict[str, Any], content: dict[str, Any], idempotency_key: str) -> dict[str, str]:
        """Publish one post and return a provider post ID and canonical URL."""
        ...


class SocialConnectorRegistry:
    """Advertises integrations without pretending unimplemented adapters work."""

    _catalog = (
        SocialConnectorInfo(
            platform="facebook",
            display_name="Facebook Pages",
            supports_text=True,
            supports_media=True,
            requires_provider_app_review=True,
            status="planned",
            setup_notes="Requires a Meta app, supported Page permissions, OAuth consent, and any required app review.",
        ),
        SocialConnectorInfo(
            platform="instagram",
            display_name="Instagram Professional",
            supports_text=True,
            supports_media=True,
            requires_provider_app_review=True,
            status="planned",
            setup_notes="Requires an eligible professional account, linked Page where applicable, publishing permissions, and Meta app review.",
        ),
        SocialConnectorInfo(
            platform="youtube",
            display_name="YouTube",
            supports_text=True,
            supports_media=True,
            requires_provider_app_review=True,
            status="planned",
            setup_notes="Video upload/publishing requires Google OAuth scopes, quota planning, and applicable API verification.",
        ),
        SocialConnectorInfo(
            platform="linkedin",
            display_name="LinkedIn",
            supports_text=True,
            supports_media=True,
            requires_provider_app_review=True,
            status="planned",
            setup_notes="Requires an approved LinkedIn developer product and member/organization permissions.",
        ),
        SocialConnectorInfo(
            platform="x",
            display_name="X",
            supports_text=True,
            supports_media=True,
            requires_provider_app_review=True,
            status="planned",
            setup_notes="Requires eligible X API access, OAuth permissions, and review of current API pricing/limits.",
        ),
    )

    def __init__(self, adapters=None):
        if adapters is not None:
            self._adapters = dict(adapters)
        else:
            self._adapters = self._load_configured_adapters()

    @staticmethod
    def _load_configured_adapters():
        import os
        adapters = {}
        # Publishing is opt-in only after the operator has completed provider
        # app setup/review and configured the token-encryption key.
        enabled = os.getenv("SMART_BETHG_META_PUBLISHING_ENABLED", "").strip().lower() == "true"
        required = (
            os.getenv("SMART_BETHG_META_APP_ID", "").strip(),
            os.getenv("SMART_BETHG_META_APP_SECRET", "").strip(),
            os.getenv("SMART_BETHG_META_REDIRECT_URI", "").strip(),
            os.getenv("SMART_BETHG_TOKEN_ENCRYPTION_KEY", "").strip(),
        )
        if enabled and all(required):
            try:
                from connectors.facebook_pages import FacebookPagesPublisher
                adapters["facebook"] = FacebookPagesPublisher()
            except Exception:
                # Never log configuration values or tokens; an absent adapter
                # is surfaced as not-ready and the worker fails closed.
                adapters.pop("facebook", None)
        return adapters

    def catalog(self):
        result = []
        for info in self._catalog:
            adapter = self._adapters.get(info.platform)
            result.append({
                "platform": info.platform,
                "display_name": info.display_name,
                "supports_text": info.supports_text,
                "supports_media": info.supports_media,
                "requires_provider_app_review": info.requires_provider_app_review,
                "status": "ready" if adapter else info.status,
                "setup_notes": info.setup_notes,
            })
        return result

    def get_publisher(self, platform: str) -> SocialPublisher:
        adapter = self._adapters.get((platform or "").strip().lower())
        if adapter is None:
            raise ConnectorNotConfigured(
                f"Publishing to {platform!r} is not enabled. Connect and verify an approved platform adapter first."
            )
        return adapter
