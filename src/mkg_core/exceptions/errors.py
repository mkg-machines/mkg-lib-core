"""Einheitliche Exception-Hierarchie mit HTTP-Status-Mapping.

Stellt eine Hierarchie von Exceptions bereit, die automatisch auf
HTTP-Status-Codes gemappt werden können.

Example:
    >>> from mkg_core.exceptions import NotFoundError, ValidationError
    >>> raise NotFoundError("Entity", entity_id="123")
    >>> raise ValidationError("Invalid email", field="email")
"""

from __future__ import annotations

from typing import Any, ClassVar


class AppError(Exception):
    """Basis-Exception für alle Anwendungsfehler.

    Attributes:
        status_code: HTTP-Status-Code für API-Responses.
        error_code: Maschinenlesbarer Fehlercode.
        message: Menschenlesbare Fehlermeldung.
        details: Zusätzliche Fehlerdetails.
    """

    status_code: ClassVar[int] = 500
    error_code: ClassVar[str] = "INTERNAL_ERROR"

    def __init__(
        self,
        message: str = "An internal error occurred",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialisiert die Exception.

        Args:
            message: Die Fehlermeldung.
            details: Optionale zusätzliche Details.
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Konvertiert die Exception zu einem API-Response-Dictionary.

        Returns:
            Dictionary mit error_code, message und details.

        Example:
            >>> error = AppError("Something went wrong")
            >>> error.to_dict()
            {'error_code': 'INTERNAL_ERROR', 'message': '...', 'details': {}}
        """
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }

    def __str__(self) -> str:
        """String-Repräsentation der Exception."""
        if self.details:
            return f"{self.error_code}: {self.message} ({self.details})"
        return f"{self.error_code}: {self.message}"


class ValidationError(AppError):
    """Validierungsfehler (HTTP 400 Bad Request).

    Wird geworfen wenn Eingabedaten nicht den Anforderungen entsprechen.

    Example:
        >>> raise ValidationError("Invalid email format", field="email")
    """

    status_code: ClassVar[int] = 400
    error_code: ClassVar[str] = "VALIDATION_ERROR"

    def __init__(
        self,
        message: str = "Validation failed",
        *,
        field: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialisiert die ValidationError.

        Args:
            message: Die Fehlermeldung.
            field: Das Feld das den Fehler verursacht hat.
            details: Optionale zusätzliche Details.
        """
        details = details or {}
        if field:
            details["field"] = field
        super().__init__(message, details=details)


class NotFoundError(AppError):
    """Ressource nicht gefunden (HTTP 404 Not Found).

    Wird geworfen wenn eine angeforderte Ressource nicht existiert.

    Example:
        >>> raise NotFoundError("User", entity_id="usr-123")
    """

    status_code: ClassVar[int] = 404
    error_code: ClassVar[str] = "NOT_FOUND"

    def __init__(
        self,
        resource_type: str = "Resource",
        *,
        entity_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialisiert die NotFoundError.

        Args:
            resource_type: Der Typ der Ressource (z.B. "User", "Order").
            entity_id: Die ID der nicht gefundenen Ressource.
            details: Optionale zusätzliche Details.
        """
        details = details or {}
        if entity_id:
            details["entity_id"] = entity_id
        message = f"{resource_type} not found"
        super().__init__(message, details=details)


class AuthorizationError(AppError):
    """Berechtigungsfehler (HTTP 403 Forbidden).

    Wird geworfen wenn der Benutzer nicht berechtigt ist.

    Example:
        >>> raise AuthorizationError("You cannot access this resource")
    """

    status_code: ClassVar[int] = 403
    error_code: ClassVar[str] = "FORBIDDEN"

    def __init__(
        self,
        message: str = "You are not authorized to perform this action",
        *,
        required_permission: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialisiert die AuthorizationError.

        Args:
            message: Die Fehlermeldung.
            required_permission: Die benötigte Berechtigung.
            details: Optionale zusätzliche Details.
        """
        details = details or {}
        if required_permission:
            details["required_permission"] = required_permission
        super().__init__(message, details=details)


class AuthenticationError(AppError):
    """Authentifizierungsfehler (HTTP 401 Unauthorized).

    Wird geworfen wenn keine gültige Authentifizierung vorliegt.

    Example:
        >>> raise AuthenticationError("Token expired")
    """

    status_code: ClassVar[int] = 401
    error_code: ClassVar[str] = "UNAUTHORIZED"

    def __init__(
        self,
        message: str = "Authentication required",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialisiert die AuthenticationError.

        Args:
            message: Die Fehlermeldung.
            details: Optionale zusätzliche Details.
        """
        super().__init__(message, details=details)


class ConflictError(AppError):
    """Konflikt-Fehler (HTTP 409 Conflict).

    Wird geworfen bei Duplikaten oder Ressourcenkonflikten.

    Example:
        >>> raise ConflictError("Email already exists", field="email")
    """

    status_code: ClassVar[int] = 409
    error_code: ClassVar[str] = "CONFLICT"

    def __init__(
        self,
        message: str = "Resource conflict",
        *,
        field: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialisiert die ConflictError.

        Args:
            message: Die Fehlermeldung.
            field: Das Feld das den Konflikt verursacht hat.
            details: Optionale zusätzliche Details.
        """
        details = details or {}
        if field:
            details["field"] = field
        super().__init__(message, details=details)


class TenantError(AppError):
    """Mandanten-bezogener Fehler (HTTP 403 Forbidden).

    Wird geworfen bei Tenant-Isolation-Verletzungen.

    Example:
        >>> raise TenantError("Access to different tenant denied")
    """

    status_code: ClassVar[int] = 403
    error_code: ClassVar[str] = "TENANT_ERROR"

    def __init__(
        self,
        message: str = "Tenant access denied",
        *,
        tenant_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialisiert die TenantError.

        Args:
            message: Die Fehlermeldung.
            tenant_id: Die betroffene Tenant-ID.
            details: Optionale zusätzliche Details.
        """
        details = details or {}
        if tenant_id:
            details["tenant_id"] = tenant_id
        super().__init__(message, details=details)
