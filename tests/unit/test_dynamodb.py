"""Tests für DynamoDB Client."""

from decimal import Decimal

import boto3
import pytest
from moto import mock_aws

from mkg_core.clients.dynamodb import DynamoDBClient, get_dynamodb_client
from mkg_core.utils.pagination import PaginationRequest


@pytest.fixture
def dynamodb_table():
    """Erstellt eine Mock-DynamoDB-Tabelle."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="eu-central-1")
        table = dynamodb.create_table(
            TableName="test-table",
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
                {"AttributeName": "GSI1PK", "AttributeType": "S"},
                {"AttributeName": "GSI1SK", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "GSI1",
                    "KeySchema": [
                        {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {
                        "ReadCapacityUnits": 5,
                        "WriteCapacityUnits": 5,
                    },
                }
            ],
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        )
        table.wait_until_exists()
        yield table


@pytest.fixture
def client(dynamodb_table):
    """Erstellt einen DynamoDB Client für Tests."""
    with mock_aws():
        # Clear singleton cache
        DynamoDBClient._instances.clear()
        client = DynamoDBClient("test-table", region="eu-central-1")
        # Force resource initialization
        _ = client.resource
        yield client


class TestDynamoDBClientInit:
    """Tests für DynamoDBClient Initialisierung."""

    def test_init_with_region(self):
        """Client wird mit expliziter Region initialisiert."""
        client = DynamoDBClient("test-table", region="us-west-2")

        assert client.table_name == "test-table"
        assert client._region == "us-west-2"

    def test_init_uses_env_region(self, mocker):
        """Client verwendet AWS_REGION aus Environment."""
        mocker.patch.dict("os.environ", {"AWS_REGION": "ap-northeast-1"})
        client = DynamoDBClient("test-table")

        assert client._region == "ap-northeast-1"

    def test_init_uses_default_region(self, mocker):
        """Client verwendet Default-Region wenn keine gesetzt."""
        import os

        mocker.patch.dict("os.environ", {}, clear=True)
        os.environ.pop("AWS_REGION", None)
        os.environ.pop("AWS_DEFAULT_REGION", None)
        client = DynamoDBClient("test-table")

        assert client._region == "eu-central-1"


class TestDynamoDBClientSerialization:
    """Tests für Serialisierung/Deserialisierung."""

    @pytest.fixture
    def client(self):
        return DynamoDBClient("test-table")

    def test_serialize_float_to_decimal(self, client):
        """Float wird zu Decimal konvertiert."""
        item = {"price": 19.99, "name": "Test"}
        serialized = client._serialize_item(item)

        assert isinstance(serialized["price"], Decimal)
        assert serialized["price"] == Decimal("19.99")
        assert serialized["name"] == "Test"

    def test_serialize_nested_dict(self, client):
        """Verschachtelte Dicts werden serialisiert."""
        item = {"data": {"nested_price": 9.99}}
        serialized = client._serialize_item(item)

        assert isinstance(serialized["data"]["nested_price"], Decimal)

    def test_serialize_list_with_dicts(self, client):
        """Listen mit Dicts werden serialisiert."""
        item = {"items": [{"price": 1.5}, {"price": 2.5}]}
        serialized = client._serialize_item(item)

        assert isinstance(serialized["items"][0]["price"], Decimal)

    def test_deserialize_decimal_to_int(self, client):
        """Decimal mit ganzer Zahl wird zu int."""
        item = {"count": Decimal("42")}
        deserialized = client._deserialize_item(item)

        assert isinstance(deserialized["count"], int)
        assert deserialized["count"] == 42

    def test_deserialize_decimal_to_float(self, client):
        """Decimal mit Nachkommastellen wird zu float."""
        item = {"price": Decimal("19.99")}
        deserialized = client._deserialize_item(item)

        assert isinstance(deserialized["price"], float)
        assert deserialized["price"] == 19.99

    def test_deserialize_nested_dict(self, client):
        """Verschachtelte Dicts werden deserialisiert."""
        item = {"data": {"value": Decimal("10")}}
        deserialized = client._deserialize_item(item)

        assert isinstance(deserialized["data"]["value"], int)

    def test_deserialize_list_with_dicts(self, client):
        """Listen mit Dicts werden deserialisiert."""
        item = {"items": [{"price": Decimal("1.5")}]}
        deserialized = client._deserialize_item(item)

        assert isinstance(deserialized["items"][0]["price"], float)


class TestDynamoDBClientOperations:
    """Tests für CRUD-Operationen."""

    def test_put_item(self, dynamodb_table):
        """put_item speichert Item in DynamoDB."""
        with mock_aws():
            client = DynamoDBClient("test-table", region="eu-central-1")

            item = {
                "PK": "TENANT#tnt-123#ENTITY",
                "SK": "ENTITY#456",
                "name": "Test Entity",
                "tenant_id": "tnt-123",
            }

            client.put_item("tnt-123", item)

            # Verify item was stored
            response = dynamodb_table.get_item(
                Key={"PK": "TENANT#tnt-123#ENTITY", "SK": "ENTITY#456"}
            )
            assert response.get("Item") is not None
            assert response["Item"]["name"] == "Test Entity"

    def test_get_item_returns_item(self, dynamodb_table):
        """get_item lädt Item aus DynamoDB."""
        with mock_aws():
            # Setup
            dynamodb_table.put_item(
                Item={
                    "PK": "TENANT#tnt-123#ENTITY",
                    "SK": "ENTITY#456",
                    "name": "Test Entity",
                    "tenant_id": "tnt-123",
                }
            )

            client = DynamoDBClient("test-table", region="eu-central-1")
            item = client.get_item("tnt-123", "TENANT#tnt-123#ENTITY", "ENTITY#456")

            assert item is not None
            assert item["name"] == "Test Entity"

    def test_get_item_returns_none_when_not_found(self, dynamodb_table):
        """get_item gibt None zurück wenn Item nicht existiert."""
        with mock_aws():
            client = DynamoDBClient("test-table", region="eu-central-1")
            item = client.get_item("tnt-123", "NONEXISTENT", "SK")

            assert item is None

    def test_get_item_validates_tenant(self, dynamodb_table):
        """get_item gibt None zurück bei Tenant-Mismatch."""
        with mock_aws():
            # Setup item with different tenant
            dynamodb_table.put_item(
                Item={
                    "PK": "TENANT#tnt-other#ENTITY",
                    "SK": "ENTITY#456",
                    "name": "Test Entity",
                    "tenant_id": "tnt-other",
                }
            )

            client = DynamoDBClient("test-table", region="eu-central-1")
            # Request with different tenant
            item = client.get_item("tnt-123", "TENANT#tnt-other#ENTITY", "ENTITY#456")

            assert item is None

    def test_update_item(self, dynamodb_table):
        """update_item aktualisiert Item."""
        with mock_aws():
            # Setup
            dynamodb_table.put_item(
                Item={
                    "PK": "TENANT#tnt-123#ENTITY",
                    "SK": "ENTITY#456",
                    "name": "Old Name",
                    "tenant_id": "tnt-123",
                }
            )

            client = DynamoDBClient("test-table", region="eu-central-1")
            updated = client.update_item(
                "tnt-123",
                "TENANT#tnt-123#ENTITY",
                "ENTITY#456",
                {"name": "New Name", "version": 2},
            )

            assert updated["name"] == "New Name"
            assert updated["version"] == 2

    def test_delete_item(self, dynamodb_table):
        """delete_item löscht Item."""
        with mock_aws():
            # Setup
            dynamodb_table.put_item(
                Item={
                    "PK": "TENANT#tnt-123#ENTITY",
                    "SK": "ENTITY#456",
                    "name": "Test",
                    "tenant_id": "tnt-123",
                }
            )

            client = DynamoDBClient("test-table", region="eu-central-1")
            client.delete_item("tnt-123", "TENANT#tnt-123#ENTITY", "ENTITY#456")

            # Verify deletion
            response = dynamodb_table.get_item(
                Key={"PK": "TENANT#tnt-123#ENTITY", "SK": "ENTITY#456"}
            )
            assert response.get("Item") is None


class TestDynamoDBClientQuery:
    """Tests für Query-Operationen."""

    def test_query_returns_items(self, dynamodb_table):
        """query gibt passende Items zurück."""
        with mock_aws():
            # Setup multiple items
            for i in range(3):
                dynamodb_table.put_item(
                    Item={
                        "PK": "TENANT#tnt-123#ENTITY",
                        "SK": f"ENTITY#{i}",
                        "name": f"Entity {i}",
                        "tenant_id": "tnt-123",
                    }
                )

            client = DynamoDBClient("test-table", region="eu-central-1")
            from boto3.dynamodb.conditions import Key

            result = client.query(
                "tnt-123", "TENANT#tnt-123#ENTITY", Key("SK").begins_with("ENTITY#")
            )

            assert len(result.items) == 3

    def test_query_with_pagination(self, dynamodb_table):
        """query mit Pagination."""
        with mock_aws():
            # Setup items
            for i in range(5):
                dynamodb_table.put_item(
                    Item={
                        "PK": "TENANT#tnt-123#ENTITY",
                        "SK": f"ENTITY#{i:03d}",
                        "name": f"Entity {i}",
                        "tenant_id": "tnt-123",
                    }
                )

            client = DynamoDBClient("test-table", region="eu-central-1")
            pagination = PaginationRequest(limit=2)

            result = client.query("tnt-123", "TENANT#tnt-123#ENTITY", pagination=pagination)

            assert len(result.items) == 2

    def test_query_with_filter(self, dynamodb_table):
        """query mit Filter-Expression."""
        with mock_aws():
            # Setup items with different status
            for i in range(3):
                dynamodb_table.put_item(
                    Item={
                        "PK": "TENANT#tnt-123#ENTITY",
                        "SK": f"ENTITY#{i}",
                        "name": f"Entity {i}",
                        "is_active": i % 2 == 0,  # 0 and 2 are active
                        "tenant_id": "tnt-123",
                    }
                )

            client = DynamoDBClient("test-table", region="eu-central-1")
            from boto3.dynamodb.conditions import Attr

            result = client.query(
                "tnt-123",
                "TENANT#tnt-123#ENTITY",
                filter_expression=Attr("is_active").eq(True),
            )

            assert len(result.items) == 2

    def test_query_descending_order(self, dynamodb_table):
        """query mit absteigender Sortierung."""
        with mock_aws():
            # Setup items
            for i in range(3):
                dynamodb_table.put_item(
                    Item={
                        "PK": "TENANT#tnt-123#ENTITY",
                        "SK": f"ENTITY#{i:03d}",
                        "name": f"Entity {i}",
                        "tenant_id": "tnt-123",
                    }
                )

            client = DynamoDBClient("test-table", region="eu-central-1")
            result = client.query(
                "tnt-123", "TENANT#tnt-123#ENTITY", scan_index_forward=False
            )

            # Items should be in descending order
            assert result.items[0]["SK"] > result.items[-1]["SK"]


class TestDynamoDBClientBatch:
    """Tests für Batch-Operationen."""

    def test_batch_get_items(self, dynamodb_table):
        """batch_get_items lädt mehrere Items."""
        with mock_aws():
            # Setup items
            for i in range(3):
                dynamodb_table.put_item(
                    Item={
                        "PK": f"TENANT#tnt-123#ENTITY",
                        "SK": f"ENTITY#{i}",
                        "name": f"Entity {i}",
                        "tenant_id": "tnt-123",
                    }
                )

            client = DynamoDBClient("test-table", region="eu-central-1")
            keys = [
                {"PK": "TENANT#tnt-123#ENTITY", "SK": "ENTITY#0"},
                {"PK": "TENANT#tnt-123#ENTITY", "SK": "ENTITY#1"},
            ]

            items = client.batch_get_items("tnt-123", keys)

            assert len(items) == 2

    def test_batch_get_items_empty_keys(self, dynamodb_table):
        """batch_get_items mit leerer Key-Liste gibt leere Liste zurück."""
        with mock_aws():
            client = DynamoDBClient("test-table", region="eu-central-1")
            items = client.batch_get_items("tnt-123", [])

            assert items == []

    def test_batch_write_items(self, dynamodb_table):
        """batch_write_items schreibt mehrere Items."""
        with mock_aws():
            client = DynamoDBClient("test-table", region="eu-central-1")
            items = [
                {
                    "PK": "TENANT#tnt-123#ENTITY",
                    "SK": f"ENTITY#{i}",
                    "name": f"Entity {i}",
                }
                for i in range(3)
            ]

            client.batch_write_items("tnt-123", items)

            # Verify items were written
            for i in range(3):
                response = dynamodb_table.get_item(
                    Key={"PK": "TENANT#tnt-123#ENTITY", "SK": f"ENTITY#{i}"}
                )
                assert response.get("Item") is not None

    def test_batch_write_items_empty(self, dynamodb_table):
        """batch_write_items mit leerer Liste tut nichts."""
        with mock_aws():
            client = DynamoDBClient("test-table", region="eu-central-1")
            client.batch_write_items("tnt-123", [])
            # No error should be raised


class TestDynamoDBClientScan:
    """Tests für Scan-Operation."""

    def test_scan_with_tenant_filter(self, dynamodb_table):
        """scan filtert nach tenant_id."""
        with mock_aws():
            # Setup items for different tenants
            dynamodb_table.put_item(
                Item={
                    "PK": "TENANT#tnt-123#ENTITY",
                    "SK": "ENTITY#1",
                    "tenant_id": "tnt-123",
                }
            )
            dynamodb_table.put_item(
                Item={
                    "PK": "TENANT#tnt-other#ENTITY",
                    "SK": "ENTITY#2",
                    "tenant_id": "tnt-other",
                }
            )

            client = DynamoDBClient("test-table", region="eu-central-1")
            result = client.scan("tnt-123")

            assert len(result.items) == 1
            assert result.items[0]["tenant_id"] == "tnt-123"


class TestGetDynamoDBClient:
    """Tests für Factory-Funktion."""

    def test_returns_singleton(self):
        """Factory gibt Singleton zurück für gleiche Parameter."""
        DynamoDBClient._instances.clear()

        with mock_aws():
            client1 = get_dynamodb_client("test-table", "eu-central-1")
            client2 = get_dynamodb_client("test-table", "eu-central-1")

            assert client1 is client2

    def test_different_tables_different_instances(self):
        """Verschiedene Tabellen bekommen verschiedene Instanzen."""
        DynamoDBClient._instances.clear()

        with mock_aws():
            client1 = get_dynamodb_client("table-1")
            client2 = get_dynamodb_client("table-2")

            assert client1 is not client2
