"""Exception-Hierarchie für die Anwendung.

Dieses Modul stellt eine einheitliche Exception-Hierarchie bereit:
    - AppError: Basis-Exception für alle Anwendungsfehler
    - ValidationError: Validierungsfehler (400)
    - NotFoundError: Ressource nicht gefunden (404)
    - AuthenticationError: Authentifizierungsfehler (401)
    - AuthorizationError: Berechtigungsfehler (403)
    - ConflictError: Konflikt-Fehler (409)
    - TenantError: Mandanten-bezogene Fehler (403)
"""

from mkg_core.exceptions.errors import (
    AppError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    TenantError,
    ValidationError,
)

__all__ = [
    "AppError",
    "AuthenticationError",
    "AuthorizationError",
    "ConflictError",
    "NotFoundError",
    "TenantError",
    "ValidationError",
]
