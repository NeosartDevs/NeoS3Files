
import asyncio
import pytest
from typing import Generator
import os

from neos3files.models import S3Config


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for the test session"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def s3_config() -> S3Config:
    """S3 configuration for tests"""
    return S3Config(
        endpoint_url="https://s3.example.com",
        bucket="test-bucket",
        access_key="test-access-key",
        secret_key="test-secret-key",
        region="us-east-1"
    )


@pytest.fixture
def temp_file(tmp_path):
    """Create temporary file for testing"""
    file_path = tmp_path / "test_file.txt"
    content = b"Hello, World! This is a test file.\n" * 100  # ~4KB
    file_path.write_bytes(content)
    return file_path