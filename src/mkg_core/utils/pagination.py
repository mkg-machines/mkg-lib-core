"""Cursor-based Pagination für die MKG Platform.

Implementiert Cursor-based Pagination gemäß den MKG API Guidelines.
Optimiert für DynamoDB LastEvaluatedKey/ExclusiveStartKey.

Example:
    >>> from mkg_core.utils.pagination import PaginationRequest, encode_cursor
    >>> request = PaginationRequest(cursor=None, limit=20)
    >>> cursor = encode_cursor({"PK": "TENANT#123", "SK": "ENTITY#456"})
"""

from __future__ import annotations

import base64
import json
from typing import Any

from pydantic import BaseModel, Field, field_validator

# Konstanten
DEFAULT_LIMIT = 20
MAX_LIMIT = 100
MIN_LIMIT = 1


class PaginationRequest(BaseModel):
    """Request-Parameter für Pagination.

    Attributes:
        cursor: Opaker Cursor für die nächste Seite (None für erste Seite).
        limit: Anzahl der Ergebnisse pro Seite (Default: 20, Max: 100).
    """

    cursor: str | None = Field(
        default=None,
        description="Opaker Cursor für die nächste Seite",
    )
    limit: int = Field(
        default=DEFAULT_LIMIT,
        ge=MIN_LIMIT,
        le=MAX_LIMIT,
        description="Anzahl der Ergebnisse pro Seite (max. 100)",
    )

    @field_validator("limit", mode="before")
    @classmethod
    def clamp_limit(cls, v: Any) -> int:
        """Begrenzt limit auf erlaubten Bereich."""
        if v is None:
            return DEFAULT_LIMIT
        if isinstance(v, str):
            v = int(v)
        return int(max(MIN_LIMIT, min(MAX_LIMIT, int(v))))

    def to_dynamodb_kwargs(self) -> dict[str, Any]:
        """Konvertiert zu DynamoDB Query/Scan kwargs.

        Returns:
            Dictionary mit Limit und optional ExclusiveStartKey.

        Example:
            >>> req = PaginationRequest(cursor="abc123", limit=20)
            >>> kwargs = req.to_dynamodb_kwargs()
            >>> # {'Limit': 20, 'ExclusiveStartKey': {...}}
        """
        kwargs: dict[str, Any] = {"Limit": self.limit}

        if self.cursor:
            exclusive_start_key = decode_cursor(self.cursor)
            if exclusive_start_key:
                kwargs["ExclusiveStartKey"] = exclusive_start_key

        return kwargs


class PaginationResponse(BaseModel):
    """Response-Format für Pagination.

    Attributes:
        cursor: Cursor für die nächste Seite (None wenn keine weiteren).
        has_more: True wenn weitere Seiten existieren.
        total_count: Gesamtanzahl der Ressourcen (optional, kann teuer sein).
    """

    cursor: str | None = Field(
        default=None,
        description="Cursor für nächste Seite, null wenn keine weiteren",
    )
    has_more: bool = Field(
        default=False,
        description="True wenn weitere Seiten existieren",
    )
    total_count: int | None = Field(
        default=None,
        description="Gesamtanzahl der Ressourcen (optional)",
    )

    model_config = {"extra": "forbid"}


class PaginatedResult[T](BaseModel):
    """Container für paginierte Ergebnisse.

    Type Parameter:
        T: Der Typ der Items in der Liste.

    Attributes:
        items: Liste der Ergebnisse.
        pagination: Pagination-Metadaten.
    """

    items: list[T]
    pagination: PaginationResponse

    model_config = {"extra": "forbid"}


def encode_cursor(last_evaluated_key: dict[str, Any] | None) -> str | None:
    """Encodiert DynamoDB LastEvaluatedKey zu einem opaken Cursor.

    Args:
        last_evaluated_key: Das LastEvaluatedKey von DynamoDB.

    Returns:
        Base64-encodierter Cursor-String oder None.

    Example:
        >>> key = {"PK": {"S": "TENANT#123"}, "SK": {"S": "ENTITY#456"}}
        >>> cursor = encode_cursor(key)
        >>> cursor  # 'eyJQSyI6IHsiUyI6ICJURU...'
    """
    if not last_evaluated_key:
        return None

    try:
        json_bytes = json.dumps(last_evaluated_key, separators=(",", ":")).encode(
            "utf-8"
        )
        return base64.urlsafe_b64encode(json_bytes).decode("ascii")
    except (TypeError, ValueError):
        return None


def decode_cursor(cursor: str | None) -> dict[str, Any] | None:
    """Decodiert einen Cursor zu DynamoDB ExclusiveStartKey.

    Args:
        cursor: Der Base64-encodierte Cursor-String.

    Returns:
        Das decodierte ExclusiveStartKey Dictionary oder None.

    Example:
        >>> cursor = "eyJQSyI6IHsiUyI6ICJURU5BTlQjMTIzIn19"
        >>> key = decode_cursor(cursor)
    """
    if not cursor:
        return None

    try:
        # URL-safe Base64 decodieren
        json_bytes = base64.urlsafe_b64decode(cursor.encode("ascii"))
        result: dict[str, Any] = json.loads(json_bytes.decode("utf-8"))
        return result
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def create_pagination_response(
    last_evaluated_key: dict[str, Any] | None,
    total_count: int | None = None,
) -> PaginationResponse:
    """Erstellt eine PaginationResponse aus DynamoDB-Ergebnis.

    Args:
        last_evaluated_key: Das LastEvaluatedKey von DynamoDB Query/Scan.
        total_count: Optionale Gesamtanzahl.

    Returns:
        Eine PaginationResponse mit cursor, has_more und total_count.

    Example:
        >>> response = create_pagination_response(
        ...     last_evaluated_key={"PK": {"S": "TENANT#123"}},
        ...     total_count=142
        ... )
        >>> response.has_more
        True
    """
    cursor = encode_cursor(last_evaluated_key)
    has_more = cursor is not None

    return PaginationResponse(
        cursor=cursor,
        has_more=has_more,
        total_count=total_count,
    )


def create_paginated_result[T](
    items: list[T],
    last_evaluated_key: dict[str, Any] | None,
    total_count: int | None = None,
) -> PaginatedResult[T]:
    """Erstellt ein PaginatedResult aus Items und DynamoDB-Metadaten.

    Type Parameter:
        T: Der Typ der Items.

    Args:
        items: Die Ergebnis-Items.
        last_evaluated_key: Das LastEvaluatedKey von DynamoDB.
        total_count: Optionale Gesamtanzahl.

    Returns:
        Ein PaginatedResult mit items und pagination.

    Example:
        >>> result = create_paginated_result(
        ...     items=[{"id": "1"}, {"id": "2"}],
        ...     last_evaluated_key={"PK": {"S": "..."}},
        ...     total_count=100
        ... )
        >>> len(result.items)
        2
        >>> result.pagination.has_more
        True
    """
    pagination = create_pagination_response(last_evaluated_key, total_count)
    return PaginatedResult(items=items, pagination=pagination)


def paginate_list[T](
    items: list[T],
    request: PaginationRequest,
    *,
    cursor_key: str = "id",
) -> PaginatedResult[T]:
    """Paginiert eine In-Memory-Liste (für Tests oder kleine Datensätze).

    Type Parameter:
        T: Der Typ der Items (muss cursor_key als Attribut haben).

    Args:
        items: Die vollständige Liste.
        request: Die Pagination-Parameter.
        cursor_key: Das Attribut für den Cursor (Default: "id").

    Returns:
        Ein PaginatedResult mit der aktuellen Seite.

    Example:
        >>> items = [{"id": "1"}, {"id": "2"}, {"id": "3"}]
        >>> result = paginate_list(items, PaginationRequest(limit=2))
        >>> len(result.items)
        2
        >>> result.pagination.has_more
        True
    """
    total_count = len(items)

    # Start-Index finden basierend auf Cursor
    start_idx = 0
    if request.cursor:
        cursor_value = decode_cursor(request.cursor)
        if cursor_value and cursor_key in cursor_value:
            # Finde Index nach dem Cursor-Element
            for i, item in enumerate(items):
                if isinstance(item, dict):
                    item_value = item.get(cursor_key)
                else:
                    item_value = getattr(item, cursor_key, None)
                if item_value == cursor_value[cursor_key]:
                    start_idx = i + 1
                    break

    # Slice erstellen
    end_idx = start_idx + request.limit
    page_items = items[start_idx:end_idx]

    # Cursor für nächste Seite
    has_more = end_idx < total_count
    next_cursor = None
    if has_more and page_items:
        last_item = page_items[-1]
        last_value = (
            last_item.get(cursor_key)
            if isinstance(last_item, dict)
            else getattr(last_item, cursor_key, None)
        )
        if last_value:
            next_cursor = encode_cursor({cursor_key: last_value})

    return PaginatedResult(
        items=page_items,
        pagination=PaginationResponse(
            cursor=next_cursor,
            has_more=has_more,
            total_count=total_count,
        ),
    )
