import pytest
import tempfile
import hashlib
from pathlib import Path

from neos3files.utils import calculate_etag, parse_s3_url


class TestCalculateEtag:
    """Test ETag calculation"""

    def test_small_file_etag(self):
        """Test ETag for small file (single part)"""
        with tempfile.NamedTemporaryFile(delete=False, mode="wb") as f:
            content = b"Hello, World!"
            f.write(content)
            f.flush()

            expected_etag = hashlib.md5(content).hexdigest()
            actual_etag = calculate_etag(f.name)

            assert actual_etag == expected_etag

        Path(f.name).unlink()

    def test_large_file_etag(self):
        """Test ETag for large file (multipart)"""
        with tempfile.NamedTemporaryFile(delete=False, mode="wb") as f:
            chunk_size = 8 * 1024 * 1024  # 8MB
            chunk = b"X" * (chunk_size // 2)  # 4MB chunk

            for _ in range(3):
                f.write(chunk)
            f.flush()

            actual_etag = calculate_etag(f.name, chunk_size=chunk_size)

            assert "-" in actual_etag
            assert actual_etag.endswith("-2")  # 12MB / 8MB = 2 parts

        Path(f.name).unlink()


class TestParseS3Url:
    """Test S3 URL parsing"""

    def test_s3_scheme_url(self):
        """Test parsing s3:// URLs"""
        bucket, key = parse_s3_url("s3://my-bucket/folder/file.txt")
        assert bucket == "my-bucket"
        assert key == "folder/file.txt"

    def test_s3_scheme_root(self):
        """Test parsing s3:// URLs at root"""
        bucket, key = parse_s3_url("s3://my-bucket/")
        assert bucket == "my-bucket"
        assert key == ""

    def test_https_s3_url_virtual_host(self):
        """Test parsing https://bucket.s3.amazonaws.com/key URLs (virtual host style)"""
        bucket, key = parse_s3_url("https://my-bucket.s3.amazonaws.com/folder/file.txt")
        assert bucket == "my-bucket"
        assert key == "folder/file.txt"

    def test_https_s3_url_path_style(self):
        """Test parsing https://s3.amazonaws.com/bucket/key URLs (path style)"""
        bucket, key = parse_s3_url("https://s3.amazonaws.com/my-bucket/folder/file.txt")
        assert bucket == "my-bucket"
        assert key == "folder/file.txt"

    def test_custom_endpoint_url(self):
        """Test parsing custom endpoint URLs"""
        bucket, key = parse_s3_url(
            "https://storage.example.com/my-bucket/folder/file.txt"
        )
        assert bucket == "my-bucket"
        assert key == "folder/file.txt"

    def test_invalid_scheme(self):
        """Test invalid URL scheme"""
        with pytest.raises(ValueError, match="Invalid S3 URL scheme"):
            parse_s3_url("ftp://example.com/file.txt")
