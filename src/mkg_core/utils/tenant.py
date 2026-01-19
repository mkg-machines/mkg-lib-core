"""Tenant-Context-Management für die MKG Platform.

Stellt Thread-Local Storage für Tenant-Kontext bereit,
um Tenant-Isolation in Lambda-Funktionen zu gewährleisten.

Example:
    >>> from mkg_core.utils.tenant import TenantContext, set_tenant_context
    >>> ctx = TenantContext(tenant_id="tnt-123", user_id="usr-456")
    >>> set_tenant_context(ctx)
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

# Context Variable für Thread-Local Storage
_tenant_context: ContextVar[TenantContext | None] = ContextVar(
    "tenant_context", default=None
)


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Kontext-Informationen für den aktuellen Tenant.

    Attributes:
        tenant_id: Die eindeutige ID des Mandanten.
        user_id: Die ID des aktuellen Benutzers (optional).
        correlation_id: Request-Tracking-ID für Logging.
        roles: Liste der Benutzerrollen.
        extra: Zusätzliche Kontext-Daten.
    """

    tenant_id: str
    user_id: str | None = None
    correlation_id: str = field(default_factory=lambda: f"req-{uuid4()}")
    roles: tuple[str, ...] = field(default_factory=tuple)
    extra: dict[str, Any] = field(default_factory=dict)

    def has_role(self, role: str) -> bool:
        """Prüft ob der Benutzer eine bestimmte Rolle hat.

        Args:
            role: Die zu prüfende Rolle.

        Returns:
            True wenn der Benutzer die Rolle hat.
        """
        return role in self.roles

    def to_dict(self) -> dict[str, Any]:
        """Konvertiert den Context zu einem Dictionary.

        Returns:
            Dictionary mit allen Context-Werten.
        """
        return {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "correlation_id": self.correlation_id,
            "roles": list(self.roles),
            **self.extra,
        }


class TenantContextError(Exception):
    """Fehler bei Tenant-Context-Operationen."""


class TenantNotSetError(TenantContextError):
    """Wird geworfen wenn kein Tenant-Context gesetzt ist."""

    def __init__(self, message: str = "Tenant context is not set") -> None:
        super().__init__(message)


def get_current_tenant() -> TenantContext | None:
    """Gibt den aktuellen Tenant-Context zurück.

    Returns:
        Der aktuelle TenantContext oder None wenn nicht gesetzt.

    Example:
        >>> ctx = get_current_tenant()
        >>> if ctx:
        ...     print(ctx.tenant_id)
    """
    return _tenant_context.get()


def get_current_tenant_id() -> str | None:
    """Gibt die aktuelle Tenant-ID zurück.

    Returns:
        Die Tenant-ID oder None wenn kein Context gesetzt.

    Example:
        >>> tenant_id = get_current_tenant_id()
    """
    ctx = get_current_tenant()
    return ctx.tenant_id if ctx else None


def require_current_tenant() -> TenantContext:
    """Gibt den aktuellen Tenant-Context zurück oder wirft eine Exception.

    Returns:
        Der aktuelle TenantContext.

    Raises:
        TenantNotSetError: Wenn kein Tenant-Context gesetzt ist.

    Example:
        >>> ctx = require_current_tenant()
        >>> print(ctx.tenant_id)
    """
    ctx = get_current_tenant()
    if ctx is None:
        raise TenantNotSetError()
    return ctx


def set_tenant_context(context: TenantContext) -> None:
    """Setzt den Tenant-Context für den aktuellen Thread/Coroutine.

    Args:
        context: Der zu setzende TenantContext.

    Example:
        >>> ctx = TenantContext(tenant_id="tnt-123")
        >>> set_tenant_context(ctx)
    """
    _tenant_context.set(context)


def clear_tenant_context() -> None:
    """Löscht den aktuellen Tenant-Context.

    Sollte am Ende jedes Lambda-Invocations aufgerufen werden.

    Example:
        >>> clear_tenant_context()
    """
    _tenant_context.set(None)


class tenant_context:  # noqa: N801
    """Context Manager für temporären Tenant-Context.

    Example:
        >>> with tenant_context(tenant_id="tnt-123", user_id="usr-456"):
        ...     ctx = get_current_tenant()
        ...     print(ctx.tenant_id)
        'tnt-123'
    """

    def __init__(
        self,
        tenant_id: str,
        *,
        user_id: str | None = None,
        correlation_id: str | None = None,
        roles: tuple[str, ...] | list[str] = (),
        **extra: Any,
    ) -> None:
        """Initialisiert den Context Manager.

        Args:
            tenant_id: Die Tenant-ID.
            user_id: Optionale User-ID.
            correlation_id: Optionale Correlation-ID (generiert wenn nicht angegeben).
            roles: Optionale Benutzerrollen.
            **extra: Zusätzliche Kontext-Daten.
        """
        roles_tuple = tuple(roles) if isinstance(roles, list) else roles
        self._context = TenantContext(
            tenant_id=tenant_id,
            user_id=user_id,
            correlation_id=correlation_id or f"req-{uuid4()}",
            roles=roles_tuple,
            extra=dict(extra),
        )
        self._token: Any = None

    def __enter__(self) -> TenantContext:
        """Setzt den Tenant-Context."""
        self._token = _tenant_context.set(self._context)
        return self._context

    def __exit__(self, *args: Any) -> None:
        """Stellt den vorherigen Context wieder her."""
        _tenant_context.reset(self._token)


def with_tenant_context(
    tenant_id: str,
    *,
    user_id: str | None = None,
    correlation_id: str | None = None,
    roles: tuple[str, ...] = (),
) -> AbstractContextManager[TenantContext]:
    """Generator-basierter Context Manager für Tenant-Context.

    Args:
        tenant_id: Die Tenant-ID.
        user_id: Optionale User-ID.
        correlation_id: Optionale Correlation-ID.
        roles: Optionale Benutzerrollen.

    Yields:
        Der gesetzte TenantContext.

    Example:
        >>> from contextlib import contextmanager
        >>> with with_tenant_context("tnt-123") as ctx:
        ...     print(ctx.tenant_id)
    """
    from collections.abc import Generator
    from contextlib import contextmanager

    @contextmanager
    def _context() -> Generator[TenantContext]:
        ctx = TenantContext(
            tenant_id=tenant_id,
            user_id=user_id,
            correlation_id=correlation_id or f"req-{uuid4()}",
            roles=roles,
        )
        token = _tenant_context.set(ctx)
        try:
            yield ctx
        finally:
            _tenant_context.reset(token)

    return _context()


def require_tenant[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Decorator der sicherstellt dass ein Tenant-Context gesetzt ist.

    Kann auf Funktionen angewendet werden die Tenant-Context benötigen.

    Args:
        func: Die zu dekorierende Funktion.

    Returns:
        Die dekorierte Funktion.

    Raises:
        TenantNotSetError: Wenn kein Tenant-Context gesetzt ist.

    Example:
        >>> @require_tenant
        ... def process_entity(entity_id: str) -> dict:
        ...     ctx = require_current_tenant()
        ...     return {"tenant": ctx.tenant_id, "entity": entity_id}
    """

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        if get_current_tenant() is None:
            raise TenantNotSetError(
                f"Function {func.__name__} requires tenant context to be set"
            )
        return func(*args, **kwargs)

    return wrapper


def extract_tenant_from_jwt(claims: dict[str, Any]) -> TenantContext:
    """Extrahiert Tenant-Informationen aus JWT Claims.

    Unterstützt das Cognito JWT-Format.

    Args:
        claims: Die JWT Claims als Dictionary.

    Returns:
        Ein TenantContext mit den extrahierten Informationen.

    Raises:
        TenantContextError: Wenn tenant_id nicht in den Claims ist.

    Example:
        >>> claims = {
        ...     "sub": "user-123",
        ...     "custom:tenant_id": "tnt-456",
        ...     "cognito:groups": ["Admin", "User"]
        ... }
        >>> ctx = extract_tenant_from_jwt(claims)
        >>> ctx.tenant_id
        'tnt-456'
    """
    # Tenant-ID aus verschiedenen möglichen Claim-Namen
    tenant_id = (
        claims.get("custom:tenant_id")
        or claims.get("tenant_id")
        or claims.get("tenantId")
    )

    if not tenant_id:
        msg = "tenant_id not found in JWT claims"
        raise TenantContextError(msg)

    # User-ID
    user_id = claims.get("sub") or claims.get("user_id") or claims.get("userId")

    # Rollen aus Cognito Groups
    roles = claims.get("cognito:groups") or claims.get("groups") or []
    if isinstance(roles, str):
        roles = [roles]

    return TenantContext(
        tenant_id=tenant_id,
        user_id=user_id,
        roles=tuple(roles),
    )
