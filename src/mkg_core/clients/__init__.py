"""AWS Client Wrapper für die MKG Platform.

Dieses Modul stellt konfigurierte AWS-Clients bereit:
    - dynamodb: DynamoDB Client mit Tenant-Isolation und Pagination
    - s3: S3 Client für Asset-Operationen
    - secrets: Secrets Manager Client mit Caching
"""

from mkg_core.clients.dynamodb import (
    Attr,
    DynamoDBClient,
    Key,
    get_dynamodb_client,
)
from mkg_core.clients.s3 import (
    S3Client,
    S3Object,
    get_s3_client,
)
from mkg_core.clients.secrets import (
    SecretsClient,
    get_secrets_client,
)

__all__ = [
    "Attr",
    "DynamoDBClient",
    "Key",
    "S3Client",
    "S3Object",
    "SecretsClient",
    "get_dynamodb_client",
    "get_s3_client",
    "get_secrets_client",
]
