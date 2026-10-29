"""
Sync HTTP client stub.

Phase 11/12 will implement the actual backend API client.
"""


class SyncClient:
    """HTTP client for uploading records to the backend."""

    def __init__(self, base_url: str = ""):
        self.base_url = base_url

    def upload(self, entity_type: str, payload: dict) -> dict:
        """Upload a single entity to the backend.

        Currently a stub — returns a mock response.
        """
        return {
            "status": "not_implemented",
            "message": "Backend sync is not yet configured.",
        }

    def health_check(self) -> bool:
        """Check if the backend is reachable."""
        return False
