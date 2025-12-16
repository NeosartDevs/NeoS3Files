import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from botocore.exceptions import ClientError

from neos3files.client import S3Client
from neos3files.exceptions import S3FileNotFoundError


class MockAIOBoto3Client:
    """Mock for aioboto3 client"""

    def __init__(self):
        self.client = AsyncMock()

    async def __aenter__(self):
        return self.client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class TestS3ClientFixed:
    """Fixed tests for S3Client"""

    @pytest_asyncio.fixture
    async def s3_client(self, s3_config):
        """S3Client instance for tests"""
        client = S3Client(s3_config)
        yield client
        await client.close()

    @pytest.mark.asyncio
    async def test_client_creation(self, s3_config):
        """Test S3Client creation"""
        async with S3Client(s3_config) as client:
            assert client.config == s3_config

    @pytest.mark.asyncio
    async def test_head_object_success(self, s3_client):
        """Test successful head_object call"""
        sample_file_info = {
            "ContentLength": 1024,
            "LastModified": "2024-01-01T00:00:00Z",
            "ETag": '"abc123"',
            "StorageClass": "STANDARD",
            "ContentType": "text/plain",
        }

        mock_boto_client = AsyncMock()
        mock_boto_client.head_object = AsyncMock(return_value=sample_file_info)

        with patch.object(s3_client, "_get_client", return_value=mock_boto_client):
            response = await s3_client.head_object("test/file.txt")

            mock_boto_client.head_object.assert_called_once_with(
                Bucket="test-bucket", Key="test/file.txt"
            )
            assert response == sample_file_info

    @pytest.mark.asyncio
    async def test_head_object_not_found(self, s3_client):
        """Test head_object with 404 error"""
        error_response = {
            "Error": {
                "Code": "NoSuchKey",
                "Message": "The specified key does not exist.",
            },
            "ResponseMetadata": {"HTTPStatusCode": 404},
        }

        mock_boto_client = AsyncMock()
        mock_boto_client.head_object = AsyncMock(
            side_effect=ClientError(error_response, "HeadObject")
        )

        with patch.object(s3_client, "_get_client", return_value=mock_boto_client):
            with pytest.raises(S3FileNotFoundError):
                await s3_client.head_object("nonexistent.txt")

    @pytest.mark.asyncio
    async def test_put_object(self, s3_client):
        """Test put_object with metadata"""
        mock_boto_client = AsyncMock()
        mock_response = {"ETag": '"abc123"'}
        mock_boto_client.put_object = AsyncMock(return_value=mock_response)

        with patch.object(s3_client, "_get_client", return_value=mock_boto_client):
            metadata = {"author": "test", "version": "1.0"}
            response = await s3_client.put_object(
                key="test.txt",
                body=b"content",
                content_type="text/plain",
                metadata=metadata,
            )

            mock_boto_client.put_object.assert_called_once_with(
                Bucket="test-bucket",
                Key="test.txt",
                Body=b"content",
                ContentType="text/plain",
                Metadata=metadata,
            )
            assert response == mock_response

    @pytest.mark.asyncio
    async def test_list_objects(self, s3_client):
        """Test list_objects generator"""
        mock_objects = [
            {
                "Key": "file1.txt",
                "Size": 1024,
                "LastModified": "2024-01-01",
                "ETag": '"etag1"',
            },
            {
                "Key": "file2.txt",
                "Size": 2048,
                "LastModified": "2024-01-02",
                "ETag": '"etag2"',
            },
        ]

        class MockAsyncIterator:
            def __init__(self, items):
                self.items = items.copy()

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.items:
                    return {"Contents": [self.items.pop(0)]}
                raise StopAsyncIteration

        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = MockAsyncIterator(mock_objects)

        mock_boto_client = AsyncMock()
        mock_boto_client.get_paginator = MagicMock(return_value=mock_paginator)

        with patch.object(s3_client, "_get_client", return_value=mock_boto_client):
            objects = []
            async for obj in s3_client.list_objects(prefix="test/"):
                objects.append(obj)

            assert len(objects) == 2
            assert objects[0]["Key"] == "file1.txt"
            assert objects[1]["Key"] == "file2.txt"
