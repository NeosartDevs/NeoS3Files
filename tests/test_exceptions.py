from neos3files.exceptions import (
    S3Error,
    S3ConnectionError,
    S3UploadError,
    S3DownloadError,
    S3FileNotFoundError,
    S3BucketNotFoundError,
    S3PermissionError,
    S3ConfigurationError,
)


class TestS3Exceptions:
    """Test S3 exception hierarchy"""

    def test_base_exception(self):
        """Test base S3Error"""
        error = S3Error("Test error")
        assert str(error) == "Test error"
        assert error.original_error is None

    def test_exception_with_original_error(self):
        """Test S3Error with original exception"""
        original = ValueError("Original error")
        error = S3Error("Test error", original)

        assert str(error) == "Test error"
        assert error.original_error == original

    def test_s3_connection_error(self):
        """Test S3ConnectionError"""
        error = S3ConnectionError("Connection failed")
        assert isinstance(error, S3Error)
        assert str(error) == "Connection failed"

    def test_s3_upload_error(self):
        """Test S3UploadError with key"""
        original = Exception("Network error")
        error = S3UploadError("test-key", "Upload failed", original)

        assert error.key == "test-key"
        assert str(error) == "Failed to upload 'test-key': Upload failed"
        assert error.original_error == original

    def test_s3_download_error(self):
        """Test S3DownloadError with key"""
        error = S3DownloadError("test-key", "Download failed")

        assert error.key == "test-key"
        assert str(error) == "Failed to download 'test-key': Download failed"

    def test_s3_file_not_found_error(self):
        """Test S3FileNotFoundError"""
        error = S3FileNotFoundError("missing-file.txt")

        assert str(error) == "File 'missing-file.txt' not found in S3"
        assert isinstance(error, S3Error)

    def test_s3_bucket_not_found_error(self):
        """Test S3BucketNotFoundError"""
        error = S3BucketNotFoundError("nonexistent-bucket")

        assert str(error) == "Bucket 'nonexistent-bucket' not found"

    def test_s3_permission_error(self):
        """Test S3PermissionError"""
        error = S3PermissionError("Access denied")

        assert str(error) == "Access denied"
        assert isinstance(error, S3Error)

    def test_s3_configuration_error(self):
        """Test S3ConfigurationError"""
        error = S3ConfigurationError("Invalid configuration")

        assert str(error) == "Invalid configuration"
        assert isinstance(error, S3Error)
