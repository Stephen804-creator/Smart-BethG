"""Safe, provider-neutral social publishing connector contract.

Concrete platform adapters must implement OAuth/token refresh, scope validation,
provider-specific media rules, idempotency/reconciliation, and publish(). Tokens
must be stored in a secret manager, never in this database or source code.
"""
from dataclasses import dataclass
from typing import Any, Protocol


class ConnectorNotConfigured(RuntimeError):
    """No production-ready publishing adapter is configured for this platform."""


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

    def publish(self, *, account_ref: str, content: dict[str, Any], idempotency_key: str) -> dict[str, str]:
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
        self._adapters = dict(adapters or {})

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
