"""Tests fuer mkg_core.models.base Modul.

Testet CoreModel, EntityBase, CreateDTO und UpdateDTO.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from mkg_core.models.base import CoreModel, CreateDTO, EntityBase, UpdateDTO

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def valid_entity_data() -> dict[str, Any]:
    """Valide Entity-Daten fuer Tests."""
    return {
        "id": "test-entity-123",
        "tenant_id": "tnt-550e8400-e29b-41d4-a716-446655440000",
    }


@pytest.fixture
def sample_user_id() -> str:
    """Sample User-ID fuer Tests."""
    return "usr-123"


# ============================================================
# CoreModel Tests
# ============================================================


class TestCoreModel:
    """Tests fuer CoreModel Basis-Klasse."""

    def test_whitespace_stripping(self):
        """Whitespace wird automatisch von String-Feldern entfernt."""

        class TestModel(CoreModel):
            name: str

        model = TestModel(name="  Test Name  ")

        assert model.name == "Test Name"

    def test_extra_fields_forbidden(self):
        """Zusaetzliche Felder werden abgelehnt."""

        class TestModel(CoreModel):
            name: str

        with pytest.raises(ValidationError) as exc_info:
            TestModel(name="Test", unknown_field="value")

        errors = exc_info.value.errors()
        assert any(e["type"] == "extra_forbidden" for e in errors)

    def test_validate_assignment(self):
        """Validierung erfolgt auch bei nachtraeglicher Zuweisung."""

        class TestModel(CoreModel):
            count: int

        model = TestModel(count=10)

        with pytest.raises(ValidationError):
            model.count = "not a number"  # type: ignore[assignment]

    def test_basic_model_creation(self):
        """Einfaches Model kann erstellt werden."""

        class TestModel(CoreModel):
            name: str
            value: int

        model = TestModel(name="Test", value=42)

        assert model.name == "Test"
        assert model.value == 42

    def test_model_dump(self):
        """model_dump() gibt korrektes Dictionary zurueck."""

        class TestModel(CoreModel):
            name: str
            active: bool = True

        model = TestModel(name="Test")
        data = model.model_dump()

        assert data == {"name": "Test", "active": True}

    def test_nested_model(self):
        """Verschachtelte Models funktionieren korrekt."""

        class Inner(CoreModel):
            value: int

        class Outer(CoreModel):
            inner: Inner

        model = Outer(inner=Inner(value=42))

        assert model.inner.value == 42

    @pytest.mark.parametrize(
        ("input_string", "expected"),
        [
            ("  hello  ", "hello"),
            ("\ttest\n", "test"),
            ("  multiple   spaces  ", "multiple   spaces"),
            ("no_spaces", "no_spaces"),
        ],
    )
    def test_whitespace_stripping_various(self, input_string, expected):
        """Whitespace-Stripping funktioniert bei verschiedenen Inputs."""

        class TestModel(CoreModel):
            text: str

        model = TestModel(text=input_string)

        assert model.text == expected


# ============================================================
# EntityBase Tests
# ============================================================


class TestEntityBase:
    """Tests fuer EntityBase."""

    def test_required_fields(self, valid_entity_data):
        """id und tenant_id sind Pflichtfelder."""

        class TestEntity(EntityBase):
            pass

        entity = TestEntity(**valid_entity_data)

        assert entity.id == valid_entity_data["id"]
        assert entity.tenant_id == valid_entity_data["tenant_id"]

    def test_id_required(self):
        """id ist ein Pflichtfeld."""

        class TestEntity(EntityBase):
            pass

        with pytest.raises(ValidationError) as exc_info:
            TestEntity(tenant_id="tnt-123")

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("id",) for e in errors)

    def test_tenant_id_required(self):
        """tenant_id ist ein Pflichtfeld."""

        class TestEntity(EntityBase):
            pass

        with pytest.raises(ValidationError) as exc_info:
            TestEntity(id="test-123")

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("tenant_id",) for e in errors)

    def test_uuid_auto_generated(self, valid_entity_data):
        """uuid wird automatisch generiert."""

        class TestEntity(EntityBase):
            pass

        entity = TestEntity(**valid_entity_data)

        assert entity.uuid is not None
        # Pruefe ob es ein gueltiges UUID-Format ist
        UUID(entity.uuid)  # Raises wenn ungueltig

    def test_uuid_unique(self, valid_entity_data):
        """Jede Entity bekommt eine einzigartige UUID."""

        class TestEntity(EntityBase):
            pass

        entity1 = TestEntity(**valid_entity_data)
        entity2 = TestEntity(**valid_entity_data)

        assert entity1.uuid != entity2.uuid

    def test_uuid_can_be_provided(self, valid_entity_data):
        """uuid kann auch manuell gesetzt werden."""

        class TestEntity(EntityBase):
            pass

        custom_uuid = "550e8400-e29b-41d4-a716-446655440000"
        entity = TestEntity(**valid_entity_data, uuid=custom_uuid)

        assert entity.uuid == custom_uuid

    def test_is_active_default_true(self, valid_entity_data):
        """is_active ist standardmaessig True."""

        class TestEntity(EntityBase):
            pass

        entity = TestEntity(**valid_entity_data)

        assert entity.is_active is True

    def test_is_active_can_be_set(self, valid_entity_data):
        """is_active kann explizit gesetzt werden."""

        class TestEntity(EntityBase):
            pass

        entity = TestEntity(**valid_entity_data, is_active=False)

        assert entity.is_active is False

    def test_created_at_auto_generated(self, valid_entity_data):
        """created_at wird automatisch gesetzt."""

        class TestEntity(EntityBase):
            pass

        before = datetime.now(UTC)
        entity = TestEntity(**valid_entity_data)
        after = datetime.now(UTC)

        assert before <= entity.created_at <= after

    def test_updated_at_auto_generated(self, valid_entity_data):
        """updated_at wird automatisch gesetzt."""

        class TestEntity(EntityBase):
            pass

        before = datetime.now(UTC)
        entity = TestEntity(**valid_entity_data)
        after = datetime.now(UTC)

        assert before <= entity.updated_at <= after

    def test_created_by_default_none(self, valid_entity_data):
        """created_by ist standardmaessig None."""

        class TestEntity(EntityBase):
            pass

        entity = TestEntity(**valid_entity_data)

        assert entity.created_by is None

    def test_created_by_can_be_set(self, valid_entity_data, sample_user_id):
        """created_by kann gesetzt werden."""

        class TestEntity(EntityBase):
            pass

        entity = TestEntity(**valid_entity_data, created_by=sample_user_id)

        assert entity.created_by == sample_user_id

    def test_updated_by_default_none(self, valid_entity_data):
        """updated_by ist standardmaessig None."""

        class TestEntity(EntityBase):
            pass

        entity = TestEntity(**valid_entity_data)

        assert entity.updated_by is None


class TestEntityBaseMarkUpdated:
    """Tests fuer EntityBase.mark_updated()."""

    def test_updates_timestamp(self, valid_entity_data):
        """mark_updated() aktualisiert updated_at."""

        class TestEntity(EntityBase):
            pass

        entity = TestEntity(**valid_entity_data)
        original_updated_at = entity.updated_at

        # Kleine Pause um Zeitunterschied sicherzustellen
        time.sleep(0.01)
        entity.mark_updated()

        assert entity.updated_at > original_updated_at

    def test_updates_user_id(self, valid_entity_data, sample_user_id):
        """mark_updated() setzt updated_by."""

        class TestEntity(EntityBase):
            pass

        entity = TestEntity(**valid_entity_data)
        entity.mark_updated(sample_user_id)

        assert entity.updated_by == sample_user_id

    def test_without_user_id(self, valid_entity_data):
        """mark_updated() funktioniert auch ohne user_id."""

        class TestEntity(EntityBase):
            pass

        entity = TestEntity(**valid_entity_data)
        original_updated_at = entity.updated_at

        time.sleep(0.01)
        entity.mark_updated()

        assert entity.updated_at > original_updated_at
        assert entity.updated_by is None


class TestEntityBaseSoftDelete:
    """Tests fuer EntityBase.soft_delete()."""

    def test_sets_is_active_false(self, valid_entity_data):
        """soft_delete() setzt is_active auf False."""

        class TestEntity(EntityBase):
            pass

        entity = TestEntity(**valid_entity_data)
        assert entity.is_active is True

        entity.soft_delete()

        assert entity.is_active is False

    def test_updates_timestamp(self, valid_entity_data):
        """soft_delete() aktualisiert updated_at."""

        class TestEntity(EntityBase):
            pass

        entity = TestEntity(**valid_entity_data)
        original_updated_at = entity.updated_at

        time.sleep(0.01)
        entity.soft_delete()

        assert entity.updated_at > original_updated_at

    def test_sets_updated_by(self, valid_entity_data, sample_user_id):
        """soft_delete() setzt updated_by."""

        class TestEntity(EntityBase):
            pass

        entity = TestEntity(**valid_entity_data)
        entity.soft_delete(sample_user_id)

        assert entity.updated_by == sample_user_id

    def test_idempotent(self, valid_entity_data):
        """Mehrfacher soft_delete() Aufruf ist idempotent."""

        class TestEntity(EntityBase):
            pass

        entity = TestEntity(**valid_entity_data)
        entity.soft_delete()
        entity.soft_delete()

        assert entity.is_active is False


# ============================================================
# CreateDTO Tests
# ============================================================


class TestCreateDTO:
    """Tests fuer CreateDTO."""

    def test_inherits_from_core_model(self):
        """CreateDTO erbt von CoreModel."""
        assert issubclass(CreateDTO, CoreModel)

    def test_basic_create_dto(self):
        """CreateDTO kann als Basis fuer Create-DTOs verwendet werden."""

        class CreateUserDTO(CreateDTO):
            email: str
            name: str

        dto = CreateUserDTO(email="test@example.com", name="Test User")

        assert dto.email == "test@example.com"
        assert dto.name == "Test User"

    def test_whitespace_stripping(self):
        """CreateDTO erbt Whitespace-Stripping von CoreModel."""

        class CreateItemDTO(CreateDTO):
            title: str

        dto = CreateItemDTO(title="  Test Title  ")

        assert dto.title == "Test Title"

    def test_extra_fields_forbidden(self):
        """CreateDTO erlaubt keine Extra-Felder."""

        class CreateSimpleDTO(CreateDTO):
            name: str

        with pytest.raises(ValidationError):
            CreateSimpleDTO(name="Test", extra="not allowed")


# ============================================================
# UpdateDTO Tests
# ============================================================


class TestUpdateDTO:
    """Tests fuer UpdateDTO."""

    def test_inherits_from_core_model(self):
        """UpdateDTO erbt von CoreModel."""
        assert issubclass(UpdateDTO, CoreModel)

    def test_basic_update_dto(self):
        """UpdateDTO kann als Basis fuer Update-DTOs verwendet werden."""

        class UpdateUserDTO(UpdateDTO):
            email: str | None = None
            name: str | None = None

        dto = UpdateUserDTO(email="new@example.com")

        assert dto.email == "new@example.com"
        assert dto.name is None

    def test_get_update_data_only_set_fields(self):
        """get_update_data() gibt nur gesetzte Felder zurueck."""

        class UpdateItemDTO(UpdateDTO):
            title: str | None = None
            description: str | None = None
            price: float | None = None

        dto = UpdateItemDTO(title="New Title", price=29.99)
        data = dto.get_update_data()

        assert data == {"title": "New Title", "price": 29.99}
        assert "description" not in data

    def test_get_update_data_empty(self):
        """get_update_data() gibt leeres Dict wenn nichts gesetzt."""

        class UpdateEmptyDTO(UpdateDTO):
            name: str | None = None
            value: int | None = None

        dto = UpdateEmptyDTO()
        data = dto.get_update_data()

        assert data == {}

    def test_get_update_data_all_fields(self):
        """get_update_data() gibt alle Felder wenn alle gesetzt."""

        class UpdateFullDTO(UpdateDTO):
            a: str | None = None
            b: int | None = None
            c: bool | None = None

        dto = UpdateFullDTO(a="test", b=42, c=True)
        data = dto.get_update_data()

        assert data == {"a": "test", "b": 42, "c": True}

    def test_whitespace_stripping(self):
        """UpdateDTO erbt Whitespace-Stripping."""

        class UpdateTextDTO(UpdateDTO):
            text: str | None = None

        dto = UpdateTextDTO(text="  trimmed  ")

        assert dto.text == "trimmed"

    def test_get_update_data_preserves_falsy_values(self):
        """get_update_data() behaelt falsy Werte (ausser None)."""

        class UpdateFalsyDTO(UpdateDTO):
            empty_string: str | None = None
            zero: int | None = None
            false_bool: bool | None = None
            none_value: str | None = None

        dto = UpdateFalsyDTO(empty_string="", zero=0, false_bool=False)
        data = dto.get_update_data()

        assert data == {"empty_string": "", "zero": 0, "false_bool": False}


# ============================================================
# Integration Tests
# ============================================================


class TestModelIntegration:
    """Integration-Tests fuer Model-Interaktionen."""

    def test_entity_with_custom_fields(self):
        """EntityBase mit Custom-Feldern funktioniert korrekt."""

        class Product(EntityBase):
            name: str
            price: float
            category: str | None = None

        product = Product(
            id="prod-123",
            tenant_id="tnt-456",
            name="Test Product",
            price=99.99,
        )

        assert product.id == "prod-123"
        assert product.name == "Test Product"
        assert product.price == 99.99
        assert product.category is None
        assert product.is_active is True
        assert product.uuid is not None

    def test_entity_serialization(self, valid_entity_data):
        """Entity kann zu JSON serialisiert werden."""

        class SimpleEntity(EntityBase):
            pass

        entity = SimpleEntity(**valid_entity_data)
        json_str = entity.model_dump_json()

        assert valid_entity_data["id"] in json_str
        assert valid_entity_data["tenant_id"] in json_str

    def test_entity_deserialization(self, valid_entity_data):
        """Entity kann von Dictionary erstellt werden."""

        class SimpleEntity(EntityBase):
            pass

        entity = SimpleEntity.model_validate(valid_entity_data)

        assert entity.id == valid_entity_data["id"]
        assert entity.tenant_id == valid_entity_data["tenant_id"]
