# NeoS3Files

A high-level async Python library for working with S3-compatible storage.

[![Python](https://img.shields.io/badge/Python-3.7%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Version](https://img.shields.io/badge/Version-2.0.0-orange)](https://pypi.org/project/neos3files/)

NeoS3Files provides a convenient async interface for AWS S3, MinIO, and other S3-compatible storage services. Built on top of `aioboto3` and `aiofiles`, it delivers fully non-blocking I/O operations.

## Features

- **Fully async API** — all I/O operations are non-blocking, built on `asyncio`
- **Automatic multipart uploads** — large files are automatically split into parts and uploaded concurrently
- **Progress tracking** — callbacks for monitoring upload progress
- **Connection pooling** — automatic connection reuse for maximum performance
- **Exception hierarchy** — typed exceptions for all S3 error types
- **Utilities** — filename sanitization, S3 URL parsing, size formatting, ETag calculation
- **S3-compatible storage support** — AWS S3, MinIO, DigitalOcean Spaces, Yandex Cloud, VK Cloud, and more

## Installation

```bash
pip install neos3files
```


## Requirements

- Python 3.7+
- `aioboto3` >= 11.0.0
- `aiofiles` >= 23.0.0
- `botocore` >= 1.29.0

## Quick Start

```python
import asyncio
from neos3files import S3Config, S3Manager

async def main():
    # Create configuration
    config = S3Config(
        endpoint_url="https://s3.example.com",
        bucket="my-bucket",
        access_key="your-access-key",
        secret_key="your-secret-key",
        region="us-east-1",
    )

    async with S3Manager(config) as manager:
        # Upload a file
        info = await manager.upload_file("local_file.txt", "remote/file.txt")
        print(f"Uploaded: {info.key}, size: {info.size_mb:.2f} MB")

        # Check if file exists
        exists = await manager.exists("remote/file.txt")
        print(f"File exists: {exists}")

        # Get file metadata
        info = await manager.get_file_info("remote/file.txt")
        print(f"Type: {info.content_type}, Modified: {info.last_modified}")

        # Download a file
        await manager.download_file("remote/file.txt", "downloaded.txt")

        # Copy and move
        await manager.copy_file("remote/file.txt", "remote/backup.txt")
        await manager.move_file("remote/file.txt", "remote/renamed.txt")

        # Delete a file
        await manager.delete_file("remote/backup.txt")

asyncio.run(main())
```

## Architecture

The library consists of two main layers:

| Component | Purpose |
|-----------|---------|
| `S3Client` | Low-level async client with connection pooling. Provides direct access to S3 operations |
| `S3Manager` | High-level manager with automatic multipart uploads, progress tracking, and convenient methods |

### S3Config

Connection configuration for S3 storage:

```python
from neos3files import S3Config

config = S3Config(
    endpoint_url="https://s3.example.com",  # S3-compatible storage endpoint URL
    bucket="my-bucket",                      # Bucket name
    access_key="AKIAIOSFODNN7EXAMPLE",       # Access key ID
    secret_key="wJalrXUtnFEMI/K7MDENG/...",  # Secret access key
    region="us-west-2",                      # AWS region (optional)
    verify_ssl=True,                         # Verify SSL certificates
    timeout=30,                              # Connection timeout in seconds
    max_pool_connections=10,                 # Maximum connections in pool
)

# Create from dictionary
config = S3Config.from_dict({
    "endpoint_url": "https://s3.example.com",
    "bucket": "my-bucket",
    "access_key": "key",
    "secret_key": "secret",
})

# Export to dictionary
config_dict = config.to_dict()
```

### S3Manager

High-level interface for everyday operations.

#### Instantiation

```python
# Standard approach
manager = S3Manager(
    config,
    chunk_size=50 * 1024 * 1024,  # Part size: 50 MB
    max_concurrent_uploads=5,     # Max concurrent part uploads
)

# Quick creation from credentials
manager = S3Manager.from_credentials(
    endpoint_url="https://s3.example.com",
    bucket="my-bucket",
    access_key="key",
    secret_key="secret",
    chunk_size=10 * 1024 * 1024,
)
```

#### File uploads with progress tracking

```python
from neos3files import UploadProgress

def on_progress(progress: UploadProgress):
    print(f"{progress.key}: {progress.progress_percent:.1f}% "
          f"({progress.completed_parts}/{progress.total_parts} parts)")

info = await manager.upload_file(
    "large_video.mp4",
    "videos/video.mp4",
    content_type="video/mp4",
    metadata={"author": "user123", "version": "1.0"},
    progress_callback=on_progress,
)
print(f"Done! Size: {info.size_mb:.2f} MB")
```

#### Listing files

```python
# All files in the bucket
async for file_info in manager.list_files():
    print(f"{file_info.key}: {file_info.size_mb:.2f} MB")

# Filter by prefix
async for file_info in manager.list_files(prefix="photos/2024/"):
    print(f"{file_info.key}: {file_info.filename}")

# Non-recursive (only files at prefix root)
async for file_info in manager.list_files(prefix="data/", recursive=False, limit=100):
    print(file_info.key)
```

#### Batch deletion

```python
keys = ["file1.txt", "file2.txt", "file3.txt"]
deleted = await manager.delete_files(keys)
print(f"Deleted files: {deleted}")
```

#### Usage statistics

```python
stats = await manager.get_usage_stats()

print(f"Total files: {stats.total_files}")
print(f"Total size: {stats.total_size_gb:.2f} GB")
print(f"Average size: {stats.avg_file_size_mb:.2f} MB")
print(f"By storage class: {stats.by_storage_class}")
```

#### Full bucket purge

```python
# ⚠️ Warning: irreversible operation!
deleted = await manager.purge()
print(f"Deleted objects: {deleted}")
```

### S3Client

Low-level client for direct S3 operations. Use when you need full control.

```python
from neos3files import S3Client

async with S3Client(config) as client:
    # Object metadata
    info = await client.head_object("file.txt")
    print(f"Size: {info['ContentLength']} bytes")

    # Upload a small file
    await client.put_object(
        "data.txt",
        b"Hello, World!",
        content_type="text/plain",
        metadata={"source": "api"},
    )

    # Streaming download
    import aiofiles
    async with aiofiles.open("local.txt", "wb") as f:
        await client.download_fileobj("remote.txt", f)

    # Copy and delete
    await client.copy_object("source.txt", "dest.txt")
    await client.delete_object("old.txt")

    # Manual multipart upload
    upload = await client.create_multipart_upload("large.bin")
    upload_id = upload["UploadId"]

    parts = []
    for i, chunk in enumerate(chunks, 1):
        result = await client.upload_part("large.bin", upload_id, i, chunk)
        parts.append({"PartNumber": i, "ETag": result["ETag"]})

    await client.complete_multipart_upload("large.bin", upload_id, parts)

    # Or abort on error
    await client.abort_multipart_upload("large.bin", upload_id)
```

## Data Models

### FileInfo

```python
info = await manager.get_file_info("path/file.txt")

print(info.key)             # "path/file.txt"
print(info.size)            # size in bytes
print(info.size_mb)         # size in MB
print(info.size_gb)         # size in GB
print(info.filename)         # "file.txt"
print(info.directory)        # "path"
print(info.content_type)    # "text/plain"
print(info.last_modified)   # datetime object
print(info.etag)            # ETag without quotes
print(info.storage_class)   # StorageClass.STANDARD
print(info.metadata)         # dict[str, str]
```

### UploadProgress

```python
@dataclass
class UploadProgress:
    key: str                # Object key being uploaded
    total_size: int         # Total size in bytes
    uploaded_size: int      # Bytes uploaded so far
    completed_parts: int    # Completed parts
    total_parts: int        # Total parts
    progress_percent: float # Progress percentage (0.0 - 100.0)
```

### UsageStats

```python
@dataclass
class UsageStats:
    total_files: int                              # Number of files
    total_size_bytes: int                         # Total size in bytes
    total_size_gb: float                          # Total size in GB
    total_size_mb: float                          # Total size in MB
    avg_file_size_mb: float                       # Average file size in MB
    by_storage_class: dict[StorageClass, int]     # Distribution by storage class
```

### StorageClass

```python
class StorageClass(str, Enum):
    STANDARD            # Standard storage
    STANDARD_IA         # Infrequent access
    GLACIER             # Archive storage
    DEEP_ARCHIVE        # Deep archive
    INTELLIGENT_TIERING # Automatic tier selection
```

## Exceptions

All exceptions inherit from the base `S3Error` class:

| Exception | Description |
|-----------|-------------|
| `S3Error` | Base exception for all S3 errors |
| `S3ConnectionError` | Failed to connect to S3 service |
| `S3UploadError` | File upload failed |
| `S3DownloadError` | File download failed |
| `S3FileNotFoundError` | File not found in storage |
| `S3BucketNotFoundError` | Bucket not found |
| `S3PermissionError` | Access denied (insufficient permissions) |
| `S3ConfigurationError` | Invalid configuration |

Error handling example:

```python
from neos3files import (
    S3FileNotFoundError,
    S3PermissionError,
    S3ConnectionError,
    S3Error,
)

try:
    info = await manager.get_file_info("important.txt")
except S3FileNotFoundError:
    print("File not found")
except S3PermissionError:
    print("Access denied")
except S3ConnectionError:
    print("Connection error")
except S3Error as e:
    print(f"S3 error: {e.message}")
    if e.original_error:
        print(f"Original error: {e.original_error}")
```

## Utilities

```python
from neos3files import sanitize_filename, parse_s3_url, build_s3_url, format_size

# Filename sanitization
safe = sanitize_filename("my file (1).txt")
print(safe)  # "my_file_1.txt"

# S3 URL parsing
bucket, key = parse_s3_url("s3://my-bucket/path/to/file.txt")
print(bucket, key)  # "my-bucket", "path/to/file.txt"

bucket, key = parse_s3_url("https://s3.amazonaws.com/bucket/key.txt")
print(bucket, key)  # "bucket", "key.txt"

# S3 URL building
url = build_s3_url("my-bucket", "folder/file.txt")
print(url)  # "s3://my-bucket/folder/file.txt"

url = build_s3_url("my-bucket", "file.txt", "https://s3.example.com")
print(url)  # "https://s3.example.com/my-bucket/file.txt"

# Size formatting
print(format_size(1024))        # "1.00 KB"
print(format_size(1073741824))  # "1.00 GB"
print(format_size(0))           # "0 B"
```

## Supported Storage Providers

The library works with any S3-compatible storage:

- **AWS S3**
- **MinIO**
- **DigitalOcean Spaces**
- **Yandex Object Storage**
- **VK Cloud Storage**
- **Selectel Object Storage**
- **Ceph (RADOS Gateway)**
- and other S3-compatible services

## Development

```bash
# Clone the repository
git clone https://github.com/NeosartDevs/NeoS3Files.git
cd NeoS3Files

# Install development dependencies
pip install -e .[dev]

# Run tests
pytest

# Run tests with coverage
pytest --cov=neos3files --cov-report=html

# Code formatting
black neos3files tests

# Type checking
mypy neos3files
```

## License

MIT License. See [LICENSE](LICENSE) for details.

## Links

- [Source Code](https://github.com/NeosartDevs/NeoS3Files)
- [Bug Tracker](https://github.com/NeosartDevs/NeoS3Files/issues)
- [PyPI](https://pypi.org/project/neos3files/)
