"""Tests fuer mkg_core.utils.validation Modul.

Testet Validierungsfunktionen und Pydantic Annotated Types.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

from mkg_core.utils.validation import (
    EntityId,
    ISOTimestamp,
    NonEmptyString,
    TenantId,
    UUIDString,
    extract_uuid_from_prefixed_id,
    generate_id,
    parse_uuid,
    sanitize_string,
    validate_entity_id,
    validate_iso_timestamp,
    validate_tenant_id,
    validate_uuid,
)

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def valid_uuid() -> str:
    """Gueltige UUID fuer Tests."""
    return "550e8400-e29b-41d4-a716-446655440000"


@pytest.fixture
def valid_uuid_uppercase() -> str:
    """Gueltige UUID in Grossbuchstaben."""
    return "550E8400-E29B-41D4-A716-446655440000"


# ============================================================
# validate_uuid Tests
# ============================================================


class TestValidateUuid:
    """Tests fuer validate_uuid()."""

    def test_valid_uuid(self, valid_uuid):
        """Gueltige UUID wird akzeptiert."""
        assert validate_uuid(valid_uuid) is True

    def test_valid_uuid_uppercase(self, valid_uuid_uppercase):
        """Grossbuchstaben-UUID wird akzeptiert (case-insensitive)."""
        assert validate_uuid(valid_uuid_uppercase) is True

    def test_invalid_uuid_wrong_format(self):
        """Falsches Format wird abgelehnt."""
        assert validate_uuid("not-a-uuid") is False

    def test_invalid_uuid_too_short(self):
        """Zu kurze UUID wird abgelehnt."""
        assert validate_uuid("550e8400-e29b-41d4-a716") is False

    def test_invalid_uuid_too_long(self, valid_uuid):
        """Zu lange UUID wird abgelehnt."""
        assert validate_uuid(valid_uuid + "extra") is False

    def test_invalid_uuid_wrong_characters(self):
        """UUID mit ungueltigen Zeichen wird abgelehnt."""
        assert validate_uuid("gggggggg-gggg-gggg-gggg-gggggggggggg") is False

    def test_invalid_uuid_missing_dashes(self):
        """UUID ohne Bindestriche wird abgelehnt."""
        assert validate_uuid("550e8400e29b41d4a716446655440000") is False

    def test_empty_string(self):
        """Leerer String wird abgelehnt."""
        assert validate_uuid("") is False

    def test_none_input(self):
        """None wird abgelehnt."""
        assert validate_uuid(None) is False  # type: ignore[arg-type]

    def test_non_string_input(self):
        """Nicht-String Input wird abgelehnt."""
        assert validate_uuid(12345) is False  # type: ignore[arg-type]
        assert validate_uuid(["uuid"]) is False  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "uuid_str",
        [
            "00000000-0000-0000-0000-000000000000",
            "ffffffff-ffff-ffff-ffff-ffffffffffff",
            "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF",
            "12345678-1234-1234-1234-123456789abc",
        ],
    )
    def test_various_valid_uuids(self, uuid_str):
        """Verschiedene gueltige UUID-Formate werden akzeptiert."""
        assert validate_uuid(uuid_str) is True

    @pytest.mark.parametrize(
        "invalid_input",
        [
            "550e8400-e29b-41d4-a716-4466554400001",  # Eine Ziffer zu viel
            "550e8400-e29b-41d4-a716-44665544000",  # Eine Ziffer zu wenig
            "550e8400--e29b-41d4-a716-446655440000",  # Doppelter Bindestrich
            "550e8400-e29b-41d4-a716-446655440000-",  # Trailing dash
            "-550e8400-e29b-41d4-a716-446655440000",  # Leading dash
        ],
    )
    def test_various_invalid_uuids(self, invalid_input):
        """Verschiedene ungueltige UUID-Formate werden abgelehnt."""
        assert validate_uuid(invalid_input) is False


# ============================================================
# validate_tenant_id Tests
# ============================================================


class TestValidateTenantId:
    """Tests fuer validate_tenant_id()."""

    def test_valid_uuid_only(self, valid_uuid):
        """Reine UUID ist gueltig."""
        assert validate_tenant_id(valid_uuid) is True

    def test_valid_with_prefix(self, valid_uuid):
        """UUID mit tnt- Prefix ist gueltig."""
        assert validate_tenant_id(f"tnt-{valid_uuid}") is True

    def test_invalid_wrong_prefix(self, valid_uuid):
        """Falscher Prefix wird abgelehnt."""
        assert validate_tenant_id(f"xyz-{valid_uuid}") is False

    def test_invalid_uuid_with_prefix(self):
        """Ungueltiger UUID-Teil wird abgelehnt."""
        assert validate_tenant_id("tnt-invalid") is False

    def test_prefix_only(self):
        """Nur Prefix ohne UUID wird abgelehnt."""
        assert validate_tenant_id("tnt-") is False

    def test_empty_string(self):
        """Leerer String wird abgelehnt."""
        assert validate_tenant_id("") is False

    def test_none_input(self):
        """None wird abgelehnt."""
        assert validate_tenant_id(None) is False  # type: ignore[arg-type]

    def test_non_string_input(self):
        """Nicht-String Input wird abgelehnt."""
        assert validate_tenant_id(12345) is False  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        ("tenant_id", "expected"),
        [
            ("550e8400-e29b-41d4-a716-446655440000", True),
            ("tnt-550e8400-e29b-41d4-a716-446655440000", True),
            ("TNT-550e8400-e29b-41d4-a716-446655440000", False),  # Case-sensitive
            ("tnt-invalid-uuid", False),
            ("invalid", False),
        ],
    )
    def test_various_tenant_ids(self, tenant_id, expected):
        """Verschiedene Tenant-ID Formate werden korrekt validiert."""
        assert validate_tenant_id(tenant_id) is expected


# ============================================================
# validate_entity_id Tests
# ============================================================


class TestValidateEntityId:
    """Tests fuer validate_entity_id()."""

    def test_valid_uuid_only(self, valid_uuid):
        """Reine UUID ist gueltig."""
        assert validate_entity_id(valid_uuid) is True

    def test_valid_with_prefix(self, valid_uuid):
        """UUID mit ent- Prefix ist gueltig."""
        assert validate_entity_id(f"ent-{valid_uuid}") is True

    def test_invalid_wrong_prefix(self, valid_uuid):
        """Falscher Prefix wird abgelehnt."""
        assert validate_entity_id(f"xyz-{valid_uuid}") is False

    def test_invalid_uuid_with_prefix(self):
        """Ungueltiger UUID-Teil wird abgelehnt."""
        assert validate_entity_id("ent-invalid") is False

    def test_empty_string(self):
        """Leerer String wird abgelehnt."""
        assert validate_entity_id("") is False

    def test_none_input(self):
        """None wird abgelehnt."""
        assert validate_entity_id(None) is False  # type: ignore[arg-type]


# ============================================================
# validate_iso_timestamp Tests
# ============================================================


class TestValidateIsoTimestamp:
    """Tests fuer validate_iso_timestamp()."""

    @pytest.mark.parametrize(
        "timestamp",
        [
            "2024-01-15T10:30:00Z",
            "2024-01-15T10:30:00+00:00",
            "2024-01-15T10:30:00-05:00",
            "2024-01-15T10:30:00.123Z",
            "2024-01-15T10:30:00.123456Z",
            "2024-12-31T23:59:59Z",
        ],
    )
    def test_valid_timestamps(self, timestamp):
        """Gueltige ISO 8601 Timestamps werden akzeptiert."""
        assert validate_iso_timestamp(timestamp) is True

    @pytest.mark.parametrize(
        "timestamp",
        [
            "2024-01-15 10:30:00",  # Leerzeichen statt T
            "2024-01-15",  # Nur Datum
            "10:30:00",  # Nur Zeit
            "2024/01/15T10:30:00Z",  # Falsche Trennzeichen
            "not-a-timestamp",
            "",
            "2024-13-01T10:30:00Z",  # Ungueltiger Monat
            "2024-01-32T10:30:00Z",  # Ungueltiger Tag
        ],
    )
    def test_invalid_timestamps(self, timestamp):
        """Ungueltige Timestamps werden abgelehnt."""
        assert validate_iso_timestamp(timestamp) is False

    def test_none_input(self):
        """None wird abgelehnt."""
        assert validate_iso_timestamp(None) is False  # type: ignore[arg-type]

    def test_non_string_input(self):
        """Nicht-String Input wird abgelehnt."""
        assert validate_iso_timestamp(12345) is False  # type: ignore[arg-type]


# ============================================================
# sanitize_string Tests
# ============================================================


class TestSanitizeString:
    """Tests fuer sanitize_string()."""

    def test_strips_whitespace_by_default(self):
        """Whitespace wird standardmaessig entfernt."""
        result = sanitize_string("  test  ")

        assert result == "test"

    def test_escapes_html_by_default(self):
        """HTML wird standardmaessig escaped."""
        result = sanitize_string("<script>alert('xss')</script>")

        assert "<" not in result
        assert "&lt;script&gt;" in result

    def test_truncates_to_max_length(self):
        """String wird auf max_length gekuerzt."""
        long_string = "a" * 100
        result = sanitize_string(long_string, max_length=50)

        assert len(result) == 50

    def test_default_max_length(self):
        """Default max_length ist 10000."""
        long_string = "a" * 15000
        result = sanitize_string(long_string)

        assert len(result) == 10000

    def test_disable_whitespace_stripping(self):
        """Whitespace-Stripping kann deaktiviert werden."""
        result = sanitize_string("  test  ", strip_whitespace=False)

        assert result == "  test  "

    def test_disable_html_escaping(self):
        """HTML-Escaping kann deaktiviert werden."""
        result = sanitize_string("<b>bold</b>", strip_html=False)

        assert result == "<b>bold</b>"

    def test_non_string_input_converted(self):
        """Nicht-String Input wird zu String konvertiert."""
        result = sanitize_string(12345)  # type: ignore[arg-type]

        assert result == "12345"

    def test_order_of_operations(self):
        """Operationen werden in korrekter Reihenfolge ausgefuehrt."""
        # Strip -> Escape -> Truncate
        result = sanitize_string("  <b>test</b>  ", max_length=15)

        # Erst strip: "<b>test</b>"
        # Dann escape: "&lt;b&gt;test&lt;/b&gt;" (22 chars)
        # Dann truncate: "&lt;b&gt;test&lt;/" (15 chars)
        assert len(result) == 15
        assert result.startswith("&lt;")

    @pytest.mark.parametrize(
        ("input_str", "expected"),
        [
            ("<", "&lt;"),
            (">", "&gt;"),
            ("&", "&amp;"),
            ('"', "&quot;"),
            ("'", "&#x27;"),
        ],
    )
    def test_html_entities_escaped(self, input_str, expected):
        """Alle relevanten HTML-Entities werden escaped."""
        result = sanitize_string(input_str)

        assert result == expected

    def test_empty_string(self):
        """Leerer String bleibt leer."""
        result = sanitize_string("")

        assert result == ""

    def test_only_whitespace(self):
        """Nur-Whitespace wird zu leerem String."""
        result = sanitize_string("   \t\n   ")

        assert result == ""


# ============================================================
# parse_uuid Tests
# ============================================================


class TestParseUuid:
    """Tests fuer parse_uuid()."""

    def test_valid_uuid(self, valid_uuid):
        """Gueltige UUID wird zu UUID-Objekt geparst."""
        result = parse_uuid(valid_uuid)

        assert isinstance(result, UUID)
        assert str(result) == valid_uuid

    def test_invalid_uuid_raises(self):
        """Ungueltige UUID wirft ValueError."""
        with pytest.raises(ValueError, match="Invalid UUID format"):
            parse_uuid("invalid-uuid")

    def test_empty_string_raises(self):
        """Leerer String wirft ValueError."""
        with pytest.raises(ValueError, match="Invalid UUID format"):
            parse_uuid("")


# ============================================================
# generate_id Tests
# ============================================================


class TestGenerateId:
    """Tests fuer generate_id()."""

    def test_without_prefix(self):
        """Generiert UUID ohne Prefix."""
        result = generate_id()

        assert validate_uuid(result) is True

    def test_with_prefix(self):
        """Generiert UUID mit Prefix."""
        result = generate_id("ent-")

        assert result.startswith("ent-")
        assert validate_uuid(result[4:]) is True

    def test_uniqueness(self):
        """Generierte IDs sind einzigartig."""
        ids = {generate_id() for _ in range(100)}

        assert len(ids) == 100

    @pytest.mark.parametrize(
        "prefix",
        ["tnt-", "usr-", "prod-", ""],
    )
    def test_various_prefixes(self, prefix):
        """Verschiedene Prefixe funktionieren."""
        result = generate_id(prefix)

        assert result.startswith(prefix)


# ============================================================
# extract_uuid_from_prefixed_id Tests
# ============================================================


class TestExtractUuidFromPrefixedId:
    """Tests fuer extract_uuid_from_prefixed_id()."""

    def test_with_ent_prefix(self, valid_uuid):
        """Extrahiert UUID aus ent-Prefix."""
        result = extract_uuid_from_prefixed_id(f"ent-{valid_uuid}")

        assert result == valid_uuid

    def test_with_tnt_prefix(self, valid_uuid):
        """Extrahiert UUID aus tnt-Prefix."""
        result = extract_uuid_from_prefixed_id(f"tnt-{valid_uuid}")

        assert result == valid_uuid

    def test_with_usr_prefix(self, valid_uuid):
        """Extrahiert UUID aus usr-Prefix."""
        result = extract_uuid_from_prefixed_id(f"usr-{valid_uuid}")

        assert result == valid_uuid

    def test_without_known_prefix(self, valid_uuid):
        """Gibt Originalwert ohne bekannten Prefix zurueck."""
        result = extract_uuid_from_prefixed_id(valid_uuid)

        assert result == valid_uuid

    def test_unknown_prefix(self, valid_uuid):
        """Unbekannter Prefix wird nicht entfernt."""
        result = extract_uuid_from_prefixed_id(f"xyz-{valid_uuid}")

        assert result == f"xyz-{valid_uuid}"

    @pytest.mark.parametrize(
        "prefix",
        ["ent-", "tnt-", "usr-", "sch-", "rel-", "evt-", "req-"],
    )
    def test_all_known_prefixes(self, prefix, valid_uuid):
        """Alle bekannten Prefixe werden erkannt."""
        result = extract_uuid_from_prefixed_id(f"{prefix}{valid_uuid}")

        assert result == valid_uuid


# ============================================================
# Pydantic Annotated Types Tests
# ============================================================


class TestUUIDStringType:
    """Tests fuer UUIDString Annotated Type."""

    def test_valid_uuid_accepted(self, valid_uuid):
        """Gueltige UUID wird akzeptiert."""

        class Model(BaseModel):
            uuid: UUIDString

        model = Model(uuid=valid_uuid)

        assert model.uuid == valid_uuid

    def test_invalid_uuid_rejected(self):
        """Ungueltige UUID wird abgelehnt."""

        class Model(BaseModel):
            uuid: UUIDString

        with pytest.raises(ValidationError):
            Model(uuid="invalid")

    def test_too_short_rejected(self):
        """Zu kurze UUID wird abgelehnt."""

        class Model(BaseModel):
            uuid: UUIDString

        with pytest.raises(ValidationError):
            Model(uuid="550e8400")


class TestTenantIdType:
    """Tests fuer TenantId Annotated Type."""

    def test_valid_uuid_accepted(self, valid_uuid):
        """Reine UUID wird akzeptiert."""

        class Model(BaseModel):
            tenant: TenantId

        model = Model(tenant=valid_uuid)

        assert model.tenant == valid_uuid

    def test_valid_prefixed_accepted(self, valid_uuid):
        """UUID mit tnt-Prefix wird akzeptiert."""

        class Model(BaseModel):
            tenant: TenantId

        model = Model(tenant=f"tnt-{valid_uuid}")

        assert model.tenant == f"tnt-{valid_uuid}"

    def test_invalid_rejected(self):
        """Ungueltige Tenant-ID wird abgelehnt."""

        class Model(BaseModel):
            tenant: TenantId

        with pytest.raises(ValidationError):
            Model(tenant="invalid")


class TestEntityIdType:
    """Tests fuer EntityId Annotated Type."""

    def test_valid_uuid_accepted(self, valid_uuid):
        """Reine UUID wird akzeptiert."""

        class Model(BaseModel):
            entity: EntityId

        model = Model(entity=valid_uuid)

        assert model.entity == valid_uuid

    def test_valid_prefixed_accepted(self, valid_uuid):
        """UUID mit ent-Prefix wird akzeptiert."""

        class Model(BaseModel):
            entity: EntityId

        model = Model(entity=f"ent-{valid_uuid}")

        assert model.entity == f"ent-{valid_uuid}"

    def test_invalid_rejected(self):
        """Ungueltige Entity-ID wird abgelehnt."""

        class Model(BaseModel):
            entity: EntityId

        with pytest.raises(ValidationError):
            Model(entity="invalid")


class TestISOTimestampType:
    """Tests fuer ISOTimestamp Annotated Type."""

    def test_valid_timestamp_accepted(self):
        """Gueltiger Timestamp wird akzeptiert."""

        class Model(BaseModel):
            timestamp: ISOTimestamp

        model = Model(timestamp="2024-01-15T10:30:00Z")

        assert model.timestamp == "2024-01-15T10:30:00Z"

    def test_invalid_timestamp_rejected(self):
        """Ungueltiger Timestamp wird abgelehnt."""

        class Model(BaseModel):
            timestamp: ISOTimestamp

        with pytest.raises(ValidationError):
            Model(timestamp="2024-01-15")


class TestNonEmptyStringType:
    """Tests fuer NonEmptyString Annotated Type."""

    def test_valid_string_accepted(self):
        """Nicht-leerer String wird akzeptiert."""

        class Model(BaseModel):
            name: NonEmptyString

        model = Model(name="Test")

        assert model.name == "Test"

    def test_empty_string_rejected(self):
        """Leerer String wird abgelehnt."""

        class Model(BaseModel):
            name: NonEmptyString

        with pytest.raises(ValidationError):
            Model(name="")

    def test_whitespace_only_rejected(self):
        """Nur-Whitespace wird nach Strip abgelehnt."""

        class Model(BaseModel):
            name: NonEmptyString

        with pytest.raises(ValidationError):
            Model(name="   ")

    def test_whitespace_stripped(self):
        """Whitespace wird gestrippt."""

        class Model(BaseModel):
            name: NonEmptyString

        model = Model(name="  Test  ")

        assert model.name == "Test"
