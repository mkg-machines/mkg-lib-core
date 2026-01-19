"""Secrets Manager Client für die MKG Platform.

Stellt einen Wrapper um AWS Secrets Manager bereit mit:
- Caching für Secret-Werte
- JSON-Parsing für strukturierte Secrets
- Binary-Support für Zertifikate

Example:
    >>> from mkg_core.clients.secrets import SecretsClient
    >>> client = SecretsClient()
    >>> db_config = client.get_secret_json("prod/database/config")
    >>> password = db_config["password"]
"""

from __future__ import annotations

import json
import os
import time
from typing import TYPE_CHECKING, Any, ClassVar

import boto3

from mkg_core.utils.logging import get_logger

if TYPE_CHECKING:
    from mypy_boto3_secretsmanager import SecretsManagerClient as Boto3SecretsClient

logger = get_logger(__name__)

# Default Cache TTL: 5 Minuten
DEFAULT_CACHE_TTL = 300


class SecretsClient:
    """Client für AWS Secrets Manager mit Caching.

    Attributes:
        region: AWS Region für den Client.
        cache_ttl: Time-to-Live für gecachte Secrets in Sekunden.

    Example:
        >>> client = SecretsClient(cache_ttl=600)
        >>> secret = client.get_secret("my-secret")
    """

    _instances: ClassVar[dict[str, SecretsClient]] = {}

    def __init__(
        self,
        region: str | None = None,
        *,
        cache_ttl: int = DEFAULT_CACHE_TTL,
    ) -> None:
        """Initialisiert den Secrets Manager Client.

        Args:
            region: AWS Region (Default: AWS_REGION oder AWS_DEFAULT_REGION).
            cache_ttl: Cache Time-to-Live in Sekunden (Default: 300).
        """
        self._region = region or os.environ.get(
            "AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "eu-central-1")
        )
        self._cache_ttl = cache_ttl
        self._cache: dict[str, tuple[Any, float]] = {}
        self._client: Boto3SecretsClient | None = None

    @property
    def client(self) -> Boto3SecretsClient:
        """Lazy-initialisierter boto3 Secrets Manager Client."""
        if self._client is None:
            self._client = boto3.client(
                "secretsmanager",
                region_name=self._region,
            )
        return self._client

    def _get_from_cache(self, secret_name: str) -> Any | None:
        """Holt einen Wert aus dem Cache wenn noch gültig.

        Args:
            secret_name: Name des Secrets.

        Returns:
            Der gecachte Wert oder None wenn nicht vorhanden/abgelaufen.
        """
        if secret_name in self._cache:
            value, timestamp = self._cache[secret_name]
            if time.time() - timestamp < self._cache_ttl:
                logger.debug("Secret from cache", secret_name=secret_name)
                return value
            # Cache abgelaufen
            del self._cache[secret_name]
        return None

    def _set_cache(self, secret_name: str, value: Any) -> None:
        """Speichert einen Wert im Cache.

        Args:
            secret_name: Name des Secrets.
            value: Der zu cachende Wert.
        """
        self._cache[secret_name] = (value, time.time())

    def clear_cache(self) -> None:
        """Löscht den gesamten Cache."""
        self._cache.clear()
        logger.debug("Secrets cache cleared")

    def get_secret(self, secret_name: str, *, use_cache: bool = True) -> str:
        """Holt einen Secret-String-Wert aus Secrets Manager.

        Args:
            secret_name: Name oder ARN des Secrets.
            use_cache: Ob der Cache verwendet werden soll (Default: True).

        Returns:
            Der Secret-String-Wert.

        Raises:
            botocore.exceptions.ClientError: Bei AWS-Fehlern.

        Example:
            >>> api_key = client.get_secret("prod/api/key")
        """
        cache_key = f"string:{secret_name}"

        if use_cache:
            cached = self._get_from_cache(cache_key)
            if cached is not None:
                return str(cached)

        logger.debug("Fetching secret from AWS", secret_name=secret_name)
        response = self.client.get_secret_value(SecretId=secret_name)

        if "SecretString" in response:
            value = response["SecretString"]
            self._set_cache(cache_key, value)
            return value

        msg = f"Secret {secret_name} is not a string secret"
        raise ValueError(msg)

    def get_secret_json(
        self, secret_name: str, *, use_cache: bool = True
    ) -> dict[str, Any]:
        """Holt einen Secret-Wert und parst ihn als JSON.

        Args:
            secret_name: Name oder ARN des Secrets.
            use_cache: Ob der Cache verwendet werden soll (Default: True).

        Returns:
            Der geparste JSON-Wert als Dictionary.

        Raises:
            botocore.exceptions.ClientError: Bei AWS-Fehlern.
            json.JSONDecodeError: Wenn der Wert kein gültiges JSON ist.

        Example:
            >>> db_config = client.get_secret_json("prod/database/config")
            >>> host = db_config["host"]
            >>> port = db_config["port"]
        """
        cache_key = f"json:{secret_name}"

        if use_cache:
            cached = self._get_from_cache(cache_key)
            if cached is not None:
                return dict(cached)

        secret_string = self.get_secret(secret_name, use_cache=False)
        value: dict[str, Any] = json.loads(secret_string)
        self._set_cache(cache_key, value)
        return value

    def get_secret_binary(self, secret_name: str, *, use_cache: bool = True) -> bytes:
        """Holt einen binären Secret-Wert (z.B. Zertifikate).

        Args:
            secret_name: Name oder ARN des Secrets.
            use_cache: Ob der Cache verwendet werden soll (Default: True).

        Returns:
            Der Secret-Wert als bytes.

        Raises:
            botocore.exceptions.ClientError: Bei AWS-Fehlern.
            ValueError: Wenn das Secret kein Binary-Secret ist.

        Example:
            >>> cert = client.get_secret_binary("prod/certs/ssl")
        """
        cache_key = f"binary:{secret_name}"

        if use_cache:
            cached = self._get_from_cache(cache_key)
            if cached is not None:
                return bytes(cached)

        logger.debug("Fetching binary secret from AWS", secret_name=secret_name)
        response = self.client.get_secret_value(SecretId=secret_name)

        if "SecretBinary" in response:
            value = response["SecretBinary"]
            self._set_cache(cache_key, value)
            return value

        msg = f"Secret {secret_name} is not a binary secret"
        raise ValueError(msg)


def get_secrets_client(
    region: str | None = None, *, cache_ttl: int = DEFAULT_CACHE_TTL
) -> SecretsClient:
    """Factory-Funktion für SecretsClient mit Singleton-Pattern.

    Gibt für dieselbe Region immer dieselbe Client-Instanz zurück.
    Optimiert für Lambda Cold-Starts.

    Args:
        region: AWS Region.
        cache_ttl: Cache Time-to-Live in Sekunden.

    Returns:
        Eine SecretsClient-Instanz.

    Example:
        >>> client = get_secrets_client()
        >>> secret = client.get_secret("my-secret")
    """
    cache_key = region or "default"
    if cache_key not in SecretsClient._instances:
        SecretsClient._instances[cache_key] = SecretsClient(
            region=region, cache_ttl=cache_ttl
        )
    return SecretsClient._instances[cache_key]
