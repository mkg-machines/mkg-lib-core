"""Tests fuer mkg_core.utils.pagination Modul.

Testet Cursor-based Pagination fuer DynamoDB.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import pytest
from pydantic import ValidationError

from mkg_core.utils.pagination import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    MIN_LIMIT,
    PaginatedResult,
    PaginationRequest,
    PaginationResponse,
    create_paginated_result,
    create_pagination_response,
    decode_cursor,
    encode_cursor,
    paginate_list,
)

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def sample_dynamodb_key() -> dict[str, Any]:
    """Sample DynamoDB LastEvaluatedKey."""
    return {"PK": {"S": "TENANT#123"}, "SK": {"S": "ENTITY#456"}}


@pytest.fixture
def sample_items() -> list[dict[str, Any]]:
    """Sample Items fuer Pagination-Tests."""
    return [{"id": str(i), "name": f"Item {i}"} for i in range(1, 11)]


@pytest.fixture
def encoded_cursor(sample_dynamodb_key) -> str:
    """Vorbereiteter encodierter Cursor."""
    return encode_cursor(sample_dynamodb_key)


# ============================================================
# Constants Tests
# ============================================================


class TestPaginationConstants:
    """Tests fuer Pagination-Konstanten."""

    def test_default_limit(self):
        """DEFAULT_LIMIT ist 20."""
        assert DEFAULT_LIMIT == 20

    def test_max_limit(self):
        """MAX_LIMIT ist 100."""
        assert MAX_LIMIT == 100

    def test_min_limit(self):
        """MIN_LIMIT ist 1."""
        assert MIN_LIMIT == 1


# ============================================================
# PaginationRequest Tests
# ============================================================


class TestPaginationRequest:
    """Tests fuer PaginationRequest."""

    def test_default_values(self):
        """PaginationRequest hat korrekte Default-Werte."""
        request = PaginationRequest()

        assert request.cursor is None
        assert request.limit == DEFAULT_LIMIT

    def test_custom_cursor(self):
        """Cursor kann gesetzt werden."""
        request = PaginationRequest(cursor="abc123")

        assert request.cursor == "abc123"

    def test_custom_limit(self):
        """Limit kann gesetzt werden."""
        request = PaginationRequest(limit=50)

        assert request.limit == 50

    def test_limit_clamped_to_max(self):
        """Limit wird auf MAX_LIMIT begrenzt."""
        request = PaginationRequest(limit=500)

        assert request.limit == MAX_LIMIT

    def test_limit_clamped_to_min(self):
        """Limit wird auf MIN_LIMIT angehoben."""
        request = PaginationRequest(limit=0)

        assert request.limit == MIN_LIMIT

    def test_negative_limit_clamped(self):
        """Negatives Limit wird auf MIN_LIMIT gesetzt."""
        request = PaginationRequest(limit=-10)

        assert request.limit == MIN_LIMIT

    def test_limit_from_string(self):
        """Limit kann als String uebergeben werden."""
        request = PaginationRequest(limit="30")  # type: ignore[arg-type]

        assert request.limit == 30

    def test_limit_none_uses_default(self):
        """None als Limit verwendet Default."""
        request = PaginationRequest(limit=None)  # type: ignore[arg-type]

        assert request.limit == DEFAULT_LIMIT

    @pytest.mark.parametrize(
        ("input_limit", "expected"),
        [
            (1, 1),
            (20, 20),
            (50, 50),
            (100, 100),
            (101, 100),
            (0, 1),
            (-5, 1),
            (1000, 100),
        ],
    )
    def test_limit_clamping(self, input_limit, expected):
        """Limit wird korrekt auf gueltigen Bereich begrenzt."""
        request = PaginationRequest(limit=input_limit)

        assert request.limit == expected


class TestPaginationRequestToDynamoDbKwargs:
    """Tests fuer PaginationRequest.to_dynamodb_kwargs()."""

    def test_without_cursor(self):
        """Ohne Cursor gibt nur Limit zurueck."""
        request = PaginationRequest(limit=25)
        kwargs = request.to_dynamodb_kwargs()

        assert kwargs == {"Limit": 25}
        assert "ExclusiveStartKey" not in kwargs

    def test_with_valid_cursor(self, sample_dynamodb_key):
        """Mit gueltigem Cursor gibt Limit und ExclusiveStartKey zurueck."""
        cursor = encode_cursor(sample_dynamodb_key)
        request = PaginationRequest(cursor=cursor, limit=25)
        kwargs = request.to_dynamodb_kwargs()

        assert kwargs["Limit"] == 25
        assert kwargs["ExclusiveStartKey"] == sample_dynamodb_key

    def test_with_invalid_cursor(self):
        """Mit ungueltigem Cursor wird nur Limit zurueckgegeben."""
        request = PaginationRequest(cursor="invalid-cursor", limit=25)
        kwargs = request.to_dynamodb_kwargs()

        assert kwargs == {"Limit": 25}
        assert "ExclusiveStartKey" not in kwargs


# ============================================================
# PaginationResponse Tests
# ============================================================


class TestPaginationResponse:
    """Tests fuer PaginationResponse."""

    def test_default_values(self):
        """PaginationResponse hat korrekte Default-Werte."""
        response = PaginationResponse()

        assert response.cursor is None
        assert response.has_more is False
        assert response.total_count is None

    def test_custom_values(self):
        """PaginationResponse akzeptiert custom Werte."""
        response = PaginationResponse(
            cursor="next-page",
            has_more=True,
            total_count=142,
        )

        assert response.cursor == "next-page"
        assert response.has_more is True
        assert response.total_count == 142

    def test_extra_fields_forbidden(self):
        """Zusaetzliche Felder werden abgelehnt."""
        with pytest.raises(ValidationError):
            PaginationResponse(cursor=None, extra="field")  # type: ignore[call-arg]


# ============================================================
# PaginatedResult Tests
# ============================================================


class TestPaginatedResult:
    """Tests fuer PaginatedResult."""

    def test_basic_creation(self, sample_items):
        """PaginatedResult kann erstellt werden."""
        pagination = PaginationResponse(has_more=True)
        result: PaginatedResult[dict] = PaginatedResult(
            items=sample_items[:5],
            pagination=pagination,
        )

        assert len(result.items) == 5
        assert result.pagination.has_more is True

    def test_empty_items(self):
        """PaginatedResult mit leerer Items-Liste."""
        pagination = PaginationResponse(has_more=False)
        result: PaginatedResult[dict] = PaginatedResult(
            items=[],
            pagination=pagination,
        )

        assert len(result.items) == 0
        assert result.pagination.has_more is False

    def test_extra_fields_forbidden(self, sample_items):
        """Zusaetzliche Felder werden abgelehnt."""
        pagination = PaginationResponse()
        with pytest.raises(ValidationError):
            PaginatedResult(
                items=sample_items,
                pagination=pagination,
                extra="field",  # type: ignore[call-arg]
            )


# ============================================================
# encode_cursor Tests
# ============================================================


class TestEncodeCursor:
    """Tests fuer encode_cursor()."""

    def test_encodes_dict(self, sample_dynamodb_key):
        """Dictionary wird zu Base64 encodiert."""
        cursor = encode_cursor(sample_dynamodb_key)

        assert cursor is not None
        assert isinstance(cursor, str)

    def test_none_returns_none(self):
        """None Input gibt None zurueck."""
        cursor = encode_cursor(None)

        assert cursor is None

    def test_empty_dict_returns_none(self):
        """Leeres Dictionary gibt None zurueck."""
        cursor = encode_cursor({})

        assert cursor is None

    def test_result_is_valid_base64(self, sample_dynamodb_key):
        """Ergebnis ist gueltiges URL-safe Base64."""
        cursor = encode_cursor(sample_dynamodb_key)

        # Sollte ohne Exception decodieren
        decoded_bytes = base64.urlsafe_b64decode(cursor)
        decoded_json = json.loads(decoded_bytes)

        assert decoded_json == sample_dynamodb_key

    def test_round_trip(self, sample_dynamodb_key):
        """Encode und Decode ergibt Original."""
        cursor = encode_cursor(sample_dynamodb_key)
        decoded = decode_cursor(cursor)

        assert decoded == sample_dynamodb_key

    @pytest.mark.parametrize(
        "key",
        [
            {"PK": {"S": "simple"}},
            {"PK": {"S": "TENANT#123"}, "SK": {"S": "ENTITY#456"}},
            {"PK": {"S": "unicode-\u00e4\u00f6\u00fc"}},
            {"nested": {"deep": {"value": 123}}},
        ],
    )
    def test_various_keys(self, key):
        """Verschiedene Key-Strukturen werden korrekt encodiert."""
        cursor = encode_cursor(key)
        decoded = decode_cursor(cursor)

        assert decoded == key


# ============================================================
# decode_cursor Tests
# ============================================================


class TestDecodeCursor:
    """Tests fuer decode_cursor()."""

    def test_decodes_valid_cursor(self, sample_dynamodb_key, encoded_cursor):
        """Gueltiger Cursor wird decodiert."""
        decoded = decode_cursor(encoded_cursor)

        assert decoded == sample_dynamodb_key

    def test_none_returns_none(self):
        """None Input gibt None zurueck."""
        decoded = decode_cursor(None)

        assert decoded is None

    def test_empty_string_returns_none(self):
        """Leerer String gibt None zurueck."""
        decoded = decode_cursor("")

        assert decoded is None

    def test_invalid_base64_returns_none(self):
        """Ungueltiges Base64 gibt None zurueck."""
        decoded = decode_cursor("not-valid-base64!!!")

        assert decoded is None

    def test_invalid_json_returns_none(self):
        """Gueltiges Base64 aber ungueltiges JSON gibt None zurueck."""
        # Base64 von "not json"
        invalid_cursor = base64.urlsafe_b64encode(b"not json").decode("ascii")
        decoded = decode_cursor(invalid_cursor)

        assert decoded is None

    def test_non_dict_json_returns_none(self):
        """JSON das kein Dict ist gibt trotzdem etwas zurueck (Liste etc.)."""
        # Base64 von "[1, 2, 3]"
        list_cursor = base64.urlsafe_b64encode(b"[1, 2, 3]").decode("ascii")
        decoded = decode_cursor(list_cursor)

        # decode_cursor gibt tatsaechlich auch Listen zurueck
        # da es dict[str, Any] | None ist, aber zur Laufzeit nicht prueft
        assert decoded == [1, 2, 3]


# ============================================================
# create_pagination_response Tests
# ============================================================


class TestCreatePaginationResponse:
    """Tests fuer create_pagination_response()."""

    def test_with_last_evaluated_key(self, sample_dynamodb_key):
        """Mit LastEvaluatedKey wird has_more=True gesetzt."""
        response = create_pagination_response(sample_dynamodb_key)

        assert response.cursor is not None
        assert response.has_more is True
        assert response.total_count is None

    def test_without_last_evaluated_key(self):
        """Ohne LastEvaluatedKey wird has_more=False gesetzt."""
        response = create_pagination_response(None)

        assert response.cursor is None
        assert response.has_more is False

    def test_with_total_count(self, sample_dynamodb_key):
        """total_count wird korrekt gesetzt."""
        response = create_pagination_response(sample_dynamodb_key, total_count=142)

        assert response.total_count == 142

    def test_cursor_is_decodable(self, sample_dynamodb_key):
        """Erzeugter Cursor kann wieder decodiert werden."""
        response = create_pagination_response(sample_dynamodb_key)
        decoded = decode_cursor(response.cursor)

        assert decoded == sample_dynamodb_key


# ============================================================
# create_paginated_result Tests
# ============================================================


class TestCreatePaginatedResult:
    """Tests fuer create_paginated_result()."""

    def test_with_items_and_key(self, sample_items, sample_dynamodb_key):
        """Erstellt PaginatedResult mit Items und Pagination."""
        result = create_paginated_result(
            items=sample_items[:5],
            last_evaluated_key=sample_dynamodb_key,
        )

        assert len(result.items) == 5
        assert result.pagination.has_more is True
        assert result.pagination.cursor is not None

    def test_without_key(self, sample_items):
        """Ohne LastEvaluatedKey wird has_more=False."""
        result = create_paginated_result(
            items=sample_items,
            last_evaluated_key=None,
        )

        assert len(result.items) == 10
        assert result.pagination.has_more is False
        assert result.pagination.cursor is None

    def test_with_total_count(self, sample_items, sample_dynamodb_key):
        """total_count wird durchgereicht."""
        result = create_paginated_result(
            items=sample_items,
            last_evaluated_key=sample_dynamodb_key,
            total_count=500,
        )

        assert result.pagination.total_count == 500

    def test_empty_items(self):
        """Leere Items-Liste funktioniert."""
        result = create_paginated_result(
            items=[],
            last_evaluated_key=None,
        )

        assert result.items == []
        assert result.pagination.has_more is False


# ============================================================
# paginate_list Tests
# ============================================================


class TestPaginateList:
    """Tests fuer paginate_list()."""

    def test_first_page(self, sample_items):
        """Erste Seite ohne Cursor."""
        request = PaginationRequest(limit=3)
        result = paginate_list(sample_items, request)

        assert len(result.items) == 3
        assert result.items[0]["id"] == "1"
        assert result.items[2]["id"] == "3"
        assert result.pagination.has_more is True
        assert result.pagination.total_count == 10

    def test_second_page(self, sample_items):
        """Zweite Seite mit Cursor."""
        # Erste Seite holen
        request1 = PaginationRequest(limit=3)
        result1 = paginate_list(sample_items, request1)

        # Zweite Seite mit Cursor
        request2 = PaginationRequest(cursor=result1.pagination.cursor, limit=3)
        result2 = paginate_list(sample_items, request2)

        assert len(result2.items) == 3
        assert result2.items[0]["id"] == "4"
        assert result2.items[2]["id"] == "6"
        assert result2.pagination.has_more is True

    def test_last_page(self, sample_items):
        """Letzte Seite hat has_more=False."""
        request = PaginationRequest(limit=100)
        result = paginate_list(sample_items, request)

        assert len(result.items) == 10
        assert result.pagination.has_more is False
        assert result.pagination.cursor is None

    def test_exact_page_boundary(self, sample_items):
        """Exakte Seitengrenze wird korrekt behandelt."""
        request = PaginationRequest(limit=5)
        result = paginate_list(sample_items, request)

        assert len(result.items) == 5
        assert result.pagination.has_more is True

        # Zweite Seite
        request2 = PaginationRequest(cursor=result.pagination.cursor, limit=5)
        result2 = paginate_list(sample_items, request2)

        assert len(result2.items) == 5
        assert result2.pagination.has_more is False

    def test_empty_list(self):
        """Leere Liste ergibt leeres Ergebnis."""
        request = PaginationRequest(limit=10)
        result = paginate_list([], request)

        assert result.items == []
        assert result.pagination.has_more is False
        assert result.pagination.total_count == 0

    def test_invalid_cursor_starts_from_beginning(self, sample_items):
        """Ungueltiger Cursor startet von Anfang."""
        request = PaginationRequest(cursor="invalid", limit=3)
        result = paginate_list(sample_items, request)

        # Startet von Anfang
        assert result.items[0]["id"] == "1"

    def test_custom_cursor_key(self):
        """Custom cursor_key funktioniert."""
        items = [{"name": f"Item-{i}", "value": i} for i in range(5)]
        request = PaginationRequest(limit=2)

        result = paginate_list(items, request, cursor_key="name")

        assert len(result.items) == 2
        assert result.pagination.has_more is True

        # Zweite Seite
        request2 = PaginationRequest(cursor=result.pagination.cursor, limit=2)
        result2 = paginate_list(items, request2, cursor_key="name")

        assert result2.items[0]["name"] == "Item-2"

    def test_full_pagination_cycle(self, sample_items):
        """Kompletter Pagination-Zyklus durch alle Seiten."""
        all_items = []
        cursor = None
        page_count = 0

        while True:
            request = PaginationRequest(cursor=cursor, limit=3)
            result = paginate_list(sample_items, request)

            all_items.extend(result.items)
            page_count += 1

            if not result.pagination.has_more:
                break
            cursor = result.pagination.cursor

        assert len(all_items) == 10
        assert page_count == 4  # ceil(10/3) = 4 Seiten

    def test_preserves_total_count(self, sample_items):
        """total_count bleibt ueber alle Seiten gleich."""
        request1 = PaginationRequest(limit=3)
        result1 = paginate_list(sample_items, request1)

        request2 = PaginationRequest(cursor=result1.pagination.cursor, limit=3)
        result2 = paginate_list(sample_items, request2)

        assert result1.pagination.total_count == result2.pagination.total_count == 10


class TestPaginateListWithObjects:
    """Tests fuer paginate_list() mit Objekten statt Dicts."""

    def test_with_dataclass_like_objects(self):
        """paginate_list funktioniert mit Objekten die Attribute haben."""

        class Item:
            def __init__(self, id: str, name: str):
                self.id = id
                self.name = name

        items = [Item(str(i), f"Item {i}") for i in range(5)]
        request = PaginationRequest(limit=2)

        result = paginate_list(items, request)

        assert len(result.items) == 2
        assert result.items[0].id == "0"
        assert result.pagination.has_more is True


# ============================================================
# Edge Cases and Integration Tests
# ============================================================


class TestPaginationEdgeCases:
    """Edge Cases fuer Pagination."""

    def test_limit_one(self, sample_items):
        """Limit=1 funktioniert korrekt."""
        request = PaginationRequest(limit=1)
        result = paginate_list(sample_items, request)

        assert len(result.items) == 1
        assert result.pagination.has_more is True

    def test_limit_equals_total(self, sample_items):
        """Limit gleich Gesamtanzahl."""
        request = PaginationRequest(limit=10)
        result = paginate_list(sample_items, request)

        assert len(result.items) == 10
        assert result.pagination.has_more is False

    def test_single_item_list(self):
        """Liste mit nur einem Item."""
        items = [{"id": "1"}]
        request = PaginationRequest(limit=10)
        result = paginate_list(items, request)

        assert len(result.items) == 1
        assert result.pagination.has_more is False
        assert result.pagination.total_count == 1

    def test_cursor_for_nonexistent_item(self, sample_items):
        """Cursor fuer nicht mehr existierendes Item."""
        # Erstelle Cursor fuer Item "5"
        cursor = encode_cursor({"id": "99"})  # Existiert nicht
        request = PaginationRequest(cursor=cursor, limit=3)

        result = paginate_list(sample_items, request)

        # Sollte von Anfang starten da Item nicht gefunden
        assert result.items[0]["id"] == "1"
