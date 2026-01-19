"""S3 Client für die MKG Platform.

Stellt einen Wrapper um AWS S3 bereit mit:
- Tenant-Isolation durch Key-Prefix
- Presigned URLs für sichere Uploads/Downloads
- Structured Logging

Example:
    >>> from mkg_core.clients.s3 import S3Client
    >>> client = S3Client(bucket_name="mkg-assets-prod")
    >>> url = client.generate_presigned_upload_url(
    ...     tenant_id="tnt-123",
    ...     key="images/logo.png",
    ...     content_type="image/png"
    ... )
"""

from __future__ import annotations

import mimetypes
import os
from datetime import datetime
from io import BytesIO
from typing import TYPE_CHECKING, Any, BinaryIO, ClassVar

import boto3
from botocore.exceptions import ClientError
from pydantic import BaseModel

from mkg_core.utils.logging import get_logger

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client as Boto3S3Client

logger = get_logger(__name__)


class S3Object(BaseModel):
    """Repräsentiert ein S3-Objekt.

    Attributes:
        key: Der vollständige S3-Key (ohne Bucket).
        size: Größe in Bytes.
        last_modified: Zeitpunkt der letzten Änderung.
        etag: ETag des Objekts.
        content_type: MIME-Type (falls bekannt).
    """

    key: str
    size: int
    last_modified: datetime
    etag: str
    content_type: str | None = None

    model_config = {"extra": "forbid"}


class S3Client:
    """Client für AWS S3 mit Tenant-Isolation.

    Alle Keys werden automatisch mit `{tenant_id}/` prefixed,
    um Tenant-Isolation zu gewährleisten.

    Attributes:
        bucket_name: Name des S3 Buckets.
        region: AWS Region.

    Example:
        >>> client = S3Client("mkg-assets-prod")
        >>> client.upload_file("tnt-123", "images/logo.png", image_bytes)
    """

    _instances: ClassVar[dict[str, S3Client]] = {}

    def __init__(
        self,
        bucket_name: str,
        region: str | None = None,
    ) -> None:
        """Initialisiert den S3 Client.

        Args:
            bucket_name: Name des S3 Buckets.
            region: AWS Region (Default: AWS_REGION oder AWS_DEFAULT_REGION).
        """
        self._bucket_name = bucket_name
        self._region = region or os.environ.get(
            "AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "eu-central-1")
        )
        self._client: Boto3S3Client | None = None

    @property
    def bucket_name(self) -> str:
        """Name des S3 Buckets."""
        return self._bucket_name

    @property
    def client(self) -> Boto3S3Client:
        """Lazy-initialisierter boto3 S3 Client."""
        if self._client is None:
            self._client = boto3.client(
                "s3",
                region_name=self._region,
            )
        return self._client

    def _build_key(self, tenant_id: str, key: str) -> str:
        """Baut den vollständigen S3-Key mit Tenant-Prefix.

        Args:
            tenant_id: Die Tenant-ID.
            key: Der relative Key.

        Returns:
            Der vollständige Key mit Tenant-Prefix.
        """
        # Entferne führende Slashes vom Key
        clean_key = key.lstrip("/")
        return f"{tenant_id}/{clean_key}"

    def upload_file(
        self,
        tenant_id: str,
        key: str,
        content: bytes | BinaryIO,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Lädt eine Datei nach S3 hoch.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            key: Der relative Key (ohne Tenant-Prefix).
            content: Der Dateiinhalt als bytes oder File-like Object.
            content_type: MIME-Type (wird automatisch erkannt wenn None).
            metadata: Optionale Metadaten.

        Returns:
            Die vollständige S3 URI (s3://bucket/key).

        Raises:
            botocore.exceptions.ClientError: Bei AWS-Fehlern.

        Example:
            >>> uri = client.upload_file(
            ...     "tnt-123",
            ...     "images/logo.png",
            ...     image_bytes,
            ...     content_type="image/png"
            ... )
        """
        full_key = self._build_key(tenant_id, key)

        # Content-Type ermitteln
        if content_type is None:
            content_type, _ = mimetypes.guess_type(key)
            content_type = content_type or "application/octet-stream"

        # Body vorbereiten
        if isinstance(content, bytes):
            body: BinaryIO = BytesIO(content)
        else:
            body = content

        # Upload-Parameter
        extra_args: dict[str, Any] = {"ContentType": content_type}
        if metadata:
            extra_args["Metadata"] = metadata

        logger.info(
            "Uploading file to S3",
            bucket=self._bucket_name,
            key=full_key,
            tenant_id=tenant_id,
            content_type=content_type,
        )

        self.client.upload_fileobj(
            body,
            self._bucket_name,
            full_key,
            ExtraArgs=extra_args,
        )

        return f"s3://{self._bucket_name}/{full_key}"

    def download_file(self, tenant_id: str, key: str) -> bytes:
        """Lädt eine Datei von S3 herunter.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            key: Der relative Key (ohne Tenant-Prefix).

        Returns:
            Der Dateiinhalt als bytes.

        Raises:
            botocore.exceptions.ClientError: Bei AWS-Fehlern (z.B. NoSuchKey).

        Example:
            >>> content = client.download_file("tnt-123", "images/logo.png")
        """
        full_key = self._build_key(tenant_id, key)

        logger.debug(
            "Downloading file from S3",
            bucket=self._bucket_name,
            key=full_key,
            tenant_id=tenant_id,
        )

        buffer = BytesIO()
        self.client.download_fileobj(self._bucket_name, full_key, buffer)
        buffer.seek(0)
        return buffer.read()

    def delete_file(self, tenant_id: str, key: str) -> None:
        """Löscht eine Datei aus S3.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            key: Der relative Key (ohne Tenant-Prefix).

        Raises:
            botocore.exceptions.ClientError: Bei AWS-Fehlern.

        Example:
            >>> client.delete_file("tnt-123", "images/old-logo.png")
        """
        full_key = self._build_key(tenant_id, key)

        logger.info(
            "Deleting file from S3",
            bucket=self._bucket_name,
            key=full_key,
            tenant_id=tenant_id,
        )

        self.client.delete_object(Bucket=self._bucket_name, Key=full_key)

    def file_exists(self, tenant_id: str, key: str) -> bool:
        """Prüft ob eine Datei in S3 existiert.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            key: Der relative Key (ohne Tenant-Prefix).

        Returns:
            True wenn die Datei existiert, False sonst.

        Example:
            >>> exists = client.file_exists("tnt-123", "images/logo.png")
        """
        full_key = self._build_key(tenant_id, key)

        try:
            self.client.head_object(Bucket=self._bucket_name, Key=full_key)
            return True
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "404":
                return False
            raise

    def generate_presigned_upload_url(
        self,
        tenant_id: str,
        key: str,
        content_type: str,
        expires_in: int = 3600,
    ) -> str:
        """Generiert eine presigned URL für direkten Upload.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            key: Der relative Key (ohne Tenant-Prefix).
            content_type: Der MIME-Type der hochzuladenden Datei.
            expires_in: Gültigkeit in Sekunden (Default: 3600 = 1 Stunde).

        Returns:
            Die presigned URL für PUT-Requests.

        Example:
            >>> url = client.generate_presigned_upload_url(
            ...     "tnt-123",
            ...     "images/new-logo.png",
            ...     "image/png",
            ...     expires_in=900
            ... )
        """
        full_key = self._build_key(tenant_id, key)

        logger.debug(
            "Generating presigned upload URL",
            bucket=self._bucket_name,
            key=full_key,
            tenant_id=tenant_id,
            expires_in=expires_in,
        )

        url: str = self.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self._bucket_name,
                "Key": full_key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
        )
        return url

    def generate_presigned_download_url(
        self,
        tenant_id: str,
        key: str,
        expires_in: int = 3600,
        *,
        filename: str | None = None,
    ) -> str:
        """Generiert eine presigned URL für direkten Download.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            key: Der relative Key (ohne Tenant-Prefix).
            expires_in: Gültigkeit in Sekunden (Default: 3600 = 1 Stunde).
            filename: Optionaler Dateiname für Content-Disposition.

        Returns:
            Die presigned URL für GET-Requests.

        Example:
            >>> url = client.generate_presigned_download_url(
            ...     "tnt-123",
            ...     "images/logo.png",
            ...     expires_in=300
            ... )
        """
        full_key = self._build_key(tenant_id, key)

        params: dict[str, Any] = {
            "Bucket": self._bucket_name,
            "Key": full_key,
        }

        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

        logger.debug(
            "Generating presigned download URL",
            bucket=self._bucket_name,
            key=full_key,
            tenant_id=tenant_id,
            expires_in=expires_in,
        )

        url: str = self.client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expires_in,
        )
        return url

    def list_files(
        self,
        tenant_id: str,
        prefix: str = "",
        max_keys: int = 1000,
    ) -> list[S3Object]:
        """Listet Dateien eines Tenants auf.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            prefix: Optionaler Prefix zum Filtern (ohne Tenant-Prefix).
            max_keys: Maximale Anzahl Ergebnisse (Default: 1000).

        Returns:
            Liste von S3Object-Instanzen.

        Example:
            >>> files = client.list_files("tnt-123", prefix="images/")
            >>> for f in files:
            ...     print(f.key, f.size)
        """
        full_prefix = self._build_key(tenant_id, prefix)

        logger.debug(
            "Listing files in S3",
            bucket=self._bucket_name,
            prefix=full_prefix,
            tenant_id=tenant_id,
        )

        response = self.client.list_objects_v2(
            Bucket=self._bucket_name,
            Prefix=full_prefix,
            MaxKeys=max_keys,
        )

        objects: list[S3Object] = []
        for obj in response.get("Contents", []):
            # Entferne Tenant-Prefix aus dem Key für Anzeige
            relative_key = obj["Key"]
            if relative_key.startswith(f"{tenant_id}/"):
                relative_key = relative_key[len(tenant_id) + 1 :]

            objects.append(
                S3Object(
                    key=relative_key,
                    size=obj["Size"],
                    last_modified=obj["LastModified"],
                    etag=obj["ETag"].strip('"'),
                )
            )

        return objects

    def copy_file(
        self,
        tenant_id: str,
        source_key: str,
        destination_key: str,
    ) -> str:
        """Kopiert eine Datei innerhalb des Buckets.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            source_key: Der Quell-Key (ohne Tenant-Prefix).
            destination_key: Der Ziel-Key (ohne Tenant-Prefix).

        Returns:
            Die vollständige S3 URI des Ziels.

        Raises:
            botocore.exceptions.ClientError: Bei AWS-Fehlern.

        Example:
            >>> new_uri = client.copy_file(
            ...     "tnt-123",
            ...     "images/logo.png",
            ...     "images/logo-backup.png"
            ... )
        """
        source_full_key = self._build_key(tenant_id, source_key)
        dest_full_key = self._build_key(tenant_id, destination_key)

        logger.info(
            "Copying file in S3",
            bucket=self._bucket_name,
            source_key=source_full_key,
            destination_key=dest_full_key,
            tenant_id=tenant_id,
        )

        self.client.copy_object(
            Bucket=self._bucket_name,
            CopySource={"Bucket": self._bucket_name, "Key": source_full_key},
            Key=dest_full_key,
        )

        return f"s3://{self._bucket_name}/{dest_full_key}"


def get_s3_client(bucket_name: str, region: str | None = None) -> S3Client:
    """Factory-Funktion für S3Client mit Singleton-Pattern.

    Gibt für denselben Bucket immer dieselbe Client-Instanz zurück.
    Optimiert für Lambda Cold-Starts.

    Args:
        bucket_name: Name des S3 Buckets.
        region: AWS Region.

    Returns:
        Eine S3Client-Instanz.

    Example:
        >>> client = get_s3_client("mkg-assets-prod")
        >>> url = client.generate_presigned_download_url("tnt-123", "file.pdf")
    """
    cache_key = f"{bucket_name}:{region or 'default'}"
    if cache_key not in S3Client._instances:
        S3Client._instances[cache_key] = S3Client(
            bucket_name=bucket_name, region=region
        )
    return S3Client._instances[cache_key]
