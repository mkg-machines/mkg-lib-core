"""Abstrakte Basis für Repository Pattern.

Stellt eine abstrakte Basisklasse für Datenzugriff bereit,
die das Repository Pattern implementiert.

Example:
    >>> from mkg_core.base import BaseRepository
    >>> class UserRepository(BaseRepository[User]):
    ...     def _get_pk(self, tenant_id: str, entity_id: str) -> str:
    ...         return f"TENANT#{tenant_id}#USER"
    ...     def _get_sk(self, entity_id: str) -> str:
    ...         return f"USER#{entity_id}"
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from boto3.dynamodb.conditions import Key

from mkg_core.utils.logging import get_logger
from mkg_core.utils.pagination import (
    PaginatedResult,
    PaginationRequest,
    create_paginated_result,
)

if TYPE_CHECKING:
    from mkg_core.clients.dynamodb import DynamoDBClient


class BaseRepository[T](ABC):
    """Abstrakte Basisklasse für Repositories.

    Implementiert das Repository Pattern für DynamoDB mit
    eingebauter Tenant-Isolation und Pagination.

    Type Parameters:
        T: Der Entity-Typ den dieses Repository verwaltet.

    Attributes:
        client: Der DynamoDB Client.
        logger: Logger-Instanz für dieses Repository.

    Example:
        >>> class ProductRepository(BaseRepository[Product]):
        ...     def _get_pk(self, tenant_id: str, entity_id: str) -> str:
        ...         return f"TENANT#{tenant_id}#PRODUCT"
        ...
        ...     def _get_sk(self, entity_id: str) -> str:
        ...         return f"PRODUCT#{entity_id}"
        ...
        ...     def _to_entity(self, item: dict) -> Product:
        ...         return Product(**item)
        ...
        ...     def _to_item(self, entity: Product) -> dict:
        ...         return entity.model_dump()
    """

    def __init__(self, client: DynamoDBClient) -> None:
        """Initialisiert das Repository.

        Args:
            client: Der DynamoDB Client für Datenbankoperationen.
        """
        self.client = client
        self.logger = get_logger(self.__class__.__name__)

    @abstractmethod
    def _get_pk(self, tenant_id: str, entity_id: str) -> str:
        """Baut den Partition Key für eine Entity.

        Args:
            tenant_id: Die Tenant-ID.
            entity_id: Die Entity-ID.

        Returns:
            Der zusammengesetzte Partition Key.
        """
        ...

    @abstractmethod
    def _get_sk(self, entity_id: str) -> str:
        """Baut den Sort Key für eine Entity.

        Args:
            entity_id: Die Entity-ID.

        Returns:
            Der Sort Key.
        """
        ...

    @abstractmethod
    def _to_entity(self, item: dict[str, Any]) -> T:
        """Konvertiert ein DynamoDB Item zu einer Entity.

        Args:
            item: Das DynamoDB Item Dictionary.

        Returns:
            Die Entity-Instanz.
        """
        ...

    @abstractmethod
    def _to_item(self, entity: T) -> dict[str, Any]:
        """Konvertiert eine Entity zu einem DynamoDB Item.

        Args:
            entity: Die Entity-Instanz.

        Returns:
            Das DynamoDB Item Dictionary.
        """
        ...

    def _get_list_pk(self, tenant_id: str) -> str:
        """Baut den Partition Key für List-Operationen.

        Standardmäßig wird _get_pk mit leerem entity_id verwendet.
        Kann überschrieben werden für spezifisches List-Verhalten.

        Args:
            tenant_id: Die Tenant-ID.

        Returns:
            Der Partition Key für Listen.
        """
        return self._get_pk(tenant_id, "")

    def _get_sk_prefix(self) -> str:
        """Gibt den Sort Key Prefix für List-Operationen zurück.

        Standardmäßig wird der SK für eine leere ID verwendet.
        Kann überschrieben werden für spezifisches List-Verhalten.

        Returns:
            Der SK Prefix für begins_with Queries.
        """
        return self._get_sk("").rstrip("#")

    def get(self, tenant_id: str, entity_id: str) -> T | None:
        """Lädt eine Entity nach ID.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            entity_id: Die Entity-ID.

        Returns:
            Die Entity oder None wenn nicht gefunden.

        Example:
            >>> user = repository.get("tnt-123", "usr-456")
        """
        pk = self._get_pk(tenant_id, entity_id)
        sk = self._get_sk(entity_id)

        self.logger.debug(
            "Getting entity",
            tenant_id=tenant_id,
            entity_id=entity_id,
        )

        item = self.client.get_item(tenant_id, pk, sk)
        if item is None:
            return None

        return self._to_entity(item)

    def create(self, tenant_id: str, entity: T) -> T:
        """Erstellt eine neue Entity.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            entity: Die zu erstellende Entity.

        Returns:
            Die erstellte Entity.

        Example:
            >>> user = User(id="usr-123", tenant_id="tnt-123", name="Test")
            >>> created = repository.create("tnt-123", user)
        """
        item = self._to_item(entity)
        entity_id = item.get("id", "")

        # Keys hinzufügen
        item["PK"] = self._get_pk(tenant_id, entity_id)
        item["SK"] = self._get_sk(entity_id)
        item["tenant_id"] = tenant_id

        self.logger.info(
            "Creating entity",
            tenant_id=tenant_id,
            entity_id=entity_id,
        )

        self.client.put_item(tenant_id, item)
        return entity

    def update(
        self,
        tenant_id: str,
        entity_id: str,
        updates: dict[str, Any],
        *,
        updated_by: str | None = None,
    ) -> T | None:
        """Aktualisiert eine Entity.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            entity_id: Die ID der Entity.
            updates: Dictionary mit zu aktualisierenden Feldern.
            updated_by: ID des Benutzers der die Änderung durchführt.

        Returns:
            Die aktualisierte Entity oder None wenn nicht gefunden.

        Example:
            >>> updated = repository.update(
            ...     "tnt-123",
            ...     "usr-456",
            ...     {"name": "New Name"},
            ...     updated_by="usr-admin"
            ... )
        """
        pk = self._get_pk(tenant_id, entity_id)
        sk = self._get_sk(entity_id)

        # Automatische updated_at Aktualisierung
        updates["updated_at"] = datetime.now(UTC).isoformat()
        if updated_by:
            updates["updated_by"] = updated_by

        self.logger.info(
            "Updating entity",
            tenant_id=tenant_id,
            entity_id=entity_id,
            fields=list(updates.keys()),
        )

        updated_item = self.client.update_item(tenant_id, pk, sk, updates)
        return self._to_entity(updated_item)

    def delete(
        self,
        tenant_id: str,
        entity_id: str,
        *,
        soft: bool = True,
        deleted_by: str | None = None,
    ) -> None:
        """Löscht eine Entity.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            entity_id: Die ID der Entity.
            soft: True für Soft-Delete (setzt is_active=False).
            deleted_by: ID des Benutzers der löscht.

        Example:
            >>> repository.delete("tnt-123", "usr-456", soft=True)
        """
        pk = self._get_pk(tenant_id, entity_id)
        sk = self._get_sk(entity_id)

        if soft:
            self.logger.info(
                "Soft-deleting entity",
                tenant_id=tenant_id,
                entity_id=entity_id,
            )
            updates: dict[str, Any] = {
                "is_active": False,
                "updated_at": datetime.now(UTC).isoformat(),
            }
            if deleted_by:
                updates["updated_by"] = deleted_by
            self.client.update_item(tenant_id, pk, sk, updates)
        else:
            self.logger.info(
                "Hard-deleting entity",
                tenant_id=tenant_id,
                entity_id=entity_id,
            )
            self.client.delete_item(tenant_id, pk, sk)

    def list(
        self,
        tenant_id: str,
        pagination: PaginationRequest | None = None,
        *,
        include_inactive: bool = False,
    ) -> PaginatedResult[T]:
        """Listet Entities eines Tenants.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            pagination: Optionale Pagination-Parameter.
            include_inactive: Auch gelöschte (is_active=False) einschließen.

        Returns:
            Paginiertes Ergebnis mit Entities.

        Example:
            >>> result = repository.list("tnt-123", PaginationRequest(limit=20))
            >>> for entity in result.items:
            ...     print(entity.name)
        """
        pk = self._get_list_pk(tenant_id)
        sk_prefix = self._get_sk_prefix()

        self.logger.debug(
            "Listing entities",
            tenant_id=tenant_id,
            include_inactive=include_inactive,
        )

        # SK Condition für begins_with
        sk_condition = Key("SK").begins_with(sk_prefix)

        # Filter für is_active wenn nötig
        filter_expression = None
        if not include_inactive:
            from boto3.dynamodb.conditions import Attr

            filter_expression = Attr("is_active").eq(True)

        result = self.client.query(
            tenant_id=tenant_id,
            pk=pk,
            sk_condition=sk_condition,
            pagination=pagination,
            filter_expression=filter_expression,
        )

        # Items zu Entities konvertieren
        entities = [self._to_entity(item) for item in result.items]

        return create_paginated_result(
            items=entities,
            last_evaluated_key=None,  # Key ist im pagination response
        )

    def exists(self, tenant_id: str, entity_id: str) -> bool:
        """Prüft ob eine Entity existiert.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            entity_id: Die ID der Entity.

        Returns:
            True wenn die Entity existiert.

        Example:
            >>> if repository.exists("tnt-123", "usr-456"):
            ...     print("User exists")
        """
        return self.get(tenant_id, entity_id) is not None

    def count(self, tenant_id: str, *, include_inactive: bool = False) -> int:
        """Zählt Entities eines Tenants.

        WARNUNG: Diese Operation kann teuer sein bei großen Datensätzen.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            include_inactive: Auch gelöschte einschließen.

        Returns:
            Anzahl der Entities.
        """
        pk = self._get_list_pk(tenant_id)
        sk_prefix = self._get_sk_prefix()

        sk_condition = Key("SK").begins_with(sk_prefix)

        filter_expression = None
        if not include_inactive:
            from boto3.dynamodb.conditions import Attr

            filter_expression = Attr("is_active").eq(True)

        count = 0
        pagination = PaginationRequest(limit=100)

        while True:
            result = self.client.query(
                tenant_id=tenant_id,
                pk=pk,
                sk_condition=sk_condition,
                pagination=pagination,
                filter_expression=filter_expression,
            )
            count += len(result.items)

            if not result.pagination.has_more:
                break

            pagination = PaginationRequest(
                cursor=result.pagination.cursor,
                limit=100,
            )

        return count
