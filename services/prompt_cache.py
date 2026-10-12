"""Small, provider-neutral helpers for provider-managed prompt caching.

This module does not store prompts, responses, embeddings, or KV state. It only
creates a non-reversible per-user cache key for providers that support one.
"""
import hashlib
import hmac
import json

import config


def make_prompt_cache_key(user_id, model_id, prefix_messages=None, conversation_id=None):
    """Return a stable opaque cache-bucket key, or None when disabled."""
    if not config.PROMPT_CACHING_ENABLED:
        return None

    prefix = json.dumps(
        prefix_messages or [],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    material = f"smart-bethg:v1:{user_id}:{conversation_id or 'default'}:{model_id}:{prefix}".encode("utf-8")
    secret = config.SECRET_KEY.encode("utf-8")
    return hmac.new(secret, material, hashlib.sha256).hexdigest()


def prefix_character_count(messages, message_count):
    """Count characters in a candidate cache prefix without modifying it."""
    if not messages or message_count <= 0:
        return 0
    return sum(len(str(message.get("content", ""))) for message in messages[:message_count])
