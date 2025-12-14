from datetime import datetime

from neos3files.models import (
    S3Config,
    FileInfo,
    StorageClass,
    UploadProgress,
    UsageStats,
)


class TestS3Config:
    """Test S3Config model"""

    def test_s3_config_creation(self):
        """Test S3Config creation"""
        config = S3Config(
            endpoint_url="https://s3.example.com",
            bucket="test-bucket",
            access_key="access-key",
            secret_key="secret-key",
            region="us-east-1",
        )

        assert config.endpoint_url == "https://s3.example.com"
        assert config.bucket == "test-bucket"
        assert config.access_key == "access-key"
        assert config.secret_key == "secret-key"
        assert config.region == "us-east-1"
        assert config.verify_ssl is True

    def test_from_dict(self):
        """Test creating config from dictionary"""
        config_dict = {
            "endpoint_url": "https://s3.example.com",
            "bucket": "test-bucket",
            "access_key": "access-key",
            "secret_key": "secret-key",
            "region": "eu-west-1",
            "verify_ssl": False,
        }

        config = S3Config.from_dict(config_dict)

        assert config.endpoint_url == config_dict["endpoint_url"]
        assert config.bucket == config_dict["bucket"]
        assert config.access_key == config_dict["access_key"]
        assert config.secret_key == config_dict["secret_key"]
        assert config.region == config_dict["region"]
        assert config.verify_ssl is False

    def test_to_dict(self):
        """Test converting config to dictionary"""
        config = S3Config(
            endpoint_url="https://s3.example.com",
            bucket="test-bucket",
            access_key="access-key",
            secret_key="secret-key",
            region="us-east-1",
        )

        config_dict = config.to_dict()

        assert config_dict["endpoint_url"] == config.endpoint_url
        assert config_dict["bucket"] == config.bucket
        assert config_dict["access_key"] == config.access_key
        assert config_dict["secret_key"] == config.secret_key
        assert config_dict["region"] == config.region


class TestFileInfo:
    """Test FileInfo model"""

    def test_file_info_creation(self):
        """Test FileInfo creation"""
        now = datetime.now()
        file_info = FileInfo(
            key="folder/file.txt",
            size=1048576,  # 1MB
            last_modified=now,
            etag="abc123",
            storage_class=StorageClass.STANDARD,
            content_type="text/plain",
        )

        assert file_info.key == "folder/file.txt"
        assert file_info.size == 1048576
        assert file_info.last_modified == now
        assert file_info.etag == "abc123"
        assert file_info.storage_class == StorageClass.STANDARD
        assert file_info.content_type == "text/plain"

    def test_size_properties(self):
        """Test size conversion properties"""
        file_info = FileInfo(
            key="test.txt",
            size=1073741824,  # 1GB
            last_modified=datetime.now(),
            etag="abc123",
        )

        assert file_info.size_mb == 1024.0  # 1GB = 1024MB
        assert file_info.size_gb == 1.0

    def test_filename_property(self):
        """Test filename extraction"""
        file_info = FileInfo(
            key="folder/subfolder/file.txt",
            size=1024,
            last_modified=datetime.now(),
            etag="abc123",
        )

        assert file_info.filename == "file.txt"
        assert file_info.directory == "folder/subfolder"

    def test_no_directory(self):
        """Test file without directory"""
        file_info = FileInfo(
            key="file.txt", size=1024, last_modified=datetime.now(), etag="abc123"
        )

        assert file_info.directory == ""
        assert file_info.filename == "file.txt"


class TestUploadProgress:
    """Test UploadProgress model"""

    def test_upload_progress(self):
        """Test UploadProgress creation"""
        progress = UploadProgress(
            key="test.txt",
            total_size=1000000,
            uploaded_size=500000,
            completed_parts=3,
            total_parts=10,
        )

        assert progress.key == "test.txt"
        assert progress.total_size == 1000000
        assert progress.uploaded_size == 500000
        assert progress.completed_parts == 3
        assert progress.total_parts == 10
        assert progress.progress_percent == 50.0

    def test_zero_size_progress(self):
        """Test progress with zero total size"""
        progress = UploadProgress(
            key="test.txt",
            total_size=0,
            uploaded_size=0,
            completed_parts=0,
            total_parts=0,
        )

        assert progress.progress_percent == 0.0


class TestUsageStats:
    """Test UsageStats model"""

    def test_usage_stats_creation(self):
        """Test UsageStats creation"""
        stats = UsageStats(
            total_files=100,
            total_size_bytes=1073741824,  # 1GB
            total_size_gb=1.0,
            total_size_mb=1024.0,
            avg_file_size_mb=10.24,
            by_storage_class={StorageClass.STANDARD: 80, StorageClass.GLACIER: 20},
        )

        assert stats.total_files == 100
        assert stats.total_size_bytes == 1073741824
        assert stats.total_size_gb == 1.0
        assert stats.total_size_mb == 1024.0
        assert stats.avg_file_size_mb == 10.24
        assert stats.by_storage_class[StorageClass.STANDARD] == 80
        assert stats.by_storage_class[StorageClass.GLACIER] == 20
