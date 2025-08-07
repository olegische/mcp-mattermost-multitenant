"""Manages a shared httpx.AsyncClient for the application."""

from typing import Optional

import httpx

from .config import ServiceConfig


class ClientManager:
    """Manages a singleton httpx.AsyncClient instance."""

    _client: Optional[httpx.AsyncClient] = None

    def get_client(self, config: ServiceConfig) -> httpx.AsyncClient:
        """
        Retrieves the existing client or creates a new one if it doesn't exist.
        """
        if self._client is None:
            headers = {}
            if config.MATTERMOST_API_KEY:
                headers["Authorization"] = f"Bearer {config.MATTERMOST_API_KEY}"
            elif config.MATTERMOST_COOKIE:
                headers["Cookie"] = f"MMAUTHTOKEN={config.MATTERMOST_COOKIE}"
                if config.MATTERMOST_CSRF_TOKEN:
                    headers["X-CSRF-Token"] = config.MATTERMOST_CSRF_TOKEN

            self._client = httpx.AsyncClient(
                base_url=config.MATTERMOST_BASE_URL, headers=headers
            )
        return self._client

    async def close_client(self):
        """Closes the client if it exists."""
        if self._client:
            await self._client.aclose()
            self._client = None


client_manager = ClientManager()
