"""
Integration tests with real S3 (requires credentials)
Marked as integration tests - run separately
"""

import pytest
import os
from datetime import datetime
from typing import Optional

from neos3files.manager import S3Manager
from neos3files.models import S3Config


# These tests require actual S3 credentials
# Set environment variables or use pytest markers to skip by default
pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_INTEGRATION_TESTS"),
    reason="Integration tests require S3 credentials",
)


@pytest.fixture
def integration_config() -> Optional[S3Config]:
    """Get integration test configuration from environment"""
    access_key = os.getenv("S3_ACCESS_KEY")
    secret_key = os.getenv("S3_SECRET_KEY")
    bucket = os.getenv("S3_BUCKET")
    endpoint = os.getenv("S3_ENDPOINT")
    region = os.getenv("S3_REGION", "us-east-1")

    if not all([access_key, secret_key, bucket, endpoint]):
        pytest.skip("S3 credentials not configured")

    return S3Config(
        endpoint_url=endpoint,
        bucket=bucket,
        access_key=access_key,
        secret_key=secret_key,
        region=region,
        verify_ssl=False,
    )


@pytest.fixture
async def integration_manager(integration_config):
    """Integration test manager"""
    async with S3Manager(config=integration_config) as manager:
        try:
            await manager.purge()
        except Exception:
            pass

        yield manager

        try:
            await manager.purge()
        except Exception:
            pass


@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration_upload_download(integration_manager, tmp_path):
    """Test upload and download with real S3"""

    test_content = b"Integration test content"
    test_file = tmp_path / "test_upload.txt"
    test_file.write_bytes(test_content)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    s3_key = f"test/{timestamp}/upload_test.txt"

    file_info = await integration_manager.upload_file(
        local_path=str(test_file), s3_key=s3_key, content_type="text/plain"
    )

    assert file_info.key == s3_key
    assert file_info.size == len(test_content)

    exists = await integration_manager.exists(s3_key)
    assert exists is True

    download_path = tmp_path / "test_download.txt"
    downloaded = await integration_manager.download_file(
        s3_key=s3_key, local_path=str(download_path)
    )

    assert downloaded == str(download_path)
    assert download_path.exists()

    downloaded_content = download_path.read_bytes()
    assert downloaded_content == test_content

    await integration_manager.delete_file(s3_key)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration_list_files(integration_manager):
    """Test listing files with real S3"""

    files_to_upload = 5
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for i in range(files_to_upload):
        s3_key = f"test/{timestamp}/file_{i}.txt"

        content = f"Test file {i}".encode()

        await integration_manager._client.put_object(
            key=s3_key, body=content, content_type="text/plain"
        )

    files = []
    async for file_info in integration_manager.list_files(prefix=f"test/{timestamp}/"):
        files.append(file_info)

    assert len(files) == files_to_upload

    keys = [file_info.key for file_info in files]
    await integration_manager.delete_files(keys)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration_usage_stats(integration_manager):
    """Test usage statistics with real S3"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for i in range(3):
        s3_key = f"test/{timestamp}/stats_file_{i}.txt"
        content = b"X" * 1024  # 1KB each

        await integration_manager._client.put_object(
            key=s3_key, body=content, content_type="text/plain"
        )

    stats = await integration_manager.get_usage_stats()

    assert stats.total_files >= 3
    assert stats.total_size_bytes >= 3072  # 3 * 1024

    keys = [f"test/{timestamp}/stats_file_{i}.txt" for i in range(3)]
    await integration_manager.delete_files(keys)
