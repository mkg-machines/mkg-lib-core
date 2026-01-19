"""Tests für Secrets Manager Client."""

import json
import time

import boto3
import pytest
from moto import mock_aws

from mkg_core.clients.secrets import (
    DEFAULT_CACHE_TTL,
    SecretsClient,
    get_secrets_client,
)


@pytest.fixture
def secrets_setup():
    """Setup für Secrets Manager Tests."""
    with mock_aws():
        client = boto3.client("secretsmanager", region_name="eu-central-1")
        # String secret
        client.create_secret(Name="test/string-secret", SecretString="my-secret-value")
        # JSON secret
        client.create_secret(
            Name="test/json-secret",
            SecretString=json.dumps({"host": "localhost", "port": 5432}),
        )
        # Binary secret
        client.create_secret(Name="test/binary-secret", SecretBinary=b"binary-data")
        yield


@pytest.fixture
def secrets_client(secrets_setup):
    """Erstellt einen SecretsClient für Tests."""
    with mock_aws():
        SecretsClient._instances.clear()
        client = SecretsClient(region="eu-central-1", cache_ttl=300)
        yield client


class TestSecretsClientInit:
    """Tests für SecretsClient Initialisierung."""

    def test_init_with_region(self):
        """Client wird mit expliziter Region initialisiert."""
        client = SecretsClient(region="us-west-2", cache_ttl=600)

        assert client._region == "us-west-2"
        assert client._cache_ttl == 600

    def test_init_uses_env_region(self, mocker):
        """Client verwendet AWS_REGION aus Environment."""
        mocker.patch.dict("os.environ", {"AWS_REGION": "ap-northeast-1"})
        client = SecretsClient()

        assert client._region == "ap-northeast-1"

    def test_init_uses_default_cache_ttl(self):
        """Client verwendet Default-Cache-TTL."""
        client = SecretsClient()

        assert client._cache_ttl == DEFAULT_CACHE_TTL


class TestSecretsClientCaching:
    """Tests für Cache-Funktionalität."""

    def test_get_from_cache_returns_cached_value(self, secrets_client):
        """Cache gibt gecachten Wert zurück wenn gültig."""
        secrets_client._cache["test-key"] = ("cached-value", time.time())

        result = secrets_client._get_from_cache("test-key")

        assert result == "cached-value"

    def test_get_from_cache_returns_none_when_expired(self, secrets_client):
        """Cache gibt None zurück wenn abgelaufen."""
        secrets_client._cache["test-key"] = (
            "cached-value",
            time.time() - 400,
        )  # Älter als TTL

        result = secrets_client._get_from_cache("test-key")

        assert result is None

    def test_get_from_cache_returns_none_when_not_cached(self, secrets_client):
        """Cache gibt None zurück wenn nicht gecacht."""
        result = secrets_client._get_from_cache("nonexistent")

        assert result is None

    def test_set_cache_stores_value(self, secrets_client):
        """set_cache speichert Wert im Cache."""
        secrets_client._set_cache("test-key", "test-value")

        assert "test-key" in secrets_client._cache
        value, timestamp = secrets_client._cache["test-key"]
        assert value == "test-value"
        assert timestamp <= time.time()

    def test_clear_cache_removes_all(self, secrets_client):
        """clear_cache löscht gesamten Cache."""
        secrets_client._cache["key1"] = ("value1", time.time())
        secrets_client._cache["key2"] = ("value2", time.time())

        secrets_client.clear_cache()

        assert len(secrets_client._cache) == 0


class TestSecretsClientGetSecret:
    """Tests für get_secret Methode."""

    def test_get_secret_returns_string_value(self, secrets_setup):
        """get_secret gibt String-Wert zurück."""
        with mock_aws():
            client = SecretsClient(region="eu-central-1")
            value = client.get_secret("test/string-secret")

            assert value == "my-secret-value"

    def test_get_secret_uses_cache(self, secrets_setup):
        """get_secret verwendet Cache bei wiederholtem Aufruf."""
        with mock_aws():
            client = SecretsClient(region="eu-central-1")

            # Erster Aufruf
            value1 = client.get_secret("test/string-secret")

            # Cache prüfen
            assert "string:test/string-secret" in client._cache

            # Zweiter Aufruf sollte aus Cache kommen
            value2 = client.get_secret("test/string-secret")

            assert value1 == value2

    def test_get_secret_bypasses_cache(self, secrets_setup):
        """get_secret kann Cache umgehen."""
        with mock_aws():
            client = SecretsClient(region="eu-central-1")

            # Cache manuell setzen
            client._cache["string:test/string-secret"] = ("old-value", time.time())

            # Mit use_cache=False sollte AWS abgefragt werden
            value = client.get_secret("test/string-secret", use_cache=False)

            assert value == "my-secret-value"

    def test_get_secret_raises_for_binary(self, secrets_setup):
        """get_secret wirft Fehler für Binary-Secret."""
        with mock_aws():
            client = SecretsClient(region="eu-central-1")

            with pytest.raises(ValueError, match="not a string secret"):
                client.get_secret("test/binary-secret")


class TestSecretsClientGetSecretJson:
    """Tests für get_secret_json Methode."""

    def test_get_secret_json_parses_json(self, secrets_setup):
        """get_secret_json parst JSON-Wert."""
        with mock_aws():
            client = SecretsClient(region="eu-central-1")
            value = client.get_secret_json("test/json-secret")

            assert value == {"host": "localhost", "port": 5432}

    def test_get_secret_json_uses_cache(self, secrets_setup):
        """get_secret_json verwendet Cache."""
        with mock_aws():
            client = SecretsClient(region="eu-central-1")

            # Erster Aufruf
            client.get_secret_json("test/json-secret")

            # Cache prüfen
            assert "json:test/json-secret" in client._cache

    def test_get_secret_json_raises_for_invalid_json(self, secrets_setup):
        """get_secret_json wirft Fehler bei ungültigem JSON."""
        with mock_aws():
            # Setup invalid JSON secret
            sm = boto3.client("secretsmanager", region_name="eu-central-1")
            sm.create_secret(Name="test/invalid-json", SecretString="not valid json")

            client = SecretsClient(region="eu-central-1")

            with pytest.raises(json.JSONDecodeError):
                client.get_secret_json("test/invalid-json")


class TestSecretsClientGetSecretBinary:
    """Tests für get_secret_binary Methode."""

    def test_get_secret_binary_returns_bytes(self, secrets_setup):
        """get_secret_binary gibt bytes zurück."""
        with mock_aws():
            client = SecretsClient(region="eu-central-1")
            value = client.get_secret_binary("test/binary-secret")

            assert value == b"binary-data"

    def test_get_secret_binary_uses_cache(self, secrets_setup):
        """get_secret_binary verwendet Cache."""
        with mock_aws():
            client = SecretsClient(region="eu-central-1")

            # Erster Aufruf
            client.get_secret_binary("test/binary-secret")

            # Cache prüfen
            assert "binary:test/binary-secret" in client._cache

    def test_get_secret_binary_raises_for_string(self, secrets_setup):
        """get_secret_binary wirft Fehler für String-Secret."""
        with mock_aws():
            client = SecretsClient(region="eu-central-1")

            with pytest.raises(ValueError, match="not a binary secret"):
                client.get_secret_binary("test/string-secret")


class TestGetSecretsClient:
    """Tests für Factory-Funktion."""

    def test_returns_singleton(self):
        """Factory gibt Singleton zurück für gleiche Region."""
        SecretsClient._instances.clear()

        with mock_aws():
            client1 = get_secrets_client("eu-central-1")
            client2 = get_secrets_client("eu-central-1")

            assert client1 is client2

    def test_different_regions_different_instances(self):
        """Verschiedene Regionen bekommen verschiedene Instanzen."""
        SecretsClient._instances.clear()

        with mock_aws():
            client1 = get_secrets_client("eu-central-1")
            client2 = get_secrets_client("us-west-2")

            assert client1 is not client2

    def test_default_region_uses_singleton(self):
        """Default-Region verwendet Singleton."""
        SecretsClient._instances.clear()

        with mock_aws():
            client1 = get_secrets_client()
            client2 = get_secrets_client()

            assert client1 is client2
