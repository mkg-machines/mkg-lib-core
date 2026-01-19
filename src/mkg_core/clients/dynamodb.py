"""DynamoDB Client für die MKG Platform.

Stellt einen Wrapper um AWS DynamoDB bereit mit:
- Tenant-Isolation durch Key-Prefix
- Integration mit Pagination Utilities
- Structured Logging
- Retry-Logik für Throttling

Example:
    >>> from mkg_core.clients.dynamodb import DynamoDBClient
    >>> client = DynamoDBClient(table_name="mkg-entities-prod")
    >>> item = client.get_item("tnt-123", "ENTITY#456", "METADATA")
"""

from __future__ import annotations

import os
from decimal import Decimal
from typing import TYPE_CHECKING, Any, ClassVar

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.config import Config

from mkg_core.utils.logging import get_logger
from mkg_core.utils.pagination import (
    PaginatedResult,
    PaginationRequest,
    create_pagination_response,
)

if TYPE_CHECKING:
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table

logger = get_logger(__name__)

# Default Retry-Konfiguration
DEFAULT_RETRY_CONFIG = Config(
    retries={
        "max_attempts": 3,
        "mode": "adaptive",
    }
)


class DynamoDBClient:
    """Client für AWS DynamoDB mit Tenant-Isolation.

    Verwendet Single-Table-Design mit zusammengesetzten Keys:
    - PK (Partition Key): `TENANT#{tenant_id}#{entity_type}`
    - SK (Sort Key): Variiert je nach Datenzugriffsmuster

    Attributes:
        table_name: Name der DynamoDB-Tabelle.
        region: AWS Region.

    Example:
        >>> client = DynamoDBClient("mkg-entities-prod")
        >>> items = client.query("tnt-123", "ENTITY#product")
    """

    _instances: ClassVar[dict[str, DynamoDBClient]] = {}

    def __init__(
        self,
        table_name: str,
        region: str | None = None,
    ) -> None:
        """Initialisiert den DynamoDB Client.

        Args:
            table_name: Name der DynamoDB-Tabelle.
            region: AWS Region (Default: AWS_REGION oder AWS_DEFAULT_REGION).
        """
        self._table_name = table_name
        self._region = region or os.environ.get(
            "AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "eu-central-1")
        )
        self._resource: DynamoDBServiceResource | None = None
        self._table: Table | None = None

    @property
    def table_name(self) -> str:
        """Name der DynamoDB-Tabelle."""
        return self._table_name

    @property
    def resource(self) -> DynamoDBServiceResource:
        """Lazy-initialisierte boto3 DynamoDB Resource."""
        if self._resource is None:
            self._resource = boto3.resource(
                "dynamodb",
                region_name=self._region,
                config=DEFAULT_RETRY_CONFIG,
            )
        return self._resource

    @property
    def table(self) -> Table:
        """Lazy-initialisierte DynamoDB Table."""
        if self._table is None:
            self._table = self.resource.Table(self._table_name)
        return self._table

    def _serialize_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """Serialisiert Python-Typen für DynamoDB.

        Konvertiert float zu Decimal (DynamoDB unterstützt kein float).

        Args:
            item: Das zu serialisierende Item.

        Returns:
            Das serialisierte Item.
        """
        serialized: dict[str, Any] = {}
        for key, value in item.items():
            if isinstance(value, float):
                serialized[key] = Decimal(str(value))
            elif isinstance(value, dict):
                serialized[key] = self._serialize_item(value)
            elif isinstance(value, list):
                serialized[key] = [
                    self._serialize_item(v) if isinstance(v, dict) else v for v in value
                ]
            else:
                serialized[key] = value
        return serialized

    def _deserialize_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """Deserialisiert DynamoDB-Typen zu Python-Typen.

        Konvertiert Decimal zu float/int.

        Args:
            item: Das zu deserialisierende Item.

        Returns:
            Das deserialisierte Item.
        """
        deserialized: dict[str, Any] = {}
        for key, value in item.items():
            if isinstance(value, Decimal):
                # Konvertiere zu int wenn möglich, sonst float
                if value % 1 == 0:
                    deserialized[key] = int(value)
                else:
                    deserialized[key] = float(value)
            elif isinstance(value, dict):
                deserialized[key] = self._deserialize_item(value)
            elif isinstance(value, list):
                deserialized[key] = [
                    self._deserialize_item(v) if isinstance(v, dict) else v
                    for v in value
                ]
            else:
                deserialized[key] = value
        return deserialized

    def put_item(
        self,
        tenant_id: str,
        item: dict[str, Any],
        *,
        condition_expression: Any | None = None,
    ) -> None:
        """Speichert ein Item in DynamoDB.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            item: Das zu speichernde Item (muss PK und SK enthalten).
            condition_expression: Optionale Condition Expression.

        Raises:
            botocore.exceptions.ClientError: Bei AWS-Fehlern.

        Example:
            >>> client.put_item("tnt-123", {
            ...     "PK": "TENANT#tnt-123#ENTITY",
            ...     "SK": "ENTITY#456",
            ...     "name": "Test Entity",
            ...     "created_at": "2025-01-15T10:00:00Z"
            ... })
        """
        serialized = self._serialize_item(item)

        logger.debug(
            "Putting item to DynamoDB",
            table=self._table_name,
            tenant_id=tenant_id,
            pk=item.get("PK"),
            sk=item.get("SK"),
        )

        kwargs: dict[str, Any] = {"Item": serialized}
        if condition_expression is not None:
            kwargs["ConditionExpression"] = condition_expression

        self.table.put_item(**kwargs)

    def get_item(
        self,
        tenant_id: str,
        pk: str,
        sk: str,
        *,
        consistent_read: bool = False,
    ) -> dict[str, Any] | None:
        """Lädt ein Item aus DynamoDB.

        Args:
            tenant_id: Die Tenant-ID für Isolation (zur Validierung).
            pk: Der Partition Key.
            sk: Der Sort Key.
            consistent_read: True für strongly consistent read.

        Returns:
            Das Item als Dictionary oder None wenn nicht gefunden.

        Raises:
            botocore.exceptions.ClientError: Bei AWS-Fehlern.
            ValueError: Wenn das Item nicht zum Tenant gehört.

        Example:
            >>> item = client.get_item(
            ...     "tnt-123",
            ...     "TENANT#tnt-123#ENTITY",
            ...     "ENTITY#456"
            ... )
        """
        logger.debug(
            "Getting item from DynamoDB",
            table=self._table_name,
            tenant_id=tenant_id,
            pk=pk,
            sk=sk,
        )

        response = self.table.get_item(
            Key={"PK": pk, "SK": sk},
            ConsistentRead=consistent_read,
        )

        item = response.get("Item")
        if item is None:
            return None

        # Tenant-Validierung
        item_tenant = item.get("tenant_id")
        if item_tenant and item_tenant != tenant_id:
            logger.warning(
                "Tenant mismatch in get_item",
                requested_tenant=tenant_id,
                item_tenant=item_tenant,
            )
            return None

        return self._deserialize_item(item)

    def update_item(
        self,
        tenant_id: str,
        pk: str,
        sk: str,
        updates: dict[str, Any],
        *,
        condition_expression: Any | None = None,
    ) -> dict[str, Any]:
        """Aktualisiert ein Item in DynamoDB.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            pk: Der Partition Key.
            sk: Der Sort Key.
            updates: Dictionary mit zu aktualisierenden Feldern.
            condition_expression: Optionale Condition Expression.

        Returns:
            Das aktualisierte Item.

        Raises:
            botocore.exceptions.ClientError: Bei AWS-Fehlern.

        Example:
            >>> updated = client.update_item(
            ...     "tnt-123",
            ...     "TENANT#tnt-123#ENTITY",
            ...     "ENTITY#456",
            ...     {"name": "Updated Name", "version": 2}
            ... )
        """
        # Build UpdateExpression
        update_parts: list[str] = []
        expression_names: dict[str, str] = {}
        expression_values: dict[str, Any] = {}

        for idx, (key, value) in enumerate(updates.items()):
            placeholder_name = f"#attr{idx}"
            placeholder_value = f":val{idx}"
            update_parts.append(f"{placeholder_name} = {placeholder_value}")
            expression_names[placeholder_name] = key
            expression_values[placeholder_value] = (
                Decimal(str(value)) if isinstance(value, float) else value
            )

        update_expression = "SET " + ", ".join(update_parts)

        logger.debug(
            "Updating item in DynamoDB",
            table=self._table_name,
            tenant_id=tenant_id,
            pk=pk,
            sk=sk,
            update_fields=list(updates.keys()),
        )

        kwargs: dict[str, Any] = {
            "Key": {"PK": pk, "SK": sk},
            "UpdateExpression": update_expression,
            "ExpressionAttributeNames": expression_names,
            "ExpressionAttributeValues": expression_values,
            "ReturnValues": "ALL_NEW",
        }

        if condition_expression is not None:
            kwargs["ConditionExpression"] = condition_expression

        response = self.table.update_item(**kwargs)
        return self._deserialize_item(response.get("Attributes", {}))

    def delete_item(
        self,
        tenant_id: str,
        pk: str,
        sk: str,
        *,
        condition_expression: Any | None = None,
    ) -> None:
        """Löscht ein Item aus DynamoDB.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            pk: Der Partition Key.
            sk: Der Sort Key.
            condition_expression: Optionale Condition Expression.

        Raises:
            botocore.exceptions.ClientError: Bei AWS-Fehlern.

        Example:
            >>> client.delete_item(
            ...     "tnt-123",
            ...     "TENANT#tnt-123#ENTITY",
            ...     "ENTITY#456"
            ... )
        """
        logger.info(
            "Deleting item from DynamoDB",
            table=self._table_name,
            tenant_id=tenant_id,
            pk=pk,
            sk=sk,
        )

        kwargs: dict[str, Any] = {"Key": {"PK": pk, "SK": sk}}
        if condition_expression is not None:
            kwargs["ConditionExpression"] = condition_expression

        self.table.delete_item(**kwargs)

    def query(
        self,
        tenant_id: str,
        pk: str,
        sk_condition: Any | None = None,
        pagination: PaginationRequest | None = None,
        *,
        scan_index_forward: bool = True,
        filter_expression: Any | None = None,
        projection_expression: str | None = None,
    ) -> PaginatedResult[dict[str, Any]]:
        """Führt eine Query auf der Tabelle aus.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            pk: Der Partition Key Wert.
            sk_condition: Optionale Sort Key Condition.
            pagination: Optionale Pagination-Parameter.
            scan_index_forward: True für aufsteigend, False für absteigend.
            filter_expression: Optionaler Filter (nach Query angewendet).
            projection_expression: Optionale Projektion auf bestimmte Attribute.

        Returns:
            PaginatedResult mit den gefundenen Items.

        Example:
            >>> result = client.query(
            ...     "tnt-123",
            ...     "TENANT#tnt-123#ENTITY",
            ...     Key("SK").begins_with("ENTITY#"),
            ...     PaginationRequest(limit=20)
            ... )
            >>> for item in result.items:
            ...     print(item["name"])
        """
        logger.debug(
            "Querying DynamoDB",
            table=self._table_name,
            tenant_id=tenant_id,
            pk=pk,
        )

        # Key Condition
        key_condition = Key("PK").eq(pk)
        if sk_condition is not None:
            key_condition = key_condition & sk_condition

        # Query-Parameter
        kwargs: dict[str, Any] = {
            "KeyConditionExpression": key_condition,
            "ScanIndexForward": scan_index_forward,
        }

        # Pagination
        if pagination:
            kwargs.update(pagination.to_dynamodb_kwargs())
        else:
            kwargs["Limit"] = 100

        if filter_expression is not None:
            kwargs["FilterExpression"] = filter_expression

        if projection_expression:
            kwargs["ProjectionExpression"] = projection_expression

        response = self.table.query(**kwargs)

        # Items deserialisieren
        items = [self._deserialize_item(item) for item in response.get("Items", [])]

        # Pagination Response
        last_key = response.get("LastEvaluatedKey")
        pagination_response = create_pagination_response(last_key)

        return PaginatedResult(items=items, pagination=pagination_response)

    def query_by_gsi(
        self,
        tenant_id: str,
        index_name: str,
        pk: str,
        sk_condition: Any | None = None,
        pagination: PaginationRequest | None = None,
        *,
        scan_index_forward: bool = True,
        filter_expression: Any | None = None,
    ) -> PaginatedResult[dict[str, Any]]:
        """Führt eine Query auf einem Global Secondary Index aus.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            index_name: Name des GSI.
            pk: Der GSI Partition Key Wert.
            sk_condition: Optionale GSI Sort Key Condition.
            pagination: Optionale Pagination-Parameter.
            scan_index_forward: True für aufsteigend, False für absteigend.
            filter_expression: Optionaler Filter.

        Returns:
            PaginatedResult mit den gefundenen Items.

        Example:
            >>> result = client.query_by_gsi(
            ...     "tnt-123",
            ...     "GSI1",
            ...     "TENANT#tnt-123#TYPE#article",
            ...     pagination=PaginationRequest(limit=50)
            ... )
        """
        logger.debug(
            "Querying DynamoDB GSI",
            table=self._table_name,
            index=index_name,
            tenant_id=tenant_id,
            pk=pk,
        )

        # Key Condition - GSI Keys heißen typischerweise GSI1PK, GSI1SK etc.
        key_condition = Key("GSI1PK").eq(pk)
        if sk_condition is not None:
            key_condition = key_condition & sk_condition

        kwargs: dict[str, Any] = {
            "IndexName": index_name,
            "KeyConditionExpression": key_condition,
            "ScanIndexForward": scan_index_forward,
        }

        if pagination:
            kwargs.update(pagination.to_dynamodb_kwargs())
        else:
            kwargs["Limit"] = 100

        if filter_expression is not None:
            kwargs["FilterExpression"] = filter_expression

        response = self.table.query(**kwargs)

        items = [self._deserialize_item(item) for item in response.get("Items", [])]
        last_key = response.get("LastEvaluatedKey")
        pagination_response = create_pagination_response(last_key)

        return PaginatedResult(items=items, pagination=pagination_response)

    def batch_get_items(
        self,
        tenant_id: str,
        keys: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        """Lädt mehrere Items in einem Batch.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            keys: Liste von Key-Dictionaries mit PK und SK.

        Returns:
            Liste der gefundenen Items.

        Example:
            >>> items = client.batch_get_items("tnt-123", [
            ...     {"PK": "TENANT#tnt-123#ENTITY", "SK": "ENTITY#1"},
            ...     {"PK": "TENANT#tnt-123#ENTITY", "SK": "ENTITY#2"},
            ... ])
        """
        if not keys:
            return []

        logger.debug(
            "Batch getting items from DynamoDB",
            table=self._table_name,
            tenant_id=tenant_id,
            count=len(keys),
        )

        response = self.resource.batch_get_item(
            RequestItems={self._table_name: {"Keys": keys}}
        )

        items = response.get("Responses", {}).get(self._table_name, [])
        return [self._deserialize_item(item) for item in items]

    def batch_write_items(
        self,
        tenant_id: str,
        items: list[dict[str, Any]],
    ) -> None:
        """Schreibt mehrere Items in einem Batch.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            items: Liste von Items zum Schreiben.

        Raises:
            botocore.exceptions.ClientError: Bei AWS-Fehlern.

        Example:
            >>> client.batch_write_items("tnt-123", [
            ...     {"PK": "...", "SK": "...", "name": "Item 1"},
            ...     {"PK": "...", "SK": "...", "name": "Item 2"},
            ... ])
        """
        if not items:
            return

        logger.info(
            "Batch writing items to DynamoDB",
            table=self._table_name,
            tenant_id=tenant_id,
            count=len(items),
        )

        # DynamoDB batch_write unterstützt max 25 Items
        batch_size = 25
        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]
            put_requests = [
                {"PutRequest": {"Item": self._serialize_item(item)}} for item in batch
            ]

            self.resource.batch_write_item(
                RequestItems={self._table_name: put_requests}  # type: ignore[dict-item]
            )

    def scan(
        self,
        tenant_id: str,
        filter_expression: Any | None = None,
        pagination: PaginationRequest | None = None,
    ) -> PaginatedResult[dict[str, Any]]:
        """Führt einen Scan auf der Tabelle aus.

        WARNUNG: Scans sind teuer und sollten vermieden werden.
        Verwende Query mit geeignetem Index wenn möglich.

        Args:
            tenant_id: Die Tenant-ID für Isolation.
            filter_expression: Filter für den Scan.
            pagination: Optionale Pagination-Parameter.

        Returns:
            PaginatedResult mit den gefundenen Items.
        """
        logger.warning(
            "Performing table scan - consider using query instead",
            table=self._table_name,
            tenant_id=tenant_id,
        )

        # Filter auf tenant_id für Isolation
        tenant_filter = Attr("tenant_id").eq(tenant_id)
        if filter_expression is not None:
            combined_filter = tenant_filter & filter_expression
        else:
            combined_filter = tenant_filter

        kwargs: dict[str, Any] = {"FilterExpression": combined_filter}

        if pagination:
            kwargs.update(pagination.to_dynamodb_kwargs())
        else:
            kwargs["Limit"] = 100

        response = self.table.scan(**kwargs)

        items = [self._deserialize_item(item) for item in response.get("Items", [])]
        last_key = response.get("LastEvaluatedKey")
        pagination_response = create_pagination_response(last_key)

        return PaginatedResult(items=items, pagination=pagination_response)


def get_dynamodb_client(table_name: str, region: str | None = None) -> DynamoDBClient:
    """Factory-Funktion für DynamoDBClient mit Singleton-Pattern.

    Gibt für dieselbe Tabelle immer dieselbe Client-Instanz zurück.
    Optimiert für Lambda Cold-Starts.

    Args:
        table_name: Name der DynamoDB-Tabelle.
        region: AWS Region.

    Returns:
        Eine DynamoDBClient-Instanz.

    Example:
        >>> client = get_dynamodb_client("mkg-entities-prod")
        >>> items = client.query("tnt-123", "TENANT#tnt-123#ENTITY")
    """
    cache_key = f"{table_name}:{region or 'default'}"
    if cache_key not in DynamoDBClient._instances:
        DynamoDBClient._instances[cache_key] = DynamoDBClient(
            table_name=table_name, region=region
        )
    return DynamoDBClient._instances[cache_key]


# Re-export für einfache Verwendung
__all__ = [
    "Attr",
    "DynamoDBClient",
    "Key",
    "get_dynamodb_client",
]
