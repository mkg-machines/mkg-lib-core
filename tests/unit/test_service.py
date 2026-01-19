"""Tests für BaseService."""

from typing import Any

import pytest
from pydantic import BaseModel

from mkg_core.base.service import BaseService
from mkg_core.exceptions.errors import NotFoundError
from mkg_core.utils.pagination import (
    PaginatedResult,
    PaginationRequest,
    PaginationResponse,
)


class SampleEntity(BaseModel):
    """Test-Entity für Service-Tests."""

    id: str
    tenant_id: str
    name: str
    is_active: bool = True


class CreateDTO(BaseModel):
    """Create-DTO für Tests."""

    name: str


class UpdateDTO(BaseModel):
    """Update-DTO für Tests."""

    name: str | None = None

    def get_update_data(self) -> dict[str, Any]:
        return {k: v for k, v in self.model_dump().items() if v is not None}


class ConcreteService(BaseService[SampleEntity, CreateDTO, UpdateDTO]):
    """Konkrete Service-Implementierung für Tests."""

    def _create_entity(self, tenant_id: str, dto: CreateDTO) -> SampleEntity:
        return SampleEntity(
            id=f"ent-{tenant_id[-3:]}",
            tenant_id=tenant_id,
            name=dto.name,
        )

    def _apply_updates(self, entity: SampleEntity, dto: UpdateDTO) -> dict[str, Any]:
        return dto.get_update_data()


class TestBaseServiceInit:
    """Tests für Service-Initialisierung."""

    def test_init_sets_repository(self, mocker):
        """Service speichert Repository-Referenz."""
        mock_repo = mocker.MagicMock()
        service = ConcreteService(mock_repo)

        assert service.repository is mock_repo

    def test_init_creates_logger(self, mocker):
        """Service erstellt Logger."""
        mock_repo = mocker.MagicMock()
        service = ConcreteService(mock_repo)

        assert service.logger is not None


class TestBaseServiceEntityName:
    """Tests für entity_name Property."""

    def test_entity_name_strips_service_suffix(self, mocker):
        """entity_name entfernt 'Service' Suffix."""
        mock_repo = mocker.MagicMock()
        service = ConcreteService(mock_repo)

        # ConcreteService -> Concrete
        assert service.entity_name == "Concrete"

    def test_entity_name_keeps_full_name_without_suffix(self, mocker):
        """entity_name behält Namen wenn kein 'Service' Suffix."""

        class MyEntity(BaseService[SampleEntity, CreateDTO, UpdateDTO]):
            def _create_entity(self, tenant_id: str, dto: CreateDTO) -> SampleEntity:
                return SampleEntity(id="1", tenant_id=tenant_id, name=dto.name)

            def _apply_updates(self, entity: SampleEntity, dto: UpdateDTO) -> dict:
                return {}

        mock_repo = mocker.MagicMock()
        service = MyEntity(mock_repo)

        assert service.entity_name == "MyEntity"


class TestBaseServiceGet:
    """Tests für get() Methode."""

    @pytest.fixture
    def service(self, mocker):
        mock_repo = mocker.MagicMock()
        return ConcreteService(mock_repo)

    def test_get_returns_entity(self, service):
        """get() gibt Entity zurück wenn gefunden."""
        expected = SampleEntity(id="ent-123", tenant_id="tnt-123", name="Test")
        service.repository.get.return_value = expected

        result = service.get("tnt-123", "ent-123")

        assert result is expected

    def test_get_raises_not_found_error(self, service):
        """get() wirft NotFoundError wenn nicht gefunden."""
        service.repository.get.return_value = None

        with pytest.raises(NotFoundError) as exc_info:
            service.get("tnt-123", "ent-123")

        # NotFoundError hat resource_type als message und entity_id in details
        assert "Concrete" in exc_info.value.message
        assert exc_info.value.details.get("entity_id") == "ent-123"


class TestBaseServiceGetOrNone:
    """Tests für get_or_none() Methode."""

    @pytest.fixture
    def service(self, mocker):
        mock_repo = mocker.MagicMock()
        return ConcreteService(mock_repo)

    def test_get_or_none_returns_entity(self, service):
        """get_or_none() gibt Entity zurück wenn gefunden."""
        expected = SampleEntity(id="ent-123", tenant_id="tnt-123", name="Test")
        service.repository.get.return_value = expected

        result = service.get_or_none("tnt-123", "ent-123")

        assert result is expected

    def test_get_or_none_returns_none(self, service):
        """get_or_none() gibt None zurück wenn nicht gefunden."""
        service.repository.get.return_value = None

        result = service.get_or_none("tnt-123", "ent-123")

        assert result is None


class TestBaseServiceCreate:
    """Tests für create() Methode."""

    @pytest.fixture
    def service(self, mocker):
        mock_repo = mocker.MagicMock()
        return ConcreteService(mock_repo)

    def test_create_returns_entity(self, service):
        """create() gibt erstellte Entity zurück."""
        dto = CreateDTO(name="New Entity")
        service.repository.create.return_value = SampleEntity(
            id="ent-123", tenant_id="tnt-123", name="New Entity"
        )

        result = service.create("tnt-123", dto)

        assert result.name == "New Entity"

    def test_create_calls_repository(self, service):
        """create() ruft Repository.create auf."""
        dto = CreateDTO(name="New Entity")
        service.repository.create.return_value = SampleEntity(
            id="ent-123", tenant_id="tnt-123", name="New Entity"
        )

        service.create("tnt-123", dto)

        service.repository.create.assert_called_once()

    def test_create_calls_hooks(self, service, mocker):
        """create() ruft Lifecycle-Hooks auf."""
        dto = CreateDTO(name="New Entity")
        service.repository.create.return_value = SampleEntity(
            id="ent-123", tenant_id="tnt-123", name="New Entity"
        )

        # Mock the hooks
        service._before_create = mocker.MagicMock()
        service._after_create = mocker.MagicMock()

        service.create("tnt-123", dto)

        service._before_create.assert_called_once_with("tnt-123", dto)
        service._after_create.assert_called_once()


class TestBaseServiceUpdate:
    """Tests für update() Methode."""

    @pytest.fixture
    def service(self, mocker):
        mock_repo = mocker.MagicMock()
        return ConcreteService(mock_repo)

    def test_update_returns_updated_entity(self, service):
        """update() gibt aktualisierte Entity zurück."""
        existing = SampleEntity(id="ent-123", tenant_id="tnt-123", name="Old Name")
        updated = SampleEntity(id="ent-123", tenant_id="tnt-123", name="New Name")
        service.repository.get.return_value = existing
        service.repository.update.return_value = updated

        dto = UpdateDTO(name="New Name")
        result = service.update("tnt-123", "ent-123", dto)

        assert result.name == "New Name"

    def test_update_raises_not_found_error(self, service):
        """update() wirft NotFoundError wenn Entity nicht existiert."""
        service.repository.get.return_value = None

        dto = UpdateDTO(name="New Name")
        with pytest.raises(NotFoundError):
            service.update("tnt-123", "ent-123", dto)

    def test_update_returns_existing_when_no_changes(self, service):
        """update() gibt bestehende Entity zurück wenn keine Änderungen."""
        existing = SampleEntity(id="ent-123", tenant_id="tnt-123", name="Name")
        service.repository.get.return_value = existing

        dto = UpdateDTO()  # Keine Änderungen
        result = service.update("tnt-123", "ent-123", dto)

        assert result is existing
        service.repository.update.assert_not_called()

    def test_update_calls_hooks(self, service, mocker):
        """update() ruft Lifecycle-Hooks auf."""
        existing = SampleEntity(id="ent-123", tenant_id="tnt-123", name="Old Name")
        updated = SampleEntity(id="ent-123", tenant_id="tnt-123", name="New Name")
        service.repository.get.return_value = existing
        service.repository.update.return_value = updated

        service._before_update = mocker.MagicMock()
        service._after_update = mocker.MagicMock()

        dto = UpdateDTO(name="New Name")
        service.update("tnt-123", "ent-123", dto)

        service._before_update.assert_called_once()
        service._after_update.assert_called_once()

    def test_update_passes_updated_by(self, service):
        """update() übergibt updated_by an Repository."""
        existing = SampleEntity(id="ent-123", tenant_id="tnt-123", name="Old Name")
        updated = SampleEntity(id="ent-123", tenant_id="tnt-123", name="New Name")
        service.repository.get.return_value = existing
        service.repository.update.return_value = updated

        dto = UpdateDTO(name="New Name")
        service.update("tnt-123", "ent-123", dto, updated_by="usr-admin")

        service.repository.update.assert_called_with(
            "tnt-123", "ent-123", {"name": "New Name"}, updated_by="usr-admin"
        )


class TestBaseServiceDelete:
    """Tests für delete() Methode."""

    @pytest.fixture
    def service(self, mocker):
        mock_repo = mocker.MagicMock()
        return ConcreteService(mock_repo)

    def test_delete_calls_repository(self, service):
        """delete() ruft Repository.delete auf."""
        existing = SampleEntity(id="ent-123", tenant_id="tnt-123", name="Test")
        service.repository.get.return_value = existing

        service.delete("tnt-123", "ent-123")

        service.repository.delete.assert_called_once()

    def test_delete_raises_not_found_error(self, service):
        """delete() wirft NotFoundError wenn Entity nicht existiert."""
        service.repository.get.return_value = None

        with pytest.raises(NotFoundError):
            service.delete("tnt-123", "ent-123")

    def test_delete_soft_by_default(self, service):
        """delete() ist standardmäßig Soft-Delete."""
        existing = SampleEntity(id="ent-123", tenant_id="tnt-123", name="Test")
        service.repository.get.return_value = existing

        service.delete("tnt-123", "ent-123")

        service.repository.delete.assert_called_with(
            "tnt-123", "ent-123", soft=True, deleted_by=None
        )

    def test_delete_hard_when_specified(self, service):
        """delete() kann Hard-Delete ausführen."""
        existing = SampleEntity(id="ent-123", tenant_id="tnt-123", name="Test")
        service.repository.get.return_value = existing

        service.delete("tnt-123", "ent-123", soft=False)

        service.repository.delete.assert_called_with(
            "tnt-123", "ent-123", soft=False, deleted_by=None
        )

    def test_delete_calls_hooks(self, service, mocker):
        """delete() ruft Lifecycle-Hooks auf."""
        existing = SampleEntity(id="ent-123", tenant_id="tnt-123", name="Test")
        service.repository.get.return_value = existing

        service._before_delete = mocker.MagicMock()
        service._after_delete = mocker.MagicMock()

        service.delete("tnt-123", "ent-123")

        service._before_delete.assert_called_once()
        service._after_delete.assert_called_once()


class TestBaseServiceList:
    """Tests für list() Methode."""

    @pytest.fixture
    def service(self, mocker):
        mock_repo = mocker.MagicMock()
        return ConcreteService(mock_repo)

    def test_list_returns_paginated_result(self, service):
        """list() gibt PaginatedResult zurück."""
        service.repository.list.return_value = PaginatedResult(
            items=[
                SampleEntity(id="ent-1", tenant_id="tnt-123", name="Entity 1"),
                SampleEntity(id="ent-2", tenant_id="tnt-123", name="Entity 2"),
            ],
            pagination=PaginationResponse(cursor=None, has_more=False),
        )

        result = service.list("tnt-123")

        assert isinstance(result, PaginatedResult)
        assert len(result.items) == 2

    def test_list_passes_pagination(self, service):
        """list() übergibt Pagination an Repository."""
        service.repository.list.return_value = PaginatedResult(
            items=[], pagination=PaginationResponse(cursor=None, has_more=False)
        )
        pagination = PaginationRequest(limit=10)

        service.list("tnt-123", pagination)

        service.repository.list.assert_called_with(
            "tnt-123", pagination, include_inactive=False
        )


class TestBaseServiceExists:
    """Tests für exists() Methode."""

    @pytest.fixture
    def service(self, mocker):
        mock_repo = mocker.MagicMock()
        return ConcreteService(mock_repo)

    def test_exists_delegates_to_repository(self, service):
        """exists() delegiert an Repository."""
        service.repository.exists.return_value = True

        result = service.exists("tnt-123", "ent-123")

        assert result is True
        service.repository.exists.assert_called_once_with("tnt-123", "ent-123")


class TestBaseServiceHooks:
    """Tests für Lifecycle-Hooks."""

    @pytest.fixture
    def service(self, mocker):
        mock_repo = mocker.MagicMock()
        return ConcreteService(mock_repo)

    def test_before_create_is_called(self, service, mocker):
        """_before_create wird aufgerufen."""
        calls = []

        class HookService(ConcreteService):
            def _before_create(self, tenant_id: str, dto: CreateDTO) -> None:
                calls.append(("before_create", tenant_id, dto))

        service = HookService(mocker.MagicMock())
        service.repository.create.return_value = SampleEntity(
            id="ent-123", tenant_id="tnt-123", name="Test"
        )

        dto = CreateDTO(name="Test")
        service.create("tnt-123", dto)

        assert len(calls) == 1
        assert calls[0][0] == "before_create"

    def test_after_create_is_called(self, service, mocker):
        """_after_create wird aufgerufen."""
        calls = []

        class HookService(ConcreteService):
            def _after_create(self, tenant_id: str, entity: SampleEntity) -> None:
                calls.append(("after_create", tenant_id, entity))

        service = HookService(mocker.MagicMock())
        service.repository.create.return_value = SampleEntity(
            id="ent-123", tenant_id="tnt-123", name="Test"
        )

        dto = CreateDTO(name="Test")
        service.create("tnt-123", dto)

        assert len(calls) == 1
        assert calls[0][0] == "after_create"

    def test_hooks_are_optional(self, service):
        """Hooks sind optional und tun standardmäßig nichts."""
        # Diese sollten keine Fehler werfen
        service._before_create("tnt", CreateDTO(name=""))
        service._after_create("tnt", SampleEntity(id="1", tenant_id="t", name=""))
        entity = SampleEntity(id="1", tenant_id="t", name="")
        service._before_update("tnt", entity, UpdateDTO())
        service._after_update("tnt", SampleEntity(id="1", tenant_id="t", name=""))
        service._before_delete("tnt", SampleEntity(id="1", tenant_id="t", name=""))
        service._after_delete("tnt", SampleEntity(id="1", tenant_id="t", name=""))
