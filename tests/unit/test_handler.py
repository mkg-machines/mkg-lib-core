"""Tests für BaseHandler."""

import json
import os
from typing import Any

import pytest

from mkg_core.base.handler import BaseHandler, get_cors_headers
from mkg_core.exceptions.errors import (
    AuthenticationError,
    NotFoundError,
    ValidationError,
)


class TestGetCorsHeaders:
    """Tests für get_cors_headers Funktion."""

    def test_returns_cors_headers_from_env(self, mocker):
        """CORS headers werden aus Environment gelesen."""
        mocker.patch.dict(os.environ, {"CORS_ALLOWED_ORIGIN": "https://example.com"})
        headers = get_cors_headers()

        assert headers["Access-Control-Allow-Origin"] == "https://example.com"
        assert "Content-Type" in headers["Access-Control-Allow-Headers"]
        assert "Authorization" in headers["Access-Control-Allow-Headers"]
        assert "GET" in headers["Access-Control-Allow-Methods"]

    def test_returns_empty_origin_when_not_set(self, mocker):
        """Leere Origin wenn Umgebungsvariable nicht gesetzt."""
        mocker.patch.dict(os.environ, {}, clear=True)
        os.environ.pop("CORS_ALLOWED_ORIGIN", None)
        headers = get_cors_headers()

        assert headers["Access-Control-Allow-Origin"] == ""


class ConcreteHandler(BaseHandler):
    """Konkrete Handler-Implementierung für Tests."""

    def __init__(self, return_value: Any = None, raise_error: Exception | None = None):
        super().__init__()
        self._return_value = return_value
        self._raise_error = raise_error

    def process(self, event: dict, context: Any) -> Any:
        if self._raise_error:
            raise self._raise_error
        return self._return_value


class TestBaseHandler:
    """Tests für BaseHandler Klasse."""

    @pytest.fixture
    def handler(self):
        """Erstellt einen Test-Handler."""
        return ConcreteHandler(return_value={"message": "success"})

    @pytest.fixture
    def api_gateway_v1_event(self):
        """API Gateway v1 Event mit Cognito Claims."""
        return {
            "httpMethod": "GET",
            "path": "/users/123",
            "requestContext": {
                "authorizer": {
                    "claims": {
                        "custom:tenant_id": "tnt-123",
                        "sub": "usr-456",
                        "cognito:groups": "admin,user",
                    }
                }
            },
            "headers": {
                "X-Correlation-Id": "corr-789",
            },
        }

    @pytest.fixture
    def api_gateway_v2_event(self):
        """API Gateway v2 (HTTP API) Event."""
        return {
            "requestContext": {
                "http": {"method": "POST"},
                "authorizer": {
                    "jwt": {
                        "claims": {
                            "custom:tenant_id": "tnt-abc",
                            "sub": "usr-def",
                        }
                    }
                },
            },
            "rawPath": "/items",
            "headers": {},
        }

    @pytest.fixture
    def direct_context_event(self):
        """Event mit direktem Context für interne Aufrufe."""
        return {
            "httpMethod": "GET",
            "path": "/test",
            "context": {
                "tenant_id": "tnt-direct",
                "user_id": "usr-direct",
                "correlation_id": "corr-direct",
                "roles": ["admin"],
            },
            "headers": {},
        }

    def test_handle_options_returns_204(self, handler):
        """OPTIONS Request gibt 204 zurück für CORS Pre-flight."""
        event = {"httpMethod": "OPTIONS"}
        response = handler.handle(event, None)

        assert response["statusCode"] == 204
        assert "Access-Control-Allow-Origin" in response["headers"]

    def test_handle_options_http_api(self, handler):
        """OPTIONS Request über HTTP API v2."""
        event = {"requestContext": {"http": {"method": "OPTIONS"}}}
        response = handler.handle(event, None)

        assert response["statusCode"] == 204

    def test_handle_successful_request_v1(self, handler, api_gateway_v1_event, mocker):
        """Erfolgreicher Request mit API Gateway v1."""
        mocker.patch.dict(os.environ, {"CORS_ALLOWED_ORIGIN": "https://app.example.com"})
        response = handler.handle(api_gateway_v1_event, None)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["message"] == "success"

    def test_handle_successful_request_v2(self, handler, api_gateway_v2_event, mocker):
        """Erfolgreicher Request mit API Gateway v2."""
        mocker.patch.dict(os.environ, {"CORS_ALLOWED_ORIGIN": "https://app.example.com"})
        response = handler.handle(api_gateway_v2_event, None)

        assert response["statusCode"] == 200

    def test_handle_direct_context(self, handler, direct_context_event, mocker):
        """Handler mit direktem Context für interne Aufrufe."""
        mocker.patch.dict(os.environ, {"CORS_ALLOWED_ORIGIN": "https://app.example.com"})
        response = handler.handle(direct_context_event, None)

        assert response["statusCode"] == 200

    def test_handle_no_auth_raises_error(self, handler):
        """Request ohne Authentifizierung gibt 401 zurück."""
        event = {
            "httpMethod": "GET",
            "path": "/test",
            "headers": {},
        }

        response = handler.handle(event, None)

        assert response["statusCode"] == 401
        body = json.loads(response["body"])
        assert body["error_code"] == "UNAUTHORIZED"

    def test_handle_app_error(self, api_gateway_v1_event, mocker):
        """AppError wird korrekt behandelt."""
        handler = ConcreteHandler(raise_error=NotFoundError("User", entity_id="123"))
        mocker.patch.dict(os.environ, {"CORS_ALLOWED_ORIGIN": "https://app.example.com"})
        response = handler.handle(api_gateway_v1_event, None)

        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert body["error_code"] == "NOT_FOUND"

    def test_handle_validation_error(self, api_gateway_v1_event, mocker):
        """ValidationError wird korrekt behandelt."""
        handler = ConcreteHandler(raise_error=ValidationError("Invalid email", field="email"))
        mocker.patch.dict(os.environ, {"CORS_ALLOWED_ORIGIN": "https://app.example.com"})
        response = handler.handle(api_gateway_v1_event, None)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error_code"] == "VALIDATION_ERROR"

    def test_handle_unexpected_error(self, api_gateway_v1_event, mocker):
        """Unerwartete Fehler werden abgefangen und geben 500 zurück."""
        handler = ConcreteHandler(raise_error=RuntimeError("Unexpected"))
        mocker.patch.dict(os.environ, {"CORS_ALLOWED_ORIGIN": "https://app.example.com"})
        response = handler.handle(api_gateway_v1_event, None)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["error_code"] == "INTERNAL_ERROR"
        assert "Unexpected" not in body["message"]  # Keine Details leaken

    def test_tenant_context_property(self, handler, api_gateway_v1_event, mocker):
        """tenant_context Property gibt korrekten Context zurück."""
        mocker.patch.dict(os.environ, {"CORS_ALLOWED_ORIGIN": "https://app.example.com"})

        class ContextCheckHandler(BaseHandler):
            def process(self, event, context):
                assert self.tenant_context.tenant_id == "tnt-123"
                assert self.tenant_context.user_id == "usr-456"
                return {"ok": True}

        check_handler = ContextCheckHandler()
        response = check_handler.handle(api_gateway_v1_event, None)
        assert response["statusCode"] == 200

    def test_tenant_context_raises_without_handle(self, handler):
        """tenant_context wirft Fehler wenn handle() nicht aufgerufen wurde."""
        with pytest.raises(RuntimeError, match="TenantContext not set"):
            _ = handler.tenant_context

    def test_tenant_id_shortcut(self, api_gateway_v1_event, mocker):
        """tenant_id Property ist Shortcut für tenant_context.tenant_id."""

        class TenantIdCheckHandler(BaseHandler):
            def process(self, event, context):
                assert self.tenant_id == "tnt-123"
                return {"ok": True}

        mocker.patch.dict(os.environ, {"CORS_ALLOWED_ORIGIN": "https://app.example.com"})
        handler = TenantIdCheckHandler()
        handler.handle(api_gateway_v1_event, None)

    def test_user_id_shortcut(self, api_gateway_v1_event, mocker):
        """user_id Property ist Shortcut für tenant_context.user_id."""

        class UserIdCheckHandler(BaseHandler):
            def process(self, event, context):
                assert self.user_id == "usr-456"
                return {"ok": True}

        mocker.patch.dict(os.environ, {"CORS_ALLOWED_ORIGIN": "https://app.example.com"})
        handler = UserIdCheckHandler()
        handler.handle(api_gateway_v1_event, None)


class TestBaseHandlerHelpers:
    """Tests für BaseHandler Helper-Methoden."""

    @pytest.fixture
    def handler(self):
        return ConcreteHandler()

    def test_get_json_body_parses_string(self, handler):
        """get_json_body parst JSON-String."""
        event = {"body": '{"name": "Test", "value": 42}'}
        body = handler.get_json_body(event)

        assert body["name"] == "Test"
        assert body["value"] == 42

    def test_get_json_body_returns_dict_if_already_parsed(self, handler):
        """get_json_body gibt dict zurück wenn Body bereits geparst."""
        event = {"body": {"name": "Test"}}
        body = handler.get_json_body(event)

        assert body["name"] == "Test"

    def test_get_json_body_returns_empty_dict_if_no_body(self, handler):
        """get_json_body gibt leeres Dict zurück wenn kein Body."""
        event = {}
        body = handler.get_json_body(event)

        assert body == {}

    def test_get_json_body_raises_on_invalid_json(self, handler):
        """get_json_body wirft ValidationError bei ungültigem JSON."""
        event = {"body": "not valid json"}

        with pytest.raises(ValidationError, match="Invalid JSON"):
            handler.get_json_body(event)

    def test_get_path_parameter_returns_value(self, handler):
        """get_path_parameter gibt Parameter-Wert zurück."""
        event = {"pathParameters": {"userId": "123"}}
        value = handler.get_path_parameter(event, "userId")

        assert value == "123"

    def test_get_path_parameter_raises_when_required_missing(self, handler):
        """get_path_parameter wirft ValidationError wenn required fehlt."""
        event = {"pathParameters": {}}

        with pytest.raises(ValidationError, match="Missing path parameter"):
            handler.get_path_parameter(event, "userId")

    def test_get_path_parameter_returns_none_when_optional_missing(self, handler):
        """get_path_parameter gibt None zurück wenn optional fehlt."""
        event = {"pathParameters": {}}
        value = handler.get_path_parameter(event, "userId", required=False)

        assert value is None

    def test_get_path_parameter_handles_none_params(self, handler):
        """get_path_parameter behandelt None pathParameters."""
        event = {"pathParameters": None}
        value = handler.get_path_parameter(event, "userId", required=False)

        assert value is None

    def test_get_query_parameter_returns_value(self, handler):
        """get_query_parameter gibt Parameter-Wert zurück."""
        event = {"queryStringParameters": {"limit": "10"}}
        value = handler.get_query_parameter(event, "limit")

        assert value == "10"

    def test_get_query_parameter_returns_default(self, handler):
        """get_query_parameter gibt Default-Wert zurück wenn fehlt."""
        event = {"queryStringParameters": {}}
        value = handler.get_query_parameter(event, "limit", default="20")

        assert value == "20"

    def test_get_query_parameter_handles_none_params(self, handler):
        """get_query_parameter behandelt None queryStringParameters."""
        event = {"queryStringParameters": None}
        value = handler.get_query_parameter(event, "limit", default="20")

        assert value == "20"


class TestHandlerJwtExtraction:
    """Tests für JWT Claims Extraktion."""

    @pytest.fixture
    def handler(self):
        return ConcreteHandler(return_value={"ok": True})

    def test_extracts_from_cognito_authorizer(self, handler, mocker):
        """Claims werden aus Cognito Authorizer extrahiert."""
        event = {
            "httpMethod": "GET",
            "path": "/test",
            "requestContext": {
                "authorizer": {
                    "claims": {
                        "custom:tenant_id": "tnt-cognito",
                        "sub": "usr-cognito",
                    }
                }
            },
            "headers": {},
        }

        mocker.patch.dict(os.environ, {"CORS_ALLOWED_ORIGIN": "https://example.com"})
        response = handler.handle(event, None)

        assert response["statusCode"] == 200

    def test_extracts_from_jwt_authorizer(self, handler, mocker):
        """Claims werden aus JWT Authorizer extrahiert."""
        event = {
            "requestContext": {
                "http": {"method": "GET"},
                "authorizer": {
                    "jwt": {
                        "claims": {
                            "custom:tenant_id": "tnt-jwt",
                            "sub": "usr-jwt",
                        }
                    }
                },
            },
            "rawPath": "/test",
            "headers": {},
        }

        mocker.patch.dict(os.environ, {"CORS_ALLOWED_ORIGIN": "https://example.com"})
        response = handler.handle(event, None)

        assert response["statusCode"] == 200

    def test_extracts_from_lambda_authorizer(self, handler, mocker):
        """Claims werden aus Lambda Authorizer extrahiert."""
        event = {
            "httpMethod": "GET",
            "path": "/test",
            "requestContext": {
                "authorizer": {
                    "principalId": "usr-lambda",
                    "custom:tenant_id": "tnt-lambda",
                }
            },
            "headers": {},
        }

        mocker.patch.dict(os.environ, {"CORS_ALLOWED_ORIGIN": "https://example.com"})
        response = handler.handle(event, None)

        assert response["statusCode"] == 200

    def test_correlation_id_from_header(self, handler, mocker):
        """Correlation-ID wird aus Header extrahiert."""

        class CorrelationCheckHandler(BaseHandler):
            def process(self, event, context):
                assert self.tenant_context.correlation_id == "my-correlation-id"
                return {"ok": True}

        event = {
            "httpMethod": "GET",
            "path": "/test",
            "requestContext": {
                "authorizer": {
                    "claims": {
                        "custom:tenant_id": "tnt-123",
                        "sub": "usr-456",
                    }
                }
            },
            "headers": {
                "X-Correlation-Id": "my-correlation-id",
            },
        }

        mocker.patch.dict(os.environ, {"CORS_ALLOWED_ORIGIN": "https://example.com"})
        check_handler = CorrelationCheckHandler()
        response = check_handler.handle(event, None)

        assert response["statusCode"] == 200

    def test_correlation_id_from_x_request_id(self, handler, mocker):
        """Correlation-ID wird auch aus X-Request-Id Header extrahiert."""

        class CorrelationCheckHandler(BaseHandler):
            def process(self, event, context):
                assert self.tenant_context.correlation_id == "request-id-123"
                return {"ok": True}

        event = {
            "httpMethod": "GET",
            "path": "/test",
            "requestContext": {
                "authorizer": {
                    "claims": {
                        "custom:tenant_id": "tnt-123",
                        "sub": "usr-456",
                    }
                }
            },
            "headers": {
                "x-request-id": "request-id-123",
            },
        }

        mocker.patch.dict(os.environ, {"CORS_ALLOWED_ORIGIN": "https://example.com"})
        check_handler = CorrelationCheckHandler()
        response = check_handler.handle(event, None)

        assert response["statusCode"] == 200


class TestHandlerResponseBuilding:
    """Tests für Response-Building."""

    @pytest.fixture
    def handler(self):
        return ConcreteHandler()

    def test_build_response_with_body(self, handler):
        """Response mit Body hat Content-Type Header."""
        response = handler._build_response(200, {"key": "value"})

        assert response["statusCode"] == 200
        assert response["headers"]["Content-Type"] == "application/json"
        assert json.loads(response["body"]) == {"key": "value"}

    def test_build_response_without_body(self, handler):
        """Response ohne Body hat keinen body Key."""
        response = handler._build_response(204, None)

        assert response["statusCode"] == 204
        assert "body" not in response

    def test_build_response_with_custom_headers(self, handler):
        """Response mit zusätzlichen Headers."""
        response = handler._build_response(
            200, {"key": "value"}, headers={"X-Custom": "test"}
        )

        assert response["headers"]["X-Custom"] == "test"

    def test_build_response_serializes_datetime(self, handler):
        """Response serialisiert datetime Objekte."""
        from datetime import datetime

        dt = datetime(2025, 1, 15, 10, 30, 0)
        response = handler._build_response(200, {"timestamp": dt})

        body = json.loads(response["body"])
        assert "2025-01-15" in body["timestamp"]
