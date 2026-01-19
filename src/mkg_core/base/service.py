"""Abstrakte Basis für Business-Logik Services.

Stellt eine abstrakte Basisklasse für Services bereit,
die Business-Logik kapseln und auf Repositories zugreifen.

Example:
    >>> from mkg_core.base import BaseService
    >>> class UserService(BaseService[User, CreateUserDTO, UpdateUserDTO]):
    ...     def _create_entity(self, tenant_id: str, dto: CreateUserDTO) -> User:
    ...         return User(id=generate_id(), tenant_id=tenant_id, **dto.model_dump())
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from mkg_core.exceptions.errors import NotFoundError
from mkg_core.utils.logging import get_logger
from mkg_core.utils.pagination import PaginatedResult, PaginationRequest

if TYPE_CHECKING:
    from mkg_core.base.repository import BaseRepository


class BaseService[T, CreateT, UpdateT](ABC):
    """Abstrakte Basisklasse für Business-Logik Services.

    Implementiert CRUD-Operationen mit Business-Logik-Hooks
    und delegiert Datenzugriff an ein Repository.

    Type Parameters:
        T: Der Entity-Typ.
        CreateT: Der DTO-Typ für Create-Operationen.
        UpdateT: Der DTO-Typ für Update-Operationen.

    Attributes:
        repository: Das Repository für Datenzugriff.
        logger: Logger-Instanz für diesen Service.

    Example:
        >>> class ProductService(BaseService[Product, CreateDTO, UpdateDTO]):
        ...     def _create_entity(self, tenant_id: str, dto: CreateDTO) -> Product:
        ...         return Product(id=f"prd-{uuid4()}", tenant_id=tenant_id)
        ...
        ...     def _apply_updates(self, entity: Product, dto: UpdateDTO) -> dict:
        ...         return dto.get_update_data()
    """

    def __init__(self, repository: BaseRepository[T]) -> None:
        """Initialisiert den Service.

        Args:
            repository: Das Repository für Datenzugriff.
        """
        self.repository = repository
        self.logger = get_logger(self.__class__.__name__)

    @property
    def entity_name(self) -> str:
        """Name der Entity für Fehlermeldungen.

        Kann überschrieben werden für bessere Lesbarkeit.

        Returns:
            Der Entity-Name (Default: Klassenname ohne 'Service').
        """
        name = self.__class__.__name__
        if name.endswith("Service"):
            name = name[:-7]
        return name

    @abstractmethod
    def _create_entity(self, tenant_id: str, dto: CreateT) -> T:
        """Erstellt eine Entity aus einem Create-DTO.

        Muss von Subklassen implementiert werden.

        Args:
            tenant_id: Die Tenant-ID.
            dto: Das Create-DTO.

        Returns:
            Die neue Entity-Instanz.
        """
        ...

    @abstractmethod
    def _apply_updates(self, entity: T, dto: UpdateT) -> dict[str, Any]:
        """Wendet Updates aus einem DTO auf eine Entity an.

        Muss von Subklassen implementiert werden.

        Args:
            entity: Die bestehende Entity.
            dto: Das Update-DTO.

        Returns:
            Dictionary mit den zu aktualisierenden Feldern.
        """
        ...

    def get(self, tenant_id: str, entity_id: str) -> T:
        """Lädt eine Entity nach ID.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            entity_id: Die Entity-ID.

        Returns:
            Die gefundene Entity.

        Raises:
            NotFoundError: Wenn die Entity nicht existiert.

        Example:
            >>> user = service.get("tnt-123", "usr-456")
        """
        self.logger.debug(
            "Getting entity",
            entity_type=self.entity_name,
            tenant_id=tenant_id,
            entity_id=entity_id,
        )

        entity = self.repository.get(tenant_id, entity_id)
        if entity is None:
            raise NotFoundError(self.entity_name, entity_id=entity_id)

        return entity

    def get_or_none(self, tenant_id: str, entity_id: str) -> T | None:
        """Lädt eine Entity nach ID oder gibt None zurück.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            entity_id: Die Entity-ID.

        Returns:
            Die gefundene Entity oder None.

        Example:
            >>> user = service.get_or_none("tnt-123", "usr-456")
            >>> if user is None:
            ...     print("User not found")
        """
        return self.repository.get(tenant_id, entity_id)

    def create(
        self,
        tenant_id: str,
        dto: CreateT,
        *,
        created_by: str | None = None,
    ) -> T:
        """Erstellt eine neue Entity.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            dto: Das Create-DTO mit den Daten.
            created_by: ID des erstellenden Benutzers.

        Returns:
            Die erstellte Entity.

        Example:
            >>> dto = CreateUserDTO(email="test@example.com", name="Test")
            >>> user = service.create("tnt-123", dto, created_by="usr-admin")
        """
        self.logger.info(
            "Creating entity",
            entity_type=self.entity_name,
            tenant_id=tenant_id,
            created_by=created_by,
        )

        # Hook für Vor-Erstellung
        self._before_create(tenant_id, dto)

        # Entity erstellen
        entity = self._create_entity(tenant_id, dto)

        # In Repository speichern
        created = self.repository.create(tenant_id, entity)

        # Hook für Nach-Erstellung
        self._after_create(tenant_id, created)

        return created

    def update(
        self,
        tenant_id: str,
        entity_id: str,
        dto: UpdateT,
        *,
        updated_by: str | None = None,
    ) -> T:
        """Aktualisiert eine Entity.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            entity_id: Die ID der Entity.
            dto: Das Update-DTO mit den Änderungen.
            updated_by: ID des aktualisierenden Benutzers.

        Returns:
            Die aktualisierte Entity.

        Raises:
            NotFoundError: Wenn die Entity nicht existiert.

        Example:
            >>> dto = UpdateUserDTO(name="New Name")
            >>> user = service.update("tnt-123", "usr-456", dto)
        """
        # Prüfen ob Entity existiert
        entity = self.get(tenant_id, entity_id)

        self.logger.info(
            "Updating entity",
            entity_type=self.entity_name,
            tenant_id=tenant_id,
            entity_id=entity_id,
            updated_by=updated_by,
        )

        # Hook für Vor-Update
        self._before_update(tenant_id, entity, dto)

        # Updates extrahieren
        updates = self._apply_updates(entity, dto)

        if not updates:
            # Keine Änderungen
            return entity

        # Update durchführen
        updated = self.repository.update(
            tenant_id,
            entity_id,
            updates,
            updated_by=updated_by,
        )

        if updated is None:
            raise NotFoundError(self.entity_name, entity_id=entity_id)

        # Hook für Nach-Update
        self._after_update(tenant_id, updated)

        return updated

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
            soft: True für Soft-Delete (Default).
            deleted_by: ID des löschenden Benutzers.

        Raises:
            NotFoundError: Wenn die Entity nicht existiert.

        Example:
            >>> service.delete("tnt-123", "usr-456", deleted_by="usr-admin")
        """
        # Prüfen ob Entity existiert
        entity = self.get(tenant_id, entity_id)

        self.logger.info(
            "Deleting entity",
            entity_type=self.entity_name,
            tenant_id=tenant_id,
            entity_id=entity_id,
            soft=soft,
            deleted_by=deleted_by,
        )

        # Hook für Vor-Löschung
        self._before_delete(tenant_id, entity)

        # Löschen
        self.repository.delete(
            tenant_id,
            entity_id,
            soft=soft,
            deleted_by=deleted_by,
        )

        # Hook für Nach-Löschung
        self._after_delete(tenant_id, entity)

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
            include_inactive: Auch gelöschte einschließen.

        Returns:
            Paginiertes Ergebnis mit Entities.

        Example:
            >>> result = service.list("tnt-123", PaginationRequest(limit=20))
            >>> for entity in result.items:
            ...     print(entity.name)
        """
        self.logger.debug(
            "Listing entities",
            entity_type=self.entity_name,
            tenant_id=tenant_id,
            include_inactive=include_inactive,
        )

        return self.repository.list(
            tenant_id,
            pagination,
            include_inactive=include_inactive,
        )

    def exists(self, tenant_id: str, entity_id: str) -> bool:
        """Prüft ob eine Entity existiert.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            entity_id: Die ID der Entity.

        Returns:
            True wenn die Entity existiert.

        Example:
            >>> if service.exists("tnt-123", "usr-456"):
            ...     print("User exists")
        """
        return self.repository.exists(tenant_id, entity_id)

    # === Lifecycle Hooks ===
    # Diese Methoden können von Subklassen überschrieben werden
    # Sie sind absichtlich nicht abstract, da sie optional sind

    def _before_create(self, tenant_id: str, dto: CreateT) -> None:  # noqa: B027
        """Hook der vor der Erstellung aufgerufen wird.

        Args:
            tenant_id: Die Tenant-ID.
            dto: Das Create-DTO.
        """
        pass

    def _after_create(self, tenant_id: str, entity: T) -> None:  # noqa: B027
        """Hook der nach der Erstellung aufgerufen wird.

        Args:
            tenant_id: Die Tenant-ID.
            entity: Die erstellte Entity.
        """
        pass

    def _before_update(self, tenant_id: str, entity: T, dto: UpdateT) -> None:  # noqa: B027
        """Hook der vor dem Update aufgerufen wird.

        Args:
            tenant_id: Die Tenant-ID.
            entity: Die bestehende Entity.
            dto: Das Update-DTO.
        """
        pass

    def _after_update(self, tenant_id: str, entity: T) -> None:  # noqa: B027
        """Hook der nach dem Update aufgerufen wird.

        Args:
            tenant_id: Die Tenant-ID.
            entity: Die aktualisierte Entity.
        """
        pass

    def _before_delete(self, tenant_id: str, entity: T) -> None:  # noqa: B027
        """Hook der vor der Löschung aufgerufen wird.

        Args:
            tenant_id: Die Tenant-ID.
            entity: Die zu löschende Entity.
        """
        pass

    def _after_delete(self, tenant_id: str, entity: T) -> None:  # noqa: B027
        """Hook der nach der Löschung aufgerufen wird.

        Args:
            tenant_id: Die Tenant-ID.
            entity: Die gelöschte Entity.
        """
        pass
