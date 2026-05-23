import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from neos3files.manager import S3Manager
from neos3files.models import FileInfo


class TestS3ManagerFixed:
    """Fixed tests for S3Manager"""

    @pytest_asyncio.fixture
    async def manager(self, s3_config):
        """S3Manager instance for tests"""
        async with S3Manager(config=s3_config) as manager:
            yield manager

    @pytest.mark.asyncio
    async def test_upload_small_file(self, manager, temp_file):
        """Test uploading small file (single part)"""
        file_size = temp_file.stat().st_size

        with patch.object(manager._client, "put_object") as mock_put, patch.object(
            manager._client, "head_object"
        ) as mock_head:
            mock_head.return_value = {
                "ContentLength": file_size,
                "LastModified": "2024-01-01T00:00:00Z",
                "ETag": '"abc123"',
                "StorageClass": "STANDARD",
            }

            file_info = await manager.upload_file(
                local_path=str(temp_file),
                s3_key="uploads/test.txt",
                content_type="text/plain",
            )

            mock_put.assert_called_once()
            assert file_info.key == "uploads/test.txt"
            assert file_info.size == file_size

    @pytest.mark.asyncio
    async def test_upload_large_file(self, manager, temp_file):
        """Test uploading large file (multipart)"""

        manager.chunk_size = 10  # 10 bytes

        file_content = b"test content for multipart upload"
        temp_file.write_bytes(file_content)
        file_size = len(file_content)

        with patch.object(
            manager._client, "create_multipart_upload"
        ) as mock_create, patch.object(
            manager._client, "upload_part"
        ) as mock_upload, patch.object(
            manager._client, "complete_multipart_upload"
        ) as mock_complete, patch.object(manager._client, "head_object") as mock_head:
            mock_create.return_value = {"UploadId": "test-upload-id"}
            mock_upload.return_value = {"ETag": '"etag1"'}
            mock_head.return_value = {
                "ContentLength": file_size,
                "LastModified": "2024-01-01T00:00:00Z",
                "ETag": '"abc123"',
                "StorageClass": "STANDARD",
            }

            file_info = await manager.upload_file(
                local_path=str(temp_file), s3_key="uploads/large.txt"
            )

            assert mock_create.called

            expected_chunks = (file_size + 9) // 10
            assert mock_upload.call_count == expected_chunks
            assert mock_complete.called
            assert file_info.key == "uploads/large.txt"

    @pytest.mark.asyncio
    async def test_purge(self, manager):
        """Test purging bucket"""

        mock_files = [
            FileInfo(key="file1.txt", size=1024, last_modified=None, etag="etag1"),
            FileInfo(key="file2.txt", size=2048, last_modified=None, etag="etag2"),
        ]

        async def mock_list_generator():
            for file in mock_files:
                yield file

        async def mock_delete_files(keys):
            return len(keys)

        with patch.object(
            manager, "list_files", return_value=mock_list_generator()
        ), patch.object(
            manager, "delete_files", side_effect=mock_delete_files
        ), patch.object(manager._client, "_get_client") as mock_get_client:

            async def async_page_generator():
                yield {
                    "Uploads": [
                        {"Key": "upload1.txt", "UploadId": "id1"},
                        {"Key": "upload2.txt", "UploadId": "id2"},
                    ]
                }

            mock_paginator = MagicMock()
            mock_paginator.paginate.return_value = async_page_generator()

            mock_client = MagicMock()
            mock_client.get_paginator = MagicMock(return_value=mock_paginator)
            mock_client.abort_multipart_upload = AsyncMock()

            mock_get_client.return_value = mock_client

            deleted_count = await manager.purge()

            assert deleted_count == 4
            assert mock_client.abort_multipart_upload.call_count == 2
