"""
Mocks for aioboto3
"""

from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any


class AioBoto3Mock:
    """Mock for aioboto3"""

    def __init__(self):
        self.mock_client = None
        self.mock_session = None
        self._setup_mocks()

    def _setup_mocks(self):
        """Setup mock objects"""

        self.mock_client = AsyncMock()

        self.mock_session = MagicMock()
        self.mock_session.client.return_value.__aenter__.return_value = self.mock_client
        self.mock_session.client.return_value.__aexit__.return_value = None

    def get_session_mock(self):
        """Get mock session"""
        return self.mock_session

    def get_client_mock(self):
        """Get mock client"""
        return self.mock_client

    def configure_client_response(
        self, method: str, response: Dict[str, Any], side_effect: Exception = None
    ):
        """Configure client method response"""
        mock_method = getattr(self.mock_client, method)

        if side_effect:
            mock_method.side_effect = side_effect
        else:
            mock_method.return_value = response

    def reset_mocks(self):
        """Reset all mocks"""
        self.mock_client.reset_mock()
        self.mock_session.reset_mock()


mock_instance = AioBoto3Mock()
