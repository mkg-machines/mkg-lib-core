"""Tests für S3 Client."""

from datetime import datetime
from io import BytesIO

import boto3
import pytest
from moto import mock_aws

from mkg_core.clients.s3 import S3Client, S3Object, get_s3_client


@pytest.fixture
def s3_bucket():
    """Erstellt einen Mock-S3-Bucket."""
    with mock_aws():
        s3 = boto3.client("s3", region_name="eu-central-1")
        s3.create_bucket(
            Bucket="test-bucket",
            CreateBucketConfiguration={"LocationConstraint": "eu-central-1"},
        )
        yield "test-bucket"


@pytest.fixture
def client(s3_bucket):
    """Erstellt einen S3 Client für Tests."""
    with mock_aws():
        S3Client._instances.clear()
        client = S3Client("test-bucket", region="eu-central-1")
        # Force client initialization
        _ = client.client
        yield client


class TestS3Object:
    """Tests für S3Object Model."""

    def test_s3_object_creation(self):
        """S3Object kann erstellt werden."""
        obj = S3Object(
            key="images/logo.png",
            size=1024,
            last_modified=datetime(2025, 1, 15, 10, 0, 0),
            etag="abc123",
            content_type="image/png",
        )

        assert obj.key == "images/logo.png"
        assert obj.size == 1024
        assert obj.content_type == "image/png"

    def test_s3_object_optional_content_type(self):
        """content_type ist optional."""
        obj = S3Object(
            key="file.bin",
            size=100,
            last_modified=datetime(2025, 1, 15),
            etag="def456",
        )

        assert obj.content_type is None


class TestS3ClientInit:
    """Tests für S3Client Initialisierung."""

    def test_init_with_region(self):
        """Client wird mit expliziter Region initialisiert."""
        client = S3Client("my-bucket", region="us-west-2")

        assert client.bucket_name == "my-bucket"
        assert client._region == "us-west-2"

    def test_init_uses_env_region(self, mocker):
        """Client verwendet AWS_REGION aus Environment."""
        mocker.patch.dict("os.environ", {"AWS_REGION": "ap-northeast-1"})
        client = S3Client("my-bucket")

        assert client._region == "ap-northeast-1"


class TestS3ClientKeyBuilding:
    """Tests für Key-Building mit Tenant-Prefix."""

    @pytest.fixture
    def client(self):
        return S3Client("test-bucket")

    def test_build_key_with_tenant_prefix(self, client):
        """Key wird mit Tenant-Prefix gebaut."""
        key = client._build_key("tnt-123", "images/logo.png")

        assert key == "tnt-123/images/logo.png"

    def test_build_key_strips_leading_slash(self, client):
        """Führende Slashes werden entfernt."""
        key = client._build_key("tnt-123", "/images/logo.png")

        assert key == "tnt-123/images/logo.png"

    def test_build_key_handles_multiple_leading_slashes(self, client):
        """Mehrfache führende Slashes werden entfernt."""
        key = client._build_key("tnt-123", "///images/logo.png")

        assert key == "tnt-123/images/logo.png"


class TestS3ClientUpload:
    """Tests für Upload-Operationen."""

    def test_upload_file_bytes(self, s3_bucket):
        """Upload von bytes Inhalt."""
        with mock_aws():
            client = S3Client("test-bucket", region="eu-central-1")
            content = b"Hello, World!"

            uri = client.upload_file("tnt-123", "test.txt", content)

            assert uri == "s3://test-bucket/tnt-123/test.txt"

            # Verify content
            s3 = boto3.client("s3", region_name="eu-central-1")
            response = s3.get_object(Bucket="test-bucket", Key="tnt-123/test.txt")
            assert response["Body"].read() == content

    def test_upload_file_with_content_type(self, s3_bucket):
        """Upload mit explizitem Content-Type."""
        with mock_aws():
            client = S3Client("test-bucket", region="eu-central-1")
            content = b'{"key": "value"}'

            uri = client.upload_file(
                "tnt-123", "data.json", content, content_type="application/json"
            )

            # Verify content type
            s3 = boto3.client("s3", region_name="eu-central-1")
            response = s3.head_object(Bucket="test-bucket", Key="tnt-123/data.json")
            assert response["ContentType"] == "application/json"

    def test_upload_file_auto_content_type(self, s3_bucket):
        """Upload erkennt Content-Type automatisch."""
        with mock_aws():
            client = S3Client("test-bucket", region="eu-central-1")
            content = b"PNG image data"

            client.upload_file("tnt-123", "image.png", content)

            s3 = boto3.client("s3", region_name="eu-central-1")
            response = s3.head_object(Bucket="test-bucket", Key="tnt-123/image.png")
            assert response["ContentType"] == "image/png"

    def test_upload_file_with_metadata(self, s3_bucket):
        """Upload mit Metadaten."""
        with mock_aws():
            client = S3Client("test-bucket", region="eu-central-1")
            content = b"Content"
            metadata = {"uploaded-by": "test-user"}

            client.upload_file("tnt-123", "file.txt", content, metadata=metadata)

            s3 = boto3.client("s3", region_name="eu-central-1")
            response = s3.head_object(Bucket="test-bucket", Key="tnt-123/file.txt")
            assert response["Metadata"]["uploaded-by"] == "test-user"

    def test_upload_file_from_file_object(self, s3_bucket):
        """Upload von File-like Object."""
        with mock_aws():
            client = S3Client("test-bucket", region="eu-central-1")
            content = BytesIO(b"File content")

            uri = client.upload_file("tnt-123", "file.txt", content)

            assert uri == "s3://test-bucket/tnt-123/file.txt"


class TestS3ClientDownload:
    """Tests für Download-Operationen."""

    def test_download_file(self, s3_bucket):
        """Download von Datei."""
        with mock_aws():
            # Setup
            s3 = boto3.client("s3", region_name="eu-central-1")
            s3.put_object(
                Bucket="test-bucket", Key="tnt-123/file.txt", Body=b"File content"
            )

            client = S3Client("test-bucket", region="eu-central-1")
            content = client.download_file("tnt-123", "file.txt")

            assert content == b"File content"


class TestS3ClientDelete:
    """Tests für Delete-Operationen."""

    def test_delete_file(self, s3_bucket):
        """Löschen einer Datei."""
        with mock_aws():
            # Setup
            s3 = boto3.client("s3", region_name="eu-central-1")
            s3.put_object(Bucket="test-bucket", Key="tnt-123/file.txt", Body=b"Content")

            client = S3Client("test-bucket", region="eu-central-1")
            client.delete_file("tnt-123", "file.txt")

            # Verify deletion
            response = s3.list_objects_v2(
                Bucket="test-bucket", Prefix="tnt-123/file.txt"
            )
            assert response.get("Contents") is None


class TestS3ClientExists:
    """Tests für Existenz-Prüfung."""

    def test_file_exists_returns_true(self, s3_bucket):
        """file_exists gibt True zurück wenn Datei existiert."""
        with mock_aws():
            # Setup
            s3 = boto3.client("s3", region_name="eu-central-1")
            s3.put_object(Bucket="test-bucket", Key="tnt-123/file.txt", Body=b"Content")

            client = S3Client("test-bucket", region="eu-central-1")
            exists = client.file_exists("tnt-123", "file.txt")

            assert exists is True

    def test_file_exists_returns_false(self, s3_bucket):
        """file_exists gibt False zurück wenn Datei nicht existiert."""
        with mock_aws():
            client = S3Client("test-bucket", region="eu-central-1")
            exists = client.file_exists("tnt-123", "nonexistent.txt")

            assert exists is False


class TestS3ClientPresignedUrls:
    """Tests für Presigned URLs."""

    def test_generate_presigned_upload_url(self, s3_bucket):
        """Presigned Upload URL wird generiert."""
        with mock_aws():
            client = S3Client("test-bucket", region="eu-central-1")
            url = client.generate_presigned_upload_url(
                "tnt-123", "uploads/file.pdf", "application/pdf", expires_in=900
            )

            assert "test-bucket" in url
            assert "tnt-123/uploads/file.pdf" in url
            assert "X-Amz-Signature" in url

    def test_generate_presigned_download_url(self, s3_bucket):
        """Presigned Download URL wird generiert."""
        with mock_aws():
            # Setup
            s3 = boto3.client("s3", region_name="eu-central-1")
            s3.put_object(Bucket="test-bucket", Key="tnt-123/file.pdf", Body=b"PDF")

            client = S3Client("test-bucket", region="eu-central-1")
            url = client.generate_presigned_download_url(
                "tnt-123", "file.pdf", expires_in=300
            )

            assert "test-bucket" in url
            assert "X-Amz-Signature" in url

    def test_generate_presigned_download_url_with_filename(self, s3_bucket):
        """Presigned Download URL mit Content-Disposition."""
        with mock_aws():
            s3 = boto3.client("s3", region_name="eu-central-1")
            s3.put_object(Bucket="test-bucket", Key="tnt-123/file.pdf", Body=b"PDF")

            client = S3Client("test-bucket", region="eu-central-1")
            url = client.generate_presigned_download_url(
                "tnt-123", "file.pdf", filename="download.pdf"
            )

            assert "response-content-disposition" in url.lower()


class TestS3ClientList:
    """Tests für List-Operationen."""

    def test_list_files(self, s3_bucket):
        """list_files listet Dateien eines Tenants."""
        with mock_aws():
            # Setup
            s3 = boto3.client("s3", region_name="eu-central-1")
            for i in range(3):
                s3.put_object(
                    Bucket="test-bucket",
                    Key=f"tnt-123/images/file{i}.png",
                    Body=b"Content",
                )

            client = S3Client("test-bucket", region="eu-central-1")
            files = client.list_files("tnt-123", prefix="images/")

            assert len(files) == 3
            for f in files:
                assert isinstance(f, S3Object)
                assert f.key.startswith("images/")

    def test_list_files_strips_tenant_prefix(self, s3_bucket):
        """list_files entfernt Tenant-Prefix aus Keys."""
        with mock_aws():
            s3 = boto3.client("s3", region_name="eu-central-1")
            s3.put_object(
                Bucket="test-bucket", Key="tnt-123/file.txt", Body=b"Content"
            )

            client = S3Client("test-bucket", region="eu-central-1")
            files = client.list_files("tnt-123")

            assert len(files) == 1
            assert files[0].key == "file.txt"  # Ohne tnt-123/ Prefix

    def test_list_files_empty(self, s3_bucket):
        """list_files gibt leere Liste zurück wenn keine Dateien."""
        with mock_aws():
            client = S3Client("test-bucket", region="eu-central-1")
            files = client.list_files("tnt-empty")

            assert files == []


class TestS3ClientCopy:
    """Tests für Copy-Operationen."""

    def test_copy_file(self, s3_bucket):
        """copy_file kopiert Datei innerhalb des Buckets."""
        with mock_aws():
            # Setup
            s3 = boto3.client("s3", region_name="eu-central-1")
            s3.put_object(
                Bucket="test-bucket", Key="tnt-123/original.txt", Body=b"Content"
            )

            client = S3Client("test-bucket", region="eu-central-1")
            uri = client.copy_file("tnt-123", "original.txt", "copy.txt")

            assert uri == "s3://test-bucket/tnt-123/copy.txt"

            # Verify copy exists
            response = s3.get_object(Bucket="test-bucket", Key="tnt-123/copy.txt")
            assert response["Body"].read() == b"Content"


class TestGetS3Client:
    """Tests für Factory-Funktion."""

    def test_returns_singleton(self):
        """Factory gibt Singleton zurück für gleiche Parameter."""
        S3Client._instances.clear()

        with mock_aws():
            client1 = get_s3_client("test-bucket", "eu-central-1")
            client2 = get_s3_client("test-bucket", "eu-central-1")

            assert client1 is client2

    def test_different_buckets_different_instances(self):
        """Verschiedene Buckets bekommen verschiedene Instanzen."""
        S3Client._instances.clear()

        with mock_aws():
            client1 = get_s3_client("bucket-1")
            client2 = get_s3_client("bucket-2")

            assert client1 is not client2
