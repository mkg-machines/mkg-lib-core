"""Tests fuer mkg_core.exceptions.errors Modul.

Testet die Exception-Hierarchie und HTTP-Status-Mapping.
"""

from __future__ import annotations

import pytest

from mkg_core.exceptions.errors import (
    AppError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    TenantError,
    ValidationError,
)

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def sample_details() -> dict:
    """Sample details Dictionary fuer Tests."""
    return {"key1": "value1", "key2": 123}


# ============================================================
# AppError Tests
# ============================================================


class TestAppError:
    """Tests fuer die Basis-Exception AppError."""

    def test_default_values(self):
        """AppError hat korrekte Default-Werte."""
        error = AppError()

        assert error.status_code == 500
        assert error.error_code == "INTERNAL_ERROR"
        assert error.message == "An internal error occurred"
        assert error.details == {}

    def test_custom_message(self):
        """AppError akzeptiert custom Message."""
        error = AppError("Custom error message")

        assert error.message == "Custom error message"
        assert str(error) == "INTERNAL_ERROR: Custom error message"

    def test_with_details(self, sample_details):
        """AppError akzeptiert Details Dictionary."""
        error = AppError("Error", details=sample_details)

        assert error.details == sample_details
        assert "key1" in str(error)
        assert "value1" in str(error)

    def test_to_dict_without_details(self):
        """to_dict() gibt korrektes Format ohne Details zurueck."""
        error = AppError("Test message")
        result = error.to_dict()

        assert result == {
            "error_code": "INTERNAL_ERROR",
            "message": "Test message",
            "details": {},
        }

    def test_to_dict_with_details(self, sample_details):
        """to_dict() inkludiert Details wenn vorhanden."""
        error = AppError("Test message", details=sample_details)
        result = error.to_dict()

        assert result["details"] == sample_details

    def test_str_without_details(self):
        """__str__ formatiert korrekt ohne Details."""
        error = AppError("Test message")

        assert str(error) == "INTERNAL_ERROR: Test message"

    def test_str_with_details(self):
        """__str__ inkludiert Details wenn vorhanden."""
        error = AppError("Test message", details={"foo": "bar"})

        assert str(error) == "INTERNAL_ERROR: Test message ({'foo': 'bar'})"

    def test_is_exception(self):
        """AppError ist eine Exception und kann raised werden."""
        with pytest.raises(AppError) as exc_info:
            raise AppError("Test error")

        assert exc_info.value.message == "Test error"

    def test_exception_args(self):
        """Exception args enthalten die Message."""
        error = AppError("Test message")

        assert error.args == ("Test message",)


# ============================================================
# ValidationError Tests
# ============================================================


class TestValidationError:
    """Tests fuer ValidationError."""

    def test_status_code(self):
        """ValidationError hat HTTP 400 Status."""
        error = ValidationError()

        assert error.status_code == 400
        assert error.error_code == "VALIDATION_ERROR"

    def test_default_message(self):
        """ValidationError hat korrekte Default-Message."""
        error = ValidationError()

        assert error.message == "Validation failed"

    def test_custom_message(self):
        """ValidationError akzeptiert custom Message."""
        error = ValidationError("Email is invalid")

        assert error.message == "Email is invalid"

    def test_with_field(self):
        """ValidationError akzeptiert field Parameter."""
        error = ValidationError("Invalid format", field="email")

        assert error.details["field"] == "email"

    def test_with_field_and_details(self):
        """field wird zu bestehenden Details hinzugefuegt."""
        error = ValidationError(
            "Invalid format",
            field="email",
            details={"min_length": 5},
        )

        assert error.details["field"] == "email"
        assert error.details["min_length"] == 5

    def test_to_dict_includes_field(self):
        """to_dict() inkludiert field in Details."""
        error = ValidationError("Invalid", field="username")
        result = error.to_dict()

        assert result["details"]["field"] == "username"

    @pytest.mark.parametrize(
        ("message", "field", "expected_message"),
        [
            ("Invalid email", "email", "Invalid email"),
            ("Too short", "password", "Too short"),
            ("Required", "name", "Required"),
        ],
    )
    def test_various_fields(self, message, field, expected_message):
        """ValidationError funktioniert mit verschiedenen Feldern."""
        error = ValidationError(message, field=field)

        assert error.message == expected_message
        assert error.details["field"] == field


# ============================================================
# NotFoundError Tests
# ============================================================


class TestNotFoundError:
    """Tests fuer NotFoundError."""

    def test_status_code(self):
        """NotFoundError hat HTTP 404 Status."""
        error = NotFoundError()

        assert error.status_code == 404
        assert error.error_code == "NOT_FOUND"

    def test_default_message(self):
        """NotFoundError generiert Message aus Resource Type."""
        error = NotFoundError()

        assert error.message == "Resource not found"

    def test_custom_resource_type(self):
        """NotFoundError akzeptiert custom Resource Type."""
        error = NotFoundError("User")

        assert error.message == "User not found"

    def test_with_entity_id(self):
        """NotFoundError akzeptiert entity_id Parameter."""
        error = NotFoundError("Product", entity_id="prod-123")

        assert error.details["entity_id"] == "prod-123"

    def test_message_format(self):
        """Message wird korrekt formatiert."""
        error = NotFoundError("Order", entity_id="ord-456")

        assert error.message == "Order not found"
        assert error.details["entity_id"] == "ord-456"

    @pytest.mark.parametrize(
        ("resource_type", "entity_id", "expected_message"),
        [
            ("User", "usr-123", "User not found"),
            ("Product", "prod-456", "Product not found"),
            ("Invoice", None, "Invoice not found"),
        ],
    )
    def test_various_resource_types(self, resource_type, entity_id, expected_message):
        """NotFoundError funktioniert mit verschiedenen Resource Types."""
        error = NotFoundError(resource_type, entity_id=entity_id)

        assert error.message == expected_message


# ============================================================
# AuthorizationError Tests
# ============================================================


class TestAuthorizationError:
    """Tests fuer AuthorizationError."""

    def test_status_code(self):
        """AuthorizationError hat HTTP 403 Status."""
        error = AuthorizationError()

        assert error.status_code == 403
        assert error.error_code == "FORBIDDEN"

    def test_default_message(self):
        """AuthorizationError hat korrekte Default-Message."""
        error = AuthorizationError()

        assert error.message == "You are not authorized to perform this action"

    def test_custom_message(self):
        """AuthorizationError akzeptiert custom Message."""
        error = AuthorizationError("Admin access required")

        assert error.message == "Admin access required"

    def test_with_required_permission(self):
        """AuthorizationError akzeptiert required_permission Parameter."""
        error = AuthorizationError(
            "Missing permission",
            required_permission="admin:write",
        )

        assert error.details["required_permission"] == "admin:write"

    def test_with_permission_and_details(self):
        """required_permission wird zu Details hinzugefuegt."""
        error = AuthorizationError(
            "Access denied",
            required_permission="read:users",
            details={"attempted_action": "list"},
        )

        assert error.details["required_permission"] == "read:users"
        assert error.details["attempted_action"] == "list"


# ============================================================
# AuthenticationError Tests
# ============================================================


class TestAuthenticationError:
    """Tests fuer AuthenticationError."""

    def test_status_code(self):
        """AuthenticationError hat HTTP 401 Status."""
        error = AuthenticationError()

        assert error.status_code == 401
        assert error.error_code == "UNAUTHORIZED"

    def test_default_message(self):
        """AuthenticationError hat korrekte Default-Message."""
        error = AuthenticationError()

        assert error.message == "Authentication required"

    def test_custom_message(self):
        """AuthenticationError akzeptiert custom Message."""
        error = AuthenticationError("Token expired")

        assert error.message == "Token expired"

    def test_with_details(self):
        """AuthenticationError akzeptiert Details."""
        error = AuthenticationError(
            "Invalid token",
            details={"reason": "expired"},
        )

        assert error.details["reason"] == "expired"


# ============================================================
# ConflictError Tests
# ============================================================


class TestConflictError:
    """Tests fuer ConflictError."""

    def test_status_code(self):
        """ConflictError hat HTTP 409 Status."""
        error = ConflictError()

        assert error.status_code == 409
        assert error.error_code == "CONFLICT"

    def test_default_message(self):
        """ConflictError hat korrekte Default-Message."""
        error = ConflictError()

        assert error.message == "Resource conflict"

    def test_custom_message(self):
        """ConflictError akzeptiert custom Message."""
        error = ConflictError("Email already exists")

        assert error.message == "Email already exists"

    def test_with_field(self):
        """ConflictError akzeptiert field Parameter."""
        error = ConflictError("Duplicate entry", field="email")

        assert error.details["field"] == "email"

    def test_with_field_and_details(self):
        """field wird zu bestehenden Details hinzugefuegt."""
        error = ConflictError(
            "Already exists",
            field="username",
            details={"existing_id": "usr-123"},
        )

        assert error.details["field"] == "username"
        assert error.details["existing_id"] == "usr-123"


# ============================================================
# TenantError Tests
# ============================================================


class TestTenantError:
    """Tests fuer TenantError."""

    def test_status_code(self):
        """TenantError hat HTTP 403 Status."""
        error = TenantError()

        assert error.status_code == 403
        assert error.error_code == "TENANT_ERROR"

    def test_default_message(self):
        """TenantError hat korrekte Default-Message."""
        error = TenantError()

        assert error.message == "Tenant access denied"

    def test_custom_message(self):
        """TenantError akzeptiert custom Message."""
        error = TenantError("Cross-tenant access not allowed")

        assert error.message == "Cross-tenant access not allowed"

    def test_with_tenant_id(self):
        """TenantError akzeptiert tenant_id Parameter."""
        error = TenantError("Access denied", tenant_id="tnt-123")

        assert error.details["tenant_id"] == "tnt-123"

    def test_with_tenant_id_and_details(self):
        """tenant_id wird zu bestehenden Details hinzugefuegt."""
        error = TenantError(
            "Forbidden",
            tenant_id="tnt-456",
            details={"requested_resource": "prod-789"},
        )

        assert error.details["tenant_id"] == "tnt-456"
        assert error.details["requested_resource"] == "prod-789"


# ============================================================
# Exception Hierarchy Tests
# ============================================================


class TestExceptionHierarchy:
    """Tests fuer die Exception-Hierarchie."""

    @pytest.mark.parametrize(
        ("exception_class", "expected_status"),
        [
            (AppError, 500),
            (ValidationError, 400),
            (NotFoundError, 404),
            (AuthorizationError, 403),
            (AuthenticationError, 401),
            (ConflictError, 409),
            (TenantError, 403),
        ],
    )
    def test_status_codes(self, exception_class, expected_status):
        """Alle Exceptions haben korrekte HTTP Status Codes."""
        assert exception_class.status_code == expected_status

    @pytest.mark.parametrize(
        "exception_class",
        [
            ValidationError,
            NotFoundError,
            AuthorizationError,
            AuthenticationError,
            ConflictError,
            TenantError,
        ],
    )
    def test_all_inherit_from_app_error(self, exception_class):
        """Alle Exceptions erben von AppError."""
        assert issubclass(exception_class, AppError)

    @pytest.mark.parametrize(
        "exception_class",
        [
            AppError,
            ValidationError,
            NotFoundError,
            AuthorizationError,
            AuthenticationError,
            ConflictError,
            TenantError,
        ],
    )
    def test_all_inherit_from_exception(self, exception_class):
        """Alle Custom Exceptions erben von Exception."""
        assert issubclass(exception_class, Exception)

    def test_can_catch_all_as_app_error(self):
        """Alle spezifischen Exceptions koennen als AppError gefangen werden."""
        exceptions = [
            ValidationError("test"),
            NotFoundError("Resource"),
            AuthorizationError("test"),
            AuthenticationError("test"),
            ConflictError("test"),
            TenantError("test"),
        ]

        for exc in exceptions:
            try:
                raise exc
            except AppError as caught:
                assert caught.message is not None
