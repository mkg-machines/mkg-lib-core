"""Validierungs-Utilities für die MKG Platform.

Stellt Validierungsfunktionen und Pydantic Annotated Types bereit
für konsistente Eingabevalidierung.

Example:
    >>> from mkg_core.utils.validation import validate_uuid, TenantId
    >>> validate_uuid("550e8400-e29b-41d4-a716-446655440000")
    True
"""

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, Field, StringConstraints

# UUID Pattern
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# ISO 8601 Timestamp Pattern (vereinfacht)
ISO_TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


def validate_uuid(value: str) -> bool:
    """Validiert ob ein String ein gültiges UUID-Format hat.

    Args:
        value: Der zu validierende String.

    Returns:
        True wenn gültig, False wenn ungültig.

    Example:
        >>> validate_uuid("550e8400-e29b-41d4-a716-446655440000")
        True
        >>> validate_uuid("invalid")
        False
    """
    if not isinstance(value, str):
        return False
    return bool(UUID_PATTERN.match(value))


def validate_tenant_id(value: str) -> bool:
    """Validiert ein tenant_id Format.

    Tenant-IDs haben das Format: tnt-{uuid} oder sind eine reine UUID.

    Args:
        value: Der zu validierende Tenant-ID String.

    Returns:
        True wenn gültig, False wenn ungültig.

    Example:
        >>> validate_tenant_id("tnt-550e8400-e29b-41d4-a716-446655440000")
        True
        >>> validate_tenant_id("550e8400-e29b-41d4-a716-446655440000")
        True
    """
    if not isinstance(value, str):
        return False

    # Mit Prefix
    if value.startswith("tnt-"):
        return validate_uuid(value[4:])

    # Ohne Prefix (reine UUID)
    return validate_uuid(value)


def validate_entity_id(value: str) -> bool:
    """Validiert ein entity_id Format.

    Entity-IDs haben das Format: ent-{uuid} oder sind eine reine UUID.

    Args:
        value: Der zu validierende Entity-ID String.

    Returns:
        True wenn gültig, False wenn ungültig.

    Example:
        >>> validate_entity_id("ent-550e8400-e29b-41d4-a716-446655440000")
        True
    """
    if not isinstance(value, str):
        return False

    # Mit Prefix
    if value.startswith("ent-"):
        return validate_uuid(value[4:])

    # Ohne Prefix (reine UUID)
    return validate_uuid(value)


def validate_iso_timestamp(value: str) -> bool:
    """Validiert ein ISO 8601 Timestamp Format.

    Args:
        value: Der zu validierende Timestamp-String.

    Returns:
        True wenn gültig, False wenn ungültig.

    Example:
        >>> validate_iso_timestamp("2024-01-15T10:30:00Z")
        True
        >>> validate_iso_timestamp("2024-01-15 10:30:00")
        False
    """
    if not isinstance(value, str):
        return False

    if not ISO_TIMESTAMP_PATTERN.match(value):
        return False

    # Versuche zu parsen um sicherzustellen dass es ein echtes Datum ist
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def sanitize_string(
    value: str,
    *,
    max_length: int = 10000,
    strip_html: bool = True,
    strip_whitespace: bool = True,
) -> str:
    """Bereinigt einen String-Input.

    Args:
        value: Der zu bereinigende String.
        max_length: Maximale Länge (Default: 10000).
        strip_html: HTML-Entities escapen (Default: True).
        strip_whitespace: Whitespace am Anfang/Ende entfernen (Default: True).

    Returns:
        Der bereinigte String.

    Example:
        >>> sanitize_string("  <script>alert('xss')</script>  ")
        "&lt;script&gt;alert('xss')&lt;/script&gt;"
    """
    if not isinstance(value, str):
        return str(value)

    result = value

    if strip_whitespace:
        result = result.strip()

    if strip_html:
        result = html.escape(result)

    if len(result) > max_length:
        result = result[:max_length]

    return result


# --- Pydantic Validators ---


def _validate_uuid_str(value: str) -> str:
    """Pydantic Validator für UUID-Strings."""
    if not validate_uuid(value):
        msg = f"Invalid UUID format: {value}"
        raise ValueError(msg)
    return value


def _validate_tenant_id_str(value: str) -> str:
    """Pydantic Validator für Tenant-IDs."""
    if not validate_tenant_id(value):
        msg = f"Invalid tenant_id format: {value}"
        raise ValueError(msg)
    return value


def _validate_entity_id_str(value: str) -> str:
    """Pydantic Validator für Entity-IDs."""
    if not validate_entity_id(value):
        msg = f"Invalid entity_id format: {value}"
        raise ValueError(msg)
    return value


def _validate_iso_timestamp_str(value: str) -> str:
    """Pydantic Validator für ISO Timestamps."""
    if not validate_iso_timestamp(value):
        msg = f"Invalid ISO 8601 timestamp: {value}"
        raise ValueError(msg)
    return value


# --- Pydantic Annotated Types ---

UUIDString = Annotated[
    str,
    StringConstraints(min_length=36, max_length=36),
    AfterValidator(_validate_uuid_str),
    Field(description="UUID v4 string"),
]
"""Annotated Type für UUID-Strings."""

TenantId = Annotated[
    str,
    StringConstraints(min_length=36, max_length=40),
    AfterValidator(_validate_tenant_id_str),
    Field(description="Tenant ID (UUID or tnt-{UUID})"),
]
"""Annotated Type für Tenant-IDs."""

EntityId = Annotated[
    str,
    StringConstraints(min_length=36, max_length=40),
    AfterValidator(_validate_entity_id_str),
    Field(description="Entity ID (UUID or ent-{UUID})"),
]
"""Annotated Type für Entity-IDs."""

ISOTimestamp = Annotated[
    str,
    StringConstraints(min_length=20, max_length=30),
    AfterValidator(_validate_iso_timestamp_str),
    Field(description="ISO 8601 timestamp string"),
]
"""Annotated Type für ISO 8601 Timestamps."""

NonEmptyString = Annotated[
    str,
    StringConstraints(min_length=1, strip_whitespace=True),
    Field(description="Non-empty string"),
]
"""Annotated Type für nicht-leere Strings."""


def parse_uuid(value: str) -> UUID:
    """Parst einen String zu einem UUID-Objekt.

    Args:
        value: Der zu parsende UUID-String.

    Returns:
        Das geparste UUID-Objekt.

    Raises:
        ValueError: Wenn der String kein gültiges UUID-Format hat.

    Example:
        >>> parse_uuid("550e8400-e29b-41d4-a716-446655440000")
        UUID('550e8400-e29b-41d4-a716-446655440000')
    """
    if not validate_uuid(value):
        msg = f"Invalid UUID format: {value}"
        raise ValueError(msg)
    return UUID(value)


def generate_id(prefix: str = "") -> str:
    """Generiert eine neue UUID mit optionalem Prefix.

    Args:
        prefix: Optionaler Prefix (z.B. 'ent-', 'tnt-').

    Returns:
        Die generierte ID.

    Example:
        >>> id = generate_id("ent-")
        >>> id.startswith("ent-")
        True
    """
    import uuid

    return f"{prefix}{uuid.uuid4()}"


def extract_uuid_from_prefixed_id(value: str) -> str:
    """Extrahiert die UUID aus einer ID mit Prefix.

    Args:
        value: Die ID (z.B. 'ent-550e8400-...').

    Returns:
        Die extrahierte UUID ohne Prefix.

    Example:
        >>> extract_uuid_from_prefixed_id("ent-550e8400-e29b-41d4-a716-446655440000")
        '550e8400-e29b-41d4-a716-446655440000'
    """
    # Bekannte Prefixes
    prefixes = ("ent-", "tnt-", "usr-", "sch-", "rel-", "evt-", "req-")

    for prefix in prefixes:
        if value.startswith(prefix):
            return value[len(prefix) :]

    # Kein bekannter Prefix, gib Originalwert zurück
    return value
