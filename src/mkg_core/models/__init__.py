"""Pydantic Models für die Anwendung.

Dieses Modul stellt Pydantic-Basismodelle bereit:
    - CoreModel: Basisklasse mit strikter Validierung
    - EntityBase: Basis-Felder für persistierte Entities (id, tenant_id, timestamps)
    - CreateDTO: Basis für Create-DTOs
    - UpdateDTO: Basis für Update-DTOs
"""

from mkg_core.models.base import (
    CoreModel,
    CreateDTO,
    EntityBase,
    UpdateDTO,
)

__all__ = [
    "CoreModel",
    "CreateDTO",
    "EntityBase",
    "UpdateDTO",
]
