"""Explicit fail-closed Wiki domain errors."""


class WikiError(Exception):
    """Base error for deterministic Wiki behavior."""


class WikiIntegrityError(WikiError):
    """The canonical Wiki snapshot violates its frozen contract."""


class WikiLookupInvalidError(WikiError):
    """A lookup identity is syntactically invalid after normalization."""


class WikiLookupAmbiguousError(WikiError):
    """A lookup identity resolves to more than one canonical page."""


class WikiPageNotFoundError(WikiError):
    """No canonical page matches the requested identity."""


class WikiUnavailableError(WikiError):
    """The Wiki cannot safely serve an invalid internal snapshot."""
