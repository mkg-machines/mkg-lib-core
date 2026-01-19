"""Pydantic-Basismodelle mit Standard-Feldern.

Stellt Basis-Modelle bereit für alle Entitäten der Anwendung
mit einheitlicher Konfiguration und Standard-Feldern.

Example:
    >>> from mkg_core.models import EntityBase, CoreModel
    >>> class User(EntityBase):
    ...     email: str
    ...     name: str
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class CoreModel(BaseModel):
    """Basis für alle Pydantic Models der Anwendung.

    Konfiguriert mit strikter Validierung:
    - extra="forbid": Keine zusätzlichen Felder erlaubt
    - str_strip_whitespace: Whitespace wird automatisch getrimmt
    - validate_assignment: Validierung auch bei Zuweisung

    Example:
        >>> class MyModel(CoreModel):
        ...     name: str
        >>> m = MyModel(name="  Test  ")
        >>> m.name
        'Test'
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class EntityBase(CoreModel):
    """Basis-Felder für alle persistierten Entitäten.

    Enthält Standard-Felder für Audit-Trail und Identifikation.

    Attributes:
        uuid: Eindeutige UUID (automatisch generiert).
        id: Business-ID der Entität.
        tenant_id: ID des zugehörigen Mandanten.
        is_active: Soft-Delete Flag (Default: True).
        created_at: Erstellungszeitpunkt (automatisch gesetzt).
        created_by: ID des Erstellers.
        updated_at: Zeitpunkt der letzten Änderung.
        updated_by: ID des letzten Bearbeiters.

    Example:
        >>> class Product(EntityBase):
        ...     name: str
        ...     price: float
    """

    uuid: str = Field(default_factory=lambda: str(uuid4()))
    id: str
    tenant_id: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_by: str | None = None

    def mark_updated(self, user_id: str | None = None) -> None:
        """Markiert die Entität als aktualisiert.

        Args:
            user_id: ID des Benutzers der die Änderung durchführt.

        Example:
            >>> entity.mark_updated("usr-456")
        """
        self.updated_at = datetime.now(UTC)
        if user_id:
            self.updated_by = user_id

    def soft_delete(self, user_id: str | None = None) -> None:
        """Führt Soft-Delete durch (setzt is_active=False).

        Args:
            user_id: ID des Benutzers der löscht.

        Example:
            >>> entity.soft_delete("usr-456")
            >>> entity.is_active
            False
        """
        self.is_active = False
        self.mark_updated(user_id)


class CreateDTO(CoreModel):
    """Generische Basis für Create-DTOs.

    DTOs für die Erstellung neuer Entitäten sollten von
    dieser Klasse erben.

    Example:
        >>> class CreateUserDTO(CreateDTO):
        ...     email: str
        ...     name: str
    """


class UpdateDTO(CoreModel):
    """Generische Basis für Update-DTOs.

    DTOs für Updates sollten von dieser Klasse erben.
    Alle Felder sollten optional sein.

    Example:
        >>> class UpdateUserDTO(UpdateDTO):
        ...     email: str | None = None
        ...     name: str | None = None
    """

    def get_update_data(self) -> dict[str, Any]:
        """Gibt nur die gesetzten (nicht-None) Felder zurück.

        Returns:
            Dictionary mit nur den gesetzten Feldern.

        Example:
            >>> dto = UpdateUserDTO(name="New Name")
            >>> dto.get_update_data()
            {'name': 'New Name'}
        """
        return {
            key: value for key, value in self.model_dump().items() if value is not None
        }
