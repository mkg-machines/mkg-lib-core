"""Tests für Tenant Utilities."""

import threading

import pytest

from mkg_core.utils.tenant import (
    TenantContext,
    TenantContextError,
    TenantNotSetError,
    clear_tenant_context,
    extract_tenant_from_jwt,
    get_current_tenant,
    get_current_tenant_id,
    require_current_tenant,
    require_tenant,
    set_tenant_context,
    tenant_context,
    with_tenant_context,
)


class TestTenantContext:
    """Tests für TenantContext Dataclass."""

    def test_tenant_context_creation(self):
        """TenantContext kann erstellt werden."""
        ctx = TenantContext(
            tenant_id="tnt-123",
            user_id="usr-456",
            correlation_id="corr-789",
            roles=("admin", "user"),
        )

        assert ctx.tenant_id == "tnt-123"
        assert ctx.user_id == "usr-456"
        assert ctx.correlation_id == "corr-789"
        assert ctx.roles == ("admin", "user")

    def test_tenant_context_optional_user_id(self):
        """user_id ist optional."""
        ctx = TenantContext(
            tenant_id="tnt-123",
            correlation_id="corr-789",
        )

        assert ctx.tenant_id == "tnt-123"
        assert ctx.user_id is None

    def test_tenant_context_default_roles(self):
        """roles hat leere Tuple als Default."""
        ctx = TenantContext(
            tenant_id="tnt-123",
            correlation_id="corr-789",
        )

        assert ctx.roles == ()

    def test_tenant_context_is_frozen(self):
        """TenantContext ist immutable."""
        ctx = TenantContext(
            tenant_id="tnt-123",
            correlation_id="corr-789",
        )

        with pytest.raises(AttributeError):
            ctx.tenant_id = "other"


class TestTenantContextMethods:
    """Tests für TenantContext Methoden."""

    def test_has_role_returns_true(self):
        """has_role gibt True zurück wenn Rolle vorhanden."""
        ctx = TenantContext(
            tenant_id="tnt-123",
            correlation_id="corr-789",
            roles=("admin", "user"),
        )

        assert ctx.has_role("admin") is True
        assert ctx.has_role("user") is True

    def test_has_role_returns_false(self):
        """has_role gibt False zurück wenn Rolle nicht vorhanden."""
        ctx = TenantContext(
            tenant_id="tnt-123",
            correlation_id="corr-789",
            roles=("user",),
        )

        assert ctx.has_role("admin") is False

    def test_to_dict(self):
        """to_dict konvertiert zu Dictionary."""
        ctx = TenantContext(
            tenant_id="tnt-123",
            user_id="usr-456",
            correlation_id="corr-789",
            roles=("admin",),
        )

        result = ctx.to_dict()

        assert result["tenant_id"] == "tnt-123"
        assert result["user_id"] == "usr-456"
        assert result["correlation_id"] == "corr-789"
        assert result["roles"] == ["admin"]


class TestExtractTenantFromJwt:
    """Tests für extract_tenant_from_jwt Funktion."""

    def test_extracts_from_cognito_claims(self):
        """Extrahiert aus Cognito-Format Claims."""
        claims = {
            "custom:tenant_id": "tnt-123",
            "sub": "usr-456",
            "cognito:groups": ["admin", "user"],
        }

        ctx = extract_tenant_from_jwt(claims)

        assert ctx.tenant_id == "tnt-123"
        assert ctx.user_id == "usr-456"
        assert "admin" in ctx.roles
        assert "user" in ctx.roles

    def test_extracts_from_standard_claims(self):
        """Extrahiert aus Standard JWT Claims."""
        claims = {
            "tenant_id": "tnt-123",
            "sub": "usr-456",
        }

        ctx = extract_tenant_from_jwt(claims)

        assert ctx.tenant_id == "tnt-123"
        assert ctx.user_id == "usr-456"

    def test_extracts_roles_as_list(self):
        """Extrahiert Rollen wenn als Liste übergeben."""
        claims = {
            "custom:tenant_id": "tnt-123",
            "sub": "usr-456",
            "cognito:groups": ["admin", "user"],
        }

        ctx = extract_tenant_from_jwt(claims)

        assert "admin" in ctx.roles
        assert "user" in ctx.roles

    def test_generates_correlation_id(self):
        """Generiert Correlation-ID wenn nicht vorhanden."""
        claims = {
            "custom:tenant_id": "tnt-123",
            "sub": "usr-456",
        }

        ctx = extract_tenant_from_jwt(claims)

        assert ctx.correlation_id != ""
        assert len(ctx.correlation_id) > 0

    def test_raises_for_missing_tenant_id(self):
        """Wirft Fehler wenn tenant_id fehlt."""
        claims = {
            "sub": "usr-456",
        }

        with pytest.raises(TenantContextError):
            extract_tenant_from_jwt(claims)

    def test_handles_string_groups(self):
        """Behandelt Rollen als String."""
        claims = {
            "custom:tenant_id": "tnt-123",
            "sub": "usr-456",
            "cognito:groups": "admin",
        }

        ctx = extract_tenant_from_jwt(claims)

        assert "admin" in ctx.roles

    def test_extracts_from_lambda_authorizer(self):
        """Extrahiert aus Lambda Authorizer Context."""
        claims = {
            "principalId": "usr-456",
            "custom:tenant_id": "tnt-123",
        }

        ctx = extract_tenant_from_jwt(claims)

        assert ctx.tenant_id == "tnt-123"

class TestTenantContextThreadLocal:
    """Tests für Thread-lokalen TenantContext."""

    def teardown_method(self):
        """Cleanup nach jedem Test."""
        clear_tenant_context()

    def test_set_and_get_tenant_context(self):
        """set_tenant_context und get_current_tenant funktionieren."""
        ctx = TenantContext(
            tenant_id="tnt-123",
            correlation_id="corr-789",
        )

        set_tenant_context(ctx)
        retrieved = get_current_tenant()

        assert retrieved is not None
        assert retrieved.tenant_id == "tnt-123"

    def test_get_current_tenant_returns_none_when_not_set(self):
        """get_current_tenant gibt None zurück wenn nicht gesetzt."""
        clear_tenant_context()
        retrieved = get_current_tenant()

        assert retrieved is None

    def test_get_current_tenant_id(self):
        """get_current_tenant_id gibt nur ID zurück."""
        ctx = TenantContext(tenant_id="tnt-123", correlation_id="corr-789")
        set_tenant_context(ctx)

        tenant_id = get_current_tenant_id()

        assert tenant_id == "tnt-123"

    def test_get_current_tenant_id_returns_none(self):
        """get_current_tenant_id gibt None zurück wenn nicht gesetzt."""
        clear_tenant_context()

        tenant_id = get_current_tenant_id()

        assert tenant_id is None

    def test_require_current_tenant(self):
        """require_current_tenant gibt Context zurück."""
        ctx = TenantContext(tenant_id="tnt-123", correlation_id="corr-789")
        set_tenant_context(ctx)

        result = require_current_tenant()

        assert result.tenant_id == "tnt-123"

    def test_require_current_tenant_raises(self):
        """require_current_tenant wirft wenn nicht gesetzt."""
        clear_tenant_context()

        with pytest.raises(TenantNotSetError):
            require_current_tenant()

    def test_clear_tenant_context(self):
        """clear_tenant_context entfernt Context."""
        ctx = TenantContext(
            tenant_id="tnt-123",
            correlation_id="corr-789",
        )
        set_tenant_context(ctx)
        clear_tenant_context()

        retrieved = get_current_tenant()
        assert retrieved is None

    def test_tenant_context_is_thread_local(self):
        """TenantContext ist Thread-lokal."""
        main_ctx = TenantContext(tenant_id="main", correlation_id="main")
        set_tenant_context(main_ctx)

        thread_context = [None]

        def thread_func():
            # Im neuen Thread sollte kein Context gesetzt sein
            thread_context[0] = get_current_tenant()
            # Setze anderen Context im Thread
            set_tenant_context(
                TenantContext(tenant_id="thread", correlation_id="thread")
            )

        thread = threading.Thread(target=thread_func)
        thread.start()
        thread.join()

        # Thread sollte keinen Context gehabt haben
        assert thread_context[0] is None

        # Main-Thread-Context sollte unverändert sein
        main_retrieved = get_current_tenant()
        assert main_retrieved is not None
        assert main_retrieved.tenant_id == "main"


class TestTenantContextValidation:
    """Tests für TenantContext Validierung."""

    def test_tenant_id_cannot_be_empty(self):
        """tenant_id darf nicht leer sein."""
        with pytest.raises(TenantContextError):
            extract_tenant_from_jwt({})

    def test_accepts_valid_tenant_id_format(self):
        """Akzeptiert gültiges tenant_id Format."""
        claims = {
            "custom:tenant_id": "tnt-valid-123",
            "sub": "usr-456",
        }

        ctx = extract_tenant_from_jwt(claims)

        assert ctx.tenant_id == "tnt-valid-123"


class TestTenantContextRoles:
    """Tests für Rollen-Handling."""

    def test_roles_from_list(self):
        """Rollen werden aus Liste übernommen."""
        claims = {
            "custom:tenant_id": "tnt-123",
            "sub": "usr-456",
            "cognito:groups": ["role1", "role2", "role3"],
        }

        ctx = extract_tenant_from_jwt(claims)

        assert len(ctx.roles) == 3
        assert "role1" in ctx.roles
        assert "role2" in ctx.roles
        assert "role3" in ctx.roles

    def test_empty_roles_produces_empty_tuple(self):
        """Keine Rollen ergibt leeres Tuple."""
        claims = {
            "custom:tenant_id": "tnt-123",
            "sub": "usr-456",
        }

        ctx = extract_tenant_from_jwt(claims)

        assert ctx.roles == ()


class TestTenantContextManager:
    """Tests für tenant_context Context Manager."""

    def teardown_method(self):
        """Cleanup nach jedem Test."""
        clear_tenant_context()

    def test_context_manager_sets_context(self):
        """Context Manager setzt Context."""
        with tenant_context("tnt-123", user_id="usr-456") as ctx:
            assert ctx.tenant_id == "tnt-123"
            assert ctx.user_id == "usr-456"

    def test_context_manager_clears_on_exit(self):
        """Context Manager räumt auf bei Exit."""
        with tenant_context("tnt-123"):
            pass

        # Nach dem with-Block sollte Context wieder None sein
        assert get_current_tenant() is None

    def test_context_manager_with_roles(self):
        """Context Manager mit Rollen."""
        with tenant_context("tnt-123", roles=("admin", "user")) as ctx:
            assert "admin" in ctx.roles
            assert "user" in ctx.roles

    def test_context_manager_with_extra(self):
        """Context Manager mit Extra-Daten."""
        with tenant_context("tnt-123", custom_field="value") as ctx:
            assert ctx.extra["custom_field"] == "value"

    def test_context_manager_with_correlation_id(self):
        """Context Manager mit Correlation-ID."""
        with tenant_context("tnt-123", correlation_id="my-corr-id") as ctx:
            assert ctx.correlation_id == "my-corr-id"

    def test_context_manager_generates_correlation_id(self):
        """Context Manager generiert Correlation-ID wenn nicht angegeben."""
        with tenant_context("tnt-123") as ctx:
            assert ctx.correlation_id.startswith("req-")


class TestWithTenantContext:
    """Tests für with_tenant_context Funktion."""

    def teardown_method(self):
        """Cleanup nach jedem Test."""
        clear_tenant_context()

    def test_with_tenant_context(self):
        """with_tenant_context funktioniert als Context Manager."""
        with with_tenant_context("tnt-123", user_id="usr-456") as ctx:
            assert ctx.tenant_id == "tnt-123"
            assert ctx.user_id == "usr-456"

    def test_with_tenant_context_clears_on_exit(self):
        """with_tenant_context räumt auf."""
        with with_tenant_context("tnt-123"):
            pass

        assert get_current_tenant() is None


class TestRequireTenantDecorator:
    """Tests für require_tenant Decorator."""

    def teardown_method(self):
        """Cleanup nach jedem Test."""
        clear_tenant_context()

    def test_require_tenant_passes_when_set(self):
        """require_tenant lässt durch wenn Context gesetzt."""

        @require_tenant
        def my_func() -> str:
            return "success"

        set_tenant_context(TenantContext(tenant_id="tnt-123"))

        result = my_func()
        assert result == "success"

    def test_require_tenant_raises_when_not_set(self):
        """require_tenant wirft wenn Context nicht gesetzt."""

        @require_tenant
        def my_func() -> str:
            return "success"

        clear_tenant_context()

        with pytest.raises(TenantNotSetError):
            my_func()

    def test_require_tenant_preserves_function_name(self):
        """require_tenant erhält Funktionsnamen."""

        @require_tenant
        def my_named_function() -> str:
            return "success"

        assert my_named_function.__name__ == "my_named_function"


class TestTenantNotSetError:
    """Tests für TenantNotSetError."""

    def test_default_message(self):
        """TenantNotSetError hat Default-Nachricht."""
        error = TenantNotSetError()

        assert "not set" in str(error).lower()

    def test_custom_message(self):
        """TenantNotSetError akzeptiert Custom-Nachricht."""
        error = TenantNotSetError("Custom message")

        assert str(error) == "Custom message"
