"""Tests für BaseRepository."""

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import BaseModel

from mkg_core.base.repository import BaseRepository
from mkg_core.utils.pagination import PaginatedResult, PaginationRequest, PaginationResponse


class SampleEntity(BaseModel):
    """Test-Entity für Repository-Tests."""

    id: str
    tenant_id: str
    name: str
    is_active: bool = True
    created_at: str | None = None
    updated_at: str | None = None


class ConcreteRepository(BaseRepository[SampleEntity]):
    """Konkrete Repository-Implementierung für Tests."""

    def _get_pk(self, tenant_id: str, entity_id: str) -> str:
        return f"TENANT#{tenant_id}#TEST"

    def _get_sk(self, entity_id: str) -> str:
        return f"TEST#{entity_id}"

    def _to_entity(self, item: dict[str, Any]) -> SampleEntity:
        return SampleEntity(**item)

    def _to_item(self, entity: SampleEntity) -> dict[str, Any]:
        return entity.model_dump()


class TestBaseRepositoryInit:
    """Tests für Repository-Initialisierung."""

    def test_init_sets_client(self, mocker):
        """Repository speichert Client-Referenz."""
        mock_client = mocker.MagicMock()
        repo = ConcreteRepository(mock_client)

        assert repo.client is mock_client

    def test_init_creates_logger(self, mocker):
        """Repository erstellt Logger."""
        mock_client = mocker.MagicMock()
        repo = ConcreteRepository(mock_client)

        assert repo.logger is not None


class TestBaseRepositoryKeyMethods:
    """Tests für Key-Generierung."""

    @pytest.fixture
    def repo(self, mocker):
        return ConcreteRepository(mocker.MagicMock())

    def test_get_pk_builds_correct_key(self, repo):
        """_get_pk baut korrekten Partition Key."""
        pk = repo._get_pk("tnt-123", "ent-456")

        assert pk == "TENANT#tnt-123#TEST"

    def test_get_sk_builds_correct_key(self, repo):
        """_get_sk baut korrekten Sort Key."""
        sk = repo._get_sk("ent-456")

        assert sk == "TEST#ent-456"

    def test_get_list_pk_uses_get_pk(self, repo):
        """_get_list_pk verwendet _get_pk mit leerem entity_id."""
        list_pk = repo._get_list_pk("tnt-123")

        assert list_pk == "TENANT#tnt-123#TEST"

    def test_get_sk_prefix_strips_trailing_hash(self, repo):
        """_get_sk_prefix entfernt trailing Hash."""
        prefix = repo._get_sk_prefix()

        # _get_sk("") returns "TEST#" and rstrip("#") gives "TEST"
        assert prefix == "TEST"
        assert not prefix.endswith("#")


class TestBaseRepositoryGet:
    """Tests für get() Methode."""

    @pytest.fixture
    def repo(self, mocker):
        mock_client = mocker.MagicMock()
        return ConcreteRepository(mock_client)

    def test_get_returns_entity(self, repo):
        """get() gibt Entity zurück wenn gefunden."""
        repo.client.get_item.return_value = {
            "id": "ent-123",
            "tenant_id": "tnt-123",
            "name": "Test Entity",
            "is_active": True,
        }

        entity = repo.get("tnt-123", "ent-123")

        assert entity is not None
        assert entity.id == "ent-123"
        assert entity.name == "Test Entity"

    def test_get_returns_none_when_not_found(self, repo):
        """get() gibt None zurück wenn nicht gefunden."""
        repo.client.get_item.return_value = None

        entity = repo.get("tnt-123", "ent-123")

        assert entity is None

    def test_get_calls_client_with_correct_keys(self, repo):
        """get() ruft Client mit korrekten Keys auf."""
        repo.client.get_item.return_value = None

        repo.get("tnt-123", "ent-123")

        repo.client.get_item.assert_called_once_with(
            "tnt-123", "TENANT#tnt-123#TEST", "TEST#ent-123"
        )


class TestBaseRepositoryCreate:
    """Tests für create() Methode."""

    @pytest.fixture
    def repo(self, mocker):
        mock_client = mocker.MagicMock()
        return ConcreteRepository(mock_client)

    def test_create_returns_entity(self, repo):
        """create() gibt erstellte Entity zurück."""
        entity = SampleEntity(id="ent-123", tenant_id="tnt-123", name="New Entity")

        result = repo.create("tnt-123", entity)

        assert result is entity

    def test_create_calls_client_with_item(self, repo):
        """create() ruft Client mit Item auf."""
        entity = SampleEntity(id="ent-123", tenant_id="tnt-123", name="New Entity")

        repo.create("tnt-123", entity)

        repo.client.put_item.assert_called_once()
        call_args = repo.client.put_item.call_args
        assert call_args[0][0] == "tnt-123"
        item = call_args[0][1]
        assert item["PK"] == "TENANT#tnt-123#TEST"
        assert item["SK"] == "TEST#ent-123"
        assert item["tenant_id"] == "tnt-123"


class TestBaseRepositoryUpdate:
    """Tests für update() Methode."""

    @pytest.fixture
    def repo(self, mocker):
        mock_client = mocker.MagicMock()
        return ConcreteRepository(mock_client)

    def test_update_returns_updated_entity(self, repo):
        """update() gibt aktualisierte Entity zurück."""
        repo.client.update_item.return_value = {
            "id": "ent-123",
            "tenant_id": "tnt-123",
            "name": "Updated Name",
            "is_active": True,
        }

        result = repo.update("tnt-123", "ent-123", {"name": "Updated Name"})

        assert result is not None
        assert result.name == "Updated Name"

    def test_update_adds_updated_at(self, repo):
        """update() fügt updated_at automatisch hinzu."""
        repo.client.update_item.return_value = {
            "id": "ent-123",
            "tenant_id": "tnt-123",
            "name": "Test",
            "is_active": True,
        }

        repo.update("tnt-123", "ent-123", {"name": "Test"})

        call_args = repo.client.update_item.call_args
        updates = call_args[0][3]
        assert "updated_at" in updates

    def test_update_adds_updated_by_when_provided(self, repo):
        """update() fügt updated_by hinzu wenn übergeben."""
        repo.client.update_item.return_value = {
            "id": "ent-123",
            "tenant_id": "tnt-123",
            "name": "Test",
            "is_active": True,
        }

        repo.update("tnt-123", "ent-123", {"name": "Test"}, updated_by="usr-admin")

        call_args = repo.client.update_item.call_args
        updates = call_args[0][3]
        assert updates["updated_by"] == "usr-admin"


class TestBaseRepositoryDelete:
    """Tests für delete() Methode."""

    @pytest.fixture
    def repo(self, mocker):
        mock_client = mocker.MagicMock()
        return ConcreteRepository(mock_client)

    def test_soft_delete_updates_is_active(self, repo):
        """Soft-Delete setzt is_active=False."""
        repo.delete("tnt-123", "ent-123", soft=True)

        repo.client.update_item.assert_called_once()
        call_args = repo.client.update_item.call_args
        updates = call_args[0][3]
        assert updates["is_active"] is False

    def test_soft_delete_adds_updated_at(self, repo):
        """Soft-Delete fügt updated_at hinzu."""
        repo.delete("tnt-123", "ent-123", soft=True)

        call_args = repo.client.update_item.call_args
        updates = call_args[0][3]
        assert "updated_at" in updates

    def test_soft_delete_adds_deleted_by(self, repo):
        """Soft-Delete fügt deleted_by hinzu wenn übergeben."""
        repo.delete("tnt-123", "ent-123", soft=True, deleted_by="usr-admin")

        call_args = repo.client.update_item.call_args
        updates = call_args[0][3]
        assert updates["updated_by"] == "usr-admin"

    def test_hard_delete_calls_delete_item(self, repo):
        """Hard-Delete ruft delete_item auf."""
        repo.delete("tnt-123", "ent-123", soft=False)

        repo.client.delete_item.assert_called_once_with(
            "tnt-123", "TENANT#tnt-123#TEST", "TEST#ent-123"
        )


class TestBaseRepositoryList:
    """Tests für list() Methode."""

    @pytest.fixture
    def repo(self, mocker):
        mock_client = mocker.MagicMock()
        return ConcreteRepository(mock_client)

    def test_list_returns_paginated_result(self, repo):
        """list() gibt PaginatedResult zurück."""
        repo.client.query.return_value = PaginatedResult(
            items=[
                {"id": "ent-1", "tenant_id": "tnt-123", "name": "Entity 1", "is_active": True},
                {"id": "ent-2", "tenant_id": "tnt-123", "name": "Entity 2", "is_active": True},
            ],
            pagination=PaginationResponse(cursor=None, has_more=False),
        )

        result = repo.list("tnt-123")

        assert isinstance(result, PaginatedResult)
        assert len(result.items) == 2

    def test_list_converts_items_to_entities(self, repo):
        """list() konvertiert Items zu Entities."""
        repo.client.query.return_value = PaginatedResult(
            items=[
                {"id": "ent-1", "tenant_id": "tnt-123", "name": "Entity 1", "is_active": True},
            ],
            pagination=PaginationResponse(cursor=None, has_more=False),
        )

        result = repo.list("tnt-123")

        assert isinstance(result.items[0], SampleEntity)

    def test_list_filters_inactive_by_default(self, repo):
        """list() filtert inaktive Entities standardmäßig."""
        repo.client.query.return_value = PaginatedResult(
            items=[], pagination=PaginationResponse(cursor=None, has_more=False)
        )

        repo.list("tnt-123")

        call_kwargs = repo.client.query.call_args[1]
        assert "filter_expression" in call_kwargs

    def test_list_includes_inactive_when_requested(self, repo):
        """list() inkludiert inaktive wenn angefordert."""
        repo.client.query.return_value = PaginatedResult(
            items=[], pagination=PaginationResponse(cursor=None, has_more=False)
        )

        repo.list("tnt-123", include_inactive=True)

        call_kwargs = repo.client.query.call_args[1]
        assert call_kwargs.get("filter_expression") is None


class TestBaseRepositoryExists:
    """Tests für exists() Methode."""

    @pytest.fixture
    def repo(self, mocker):
        mock_client = mocker.MagicMock()
        return ConcreteRepository(mock_client)

    def test_exists_returns_true_when_found(self, repo):
        """exists() gibt True zurück wenn Entity existiert."""
        repo.client.get_item.return_value = {
            "id": "ent-123",
            "tenant_id": "tnt-123",
            "name": "Test",
            "is_active": True,
        }

        result = repo.exists("tnt-123", "ent-123")

        assert result is True

    def test_exists_returns_false_when_not_found(self, repo):
        """exists() gibt False zurück wenn Entity nicht existiert."""
        repo.client.get_item.return_value = None

        result = repo.exists("tnt-123", "ent-123")

        assert result is False


class TestBaseRepositoryCount:
    """Tests für count() Methode."""

    @pytest.fixture
    def repo(self, mocker):
        mock_client = mocker.MagicMock()
        return ConcreteRepository(mock_client)

    def test_count_returns_total(self, repo):
        """count() gibt Gesamtzahl zurück."""
        repo.client.query.return_value = PaginatedResult(
            items=[
                {"id": "1", "tenant_id": "t", "name": "a", "is_active": True},
                {"id": "2", "tenant_id": "t", "name": "b", "is_active": True},
                {"id": "3", "tenant_id": "t", "name": "c", "is_active": True},
            ],
            pagination=PaginationResponse(cursor=None, has_more=False),
        )

        count = repo.count("tnt-123")

        assert count == 3

    def test_count_paginates_through_all_results(self, repo):
        """count() paginiert durch alle Ergebnisse."""
        # First call returns items with has_more=True
        repo.client.query.side_effect = [
            PaginatedResult(
                items=[
                    {"id": "1", "tenant_id": "t", "name": "a", "is_active": True},
                    {"id": "2", "tenant_id": "t", "name": "b", "is_active": True},
                ],
                pagination=PaginationResponse(cursor="next-cursor", has_more=True),
            ),
            PaginatedResult(
                items=[
                    {"id": "3", "tenant_id": "t", "name": "c", "is_active": True},
                ],
                pagination=PaginationResponse(cursor=None, has_more=False),
            ),
        ]

        count = repo.count("tnt-123")

        assert count == 3
        assert repo.client.query.call_count == 2
