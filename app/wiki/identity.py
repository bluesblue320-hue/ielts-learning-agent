"""Frozen deterministic identity normalization for Wiki lookup."""

from __future__ import annotations

import unicodedata

from app.wiki.errors import WikiLookupInvalidError


MAX_WIKI_IDENTITY_CODEPOINTS = 120


def normalize_wiki_identity(value: str) -> str:
    """Apply the exact NFKC/whitespace/casefold Wiki v1 normalizer."""
    if not isinstance(value, str) or len(value) > MAX_WIKI_IDENTITY_CODEPOINTS:
        raise WikiLookupInvalidError("wiki identity is invalid")
    normalized = unicodedata.normalize("NFKC", value)
    normalized = " ".join(normalized.split()).casefold()
    if not normalized:
        raise WikiLookupInvalidError("wiki identity is invalid")
    return normalized
