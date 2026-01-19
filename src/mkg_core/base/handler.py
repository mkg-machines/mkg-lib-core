"""Basis für Lambda Event Handler.

Stellt eine Basisklasse für AWS Lambda Handler bereit mit
automatischer TenantContext-Extraktion und Error-Handling.

Example:
    >>> from mkg_core.base import BaseHandler
    >>> class GetUserHandler(BaseHandler):
    ...     def process(self, event: dict, context: Any) -> dict:
    ...         user_id = event["pathParameters"]["user_id"]
    ...         return {"user": {"id": user_id}}
"""

from __future__ import annotations

import json
import os
import traceback
from abc import ABC, abstractmethod
from typing import Any

from mkg_core.exceptions.errors import AppError, AuthenticationError
from mkg_core.utils.logging import get_logger
from mkg_core.utils.tenant import (
    TenantContext,
    clear_tenant_context,
    extract_tenant_from_jwt,
    set_tenant_context,
)


def get_cors_headers() -> dict[str, str]:
    """Gibt CORS Headers basierend auf Environment zurück.

    Die erlaubte Origin wird aus der Umgebungsvariable CORS_ALLOWED_ORIGIN
    gelesen. Wildcards sind aus Sicherheitsgründen nicht erlaubt.

    Returns:
        Dictionary mit CORS Headers.
    """
    allowed_origin = os.environ.get("CORS_ALLOWED_ORIGIN", "")
    return {
        "Access-Control-Allow-Origin": allowed_origin,
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Correlation-Id",
        "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
    }


class BaseHandler(ABC):
    """Basis-Klasse für Lambda Event Handler.

    Bietet automatische TenantContext-Extraktion aus JWT Claims
    und einheitliches Error-Handling für API Gateway Responses.

    Example:
        >>> class CreateUserHandler(BaseHandler):
        ...     def process(self, event: dict, context: Any) -> dict:
        ...         body = self.get_json_body(event)
        ...         tenant_ctx = self.tenant_context
        ...         # Business-Logik hier...
        ...         return {"id": "usr-123", "email": body["email"]}
        ...
        >>> handler = CreateUserHandler()
        >>> # In Lambda: handler.handle(event, context)
    """

    def __init__(self) -> None:
        """Initialisiert den Handler."""
        self.logger = get_logger(self.__class__.__name__)
        self._tenant_context: TenantContext | None = None

    @property
    def tenant_context(self) -> TenantContext:
        """Gibt den aktuellen TenantContext zurück.

        Returns:
            Der TenantContext für den aktuellen Request.

        Raises:
            RuntimeError: Wenn kein TenantContext gesetzt ist.
        """
        if self._tenant_context is None:
            msg = "TenantContext not set - was handle() called?"
            raise RuntimeError(msg)
        return self._tenant_context

    @property
    def tenant_id(self) -> str:
        """Kurzform für tenant_context.tenant_id."""
        return self.tenant_context.tenant_id

    @property
    def user_id(self) -> str | None:
        """Kurzform für tenant_context.user_id."""
        return self.tenant_context.user_id

    @abstractmethod
    def process(self, event: dict[str, Any], context: Any) -> Any:
        """Verarbeitet das Event und gibt das Ergebnis zurück.

        Muss von Subklassen implementiert werden.

        Args:
            event: Das Lambda Event.
            context: Der Lambda Context.

        Returns:
            Das Ergebnis das im Response-Body zurückgegeben wird.
        """
        ...

    def handle(self, event: dict[str, Any], context: Any) -> dict[str, Any]:
        """Haupteinstiegspunkt für Lambda Handler.

        Extrahiert TenantContext, ruft process() auf und
        baut die API Gateway Response.

        Args:
            event: Das Lambda Event.
            context: Der Lambda Context.

        Returns:
            API Gateway Response Dictionary.

        Example:
            >>> def lambda_handler(event, context):
            ...     return MyHandler().handle(event, context)
        """
        try:
            # OPTIONS Request für CORS Pre-flight
            request_ctx = event.get("requestContext", {})
            http_api_method = request_ctx.get("http", {}).get("method", "")
            http_method = event.get("httpMethod") or http_api_method
            if http_method == "OPTIONS":
                return self._build_response(204, None)

            # TenantContext extrahieren und setzen
            self._tenant_context = self._extract_tenant_context(event)
            set_tenant_context(self._tenant_context)

            # Request loggen
            self.logger.info(
                "Processing request",
                method=http_method,
                path=event.get("path", event.get("rawPath", "")),
                tenant_id=self._tenant_context.tenant_id,
                correlation_id=self._tenant_context.correlation_id,
            )

            # Business-Logik aufrufen
            result = self.process(event, context)

            # Erfolgreiche Response
            return self._build_response(200, result)

        except AppError as e:
            return self._handle_app_error(e)

        except Exception as e:
            return self._handle_unexpected_error(e)

        finally:
            # TenantContext aufräumen
            clear_tenant_context()
            self._tenant_context = None

    def _extract_tenant_context(self, event: dict[str, Any]) -> TenantContext:
        """Extrahiert TenantContext aus dem Event.

        Unterstützt:
        - API Gateway v1 (REST API)
        - API Gateway v2 (HTTP API)
        - Direct Lambda Invocation mit context Parameter

        Args:
            event: Das Lambda Event.

        Returns:
            Der extrahierte TenantContext.

        Raises:
            AuthenticationError: Wenn keine gültigen Claims gefunden werden.
        """
        claims = self._get_jwt_claims(event)

        if not claims:
            # Prüfe auf direkt übergebenen Context (für Tests/interne Aufrufe)
            direct_context = event.get("context", {})
            if direct_context.get("tenant_id"):
                return TenantContext(
                    tenant_id=direct_context["tenant_id"],
                    user_id=direct_context.get("user_id"),
                    correlation_id=direct_context.get("correlation_id", ""),
                    roles=tuple(direct_context.get("roles", [])),
                )

            raise AuthenticationError("No valid authentication found")

        # Correlation-ID aus Header oder generieren
        correlation_id = self._get_correlation_id(event)

        # TenantContext aus JWT Claims erstellen
        ctx = extract_tenant_from_jwt(claims)

        # Correlation-ID überschreiben wenn aus Header
        if correlation_id:
            return TenantContext(
                tenant_id=ctx.tenant_id,
                user_id=ctx.user_id,
                correlation_id=correlation_id,
                roles=ctx.roles,
            )

        return ctx

    def _get_jwt_claims(self, event: dict[str, Any]) -> dict[str, Any]:
        """Extrahiert JWT Claims aus dem Event.

        Args:
            event: Das Lambda Event.

        Returns:
            Die JWT Claims oder leeres Dictionary.
        """
        # API Gateway v1 (REST API) mit Cognito Authorizer
        claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {})
        if claims:
            return dict(claims)

        # API Gateway v2 (HTTP API) mit JWT Authorizer
        jwt_claims = (
            event.get("requestContext", {})
            .get("authorizer", {})
            .get("jwt", {})
            .get("claims", {})
        )
        if jwt_claims:
            return dict(jwt_claims)

        # Lambda Authorizer context
        auth_context = event.get("requestContext", {}).get("authorizer", {})
        if auth_context and "principalId" in auth_context:
            return dict(auth_context)

        return {}

    def _get_correlation_id(self, event: dict[str, Any]) -> str | None:
        """Extrahiert Correlation-ID aus Request Headers.

        Args:
            event: Das Lambda Event.

        Returns:
            Die Correlation-ID oder None.
        """
        headers = event.get("headers") or {}
        # Header-Namen case-insensitive
        headers_lower = {k.lower(): v for k, v in headers.items()}
        return headers_lower.get("x-correlation-id") or headers_lower.get(
            "x-request-id"
        )

    def _build_response(
        self,
        status_code: int,
        body: Any,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Baut eine API Gateway Response.

        Args:
            status_code: HTTP Status Code.
            body: Der Response Body (wird zu JSON serialisiert).
            headers: Zusätzliche Response Headers.

        Returns:
            API Gateway Response Dictionary.
        """
        response_headers = get_cors_headers()
        if headers:
            response_headers.update(headers)

        response: dict[str, Any] = {
            "statusCode": status_code,
            "headers": response_headers,
        }

        if body is not None:
            response["body"] = json.dumps(body, default=str)
            response["headers"]["Content-Type"] = "application/json"

        return response

    def _handle_app_error(self, error: AppError) -> dict[str, Any]:
        """Behandelt bekannte Anwendungsfehler.

        Args:
            error: Die AppError.

        Returns:
            API Gateway Response mit Fehlerdetails.
        """
        self.logger.warning(
            "Application error",
            error_code=error.error_code,
            message=error.message,
            details=error.details,
            status_code=error.status_code,
        )

        return self._build_response(error.status_code, error.to_dict())

    def _handle_unexpected_error(self, error: Exception) -> dict[str, Any]:
        """Behandelt unerwartete Fehler.

        Args:
            error: Die Exception.

        Returns:
            API Gateway Response mit generischer Fehlermeldung.
        """
        self.logger.error(
            "Unexpected error",
            error_type=type(error).__name__,
            error_message=str(error),
            traceback=traceback.format_exc(),
        )

        # Keine Details an Client leaken
        return self._build_response(
            500,
            {
                "error_code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {},
            },
        )

    # === Helper Methods ===

    def get_json_body(self, event: dict[str, Any]) -> dict[str, Any]:
        """Parst den JSON Body aus dem Event.

        Args:
            event: Das Lambda Event.

        Returns:
            Der geparste Body als Dictionary.

        Raises:
            ValidationError: Bei ungültigem JSON.
        """
        from mkg_core.exceptions.errors import ValidationError

        body = event.get("body")
        if not body:
            return {}

        try:
            if isinstance(body, str):
                return dict(json.loads(body))
            return dict(body)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON body: {e}") from e

    def get_path_parameter(
        self,
        event: dict[str, Any],
        name: str,
        *,
        required: bool = True,
    ) -> str | None:
        """Holt einen Path Parameter aus dem Event.

        Args:
            event: Das Lambda Event.
            name: Name des Parameters.
            required: Ob der Parameter erforderlich ist.

        Returns:
            Der Parameter-Wert oder None.

        Raises:
            ValidationError: Wenn required=True und Parameter fehlt.
        """
        from mkg_core.exceptions.errors import ValidationError

        params = event.get("pathParameters") or {}
        value = params.get(name)

        if required and not value:
            raise ValidationError(f"Missing path parameter: {name}", field=name)

        return value

    def get_query_parameter(
        self,
        event: dict[str, Any],
        name: str,
        *,
        default: str | None = None,
    ) -> str | None:
        """Holt einen Query Parameter aus dem Event.

        Args:
            event: Das Lambda Event.
            name: Name des Parameters.
            default: Default-Wert wenn nicht vorhanden.

        Returns:
            Der Parameter-Wert oder Default.
        """
        params = event.get("queryStringParameters") or {}
        return params.get(name, default)
