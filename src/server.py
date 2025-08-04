"""MCP server definition.

This module defines the MCP server instance and registers the tools that wrap the
Mattermost API.
"""

import logging
from typing import Any, List, Optional

import httpx
from fastapi.middleware.cors import CORSMiddleware
from starlette.applications import Starlette
from starlette.middleware import Middleware

from mcp.server.fastmcp import Context, FastMCP

from .utils.dependencies import (
    ServiceConfig,
    get_mattermost_client,
    get_service_config,
)

# Get a module-level logger
logger = logging.getLogger(__name__)


class CustomFastMCP(FastMCP):
    """Custom FastMCP server with CORS middleware."""

    def _add_cors_middleware(self, app: Starlette) -> Starlette:
        """A helper to add CORS middleware to a Starlette app."""
        app.user_middleware.insert(
            0,
            Middleware(
                CORSMiddleware,
                allow_origin_regex=".*",  # Allow any origin
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            ),
        )
        app.middleware_stack = app.build_middleware_stack()
        return app

    def sse_app(self, mount_path: str | None = None) -> Starlette:
        """Overrides the default sse_app to inject CORS middleware."""
        app = super().sse_app(mount_path)
        return self._add_cors_middleware(app)

    def streamable_http_app(self) -> Starlette:
        """Overrides the default streamable_http_app to inject CORS middleware."""
        app = super().streamable_http_app()
        return self._add_cors_middleware(app)


def build_server(config: ServiceConfig) -> CustomFastMCP:
    """Build and configure the FastMCP server instance.

    Args:
        config: The server's service configuration.

    Returns:
        A configured CustomFastMCP instance.
    """
    logger.info(
        "Initializing FastMCP server",
        extra={"host": config.MCP_HOST, "port": config.MCP_PORT},
    )
    return CustomFastMCP(
        "mcp-mattermost",
        host=config.MCP_HOST,
        port=config.MCP_PORT,
    )


# Get the base configuration for server initialization.
# Tool-specific calls will use get_service_config(context) for request-scoped config.
server_config = get_service_config(Context())
mcp_app = build_server(server_config)


async def handle_api_error(response: httpx.Response) -> None:
    """Handle non-2xx API responses by raising a ValueError."""
    try:
        # Try to parse the JSON body for a 'detail' key.
        error_detail = response.json().get("detail", response.text)
    except Exception:
        # Fallback to the raw response text if JSON parsing fails.
        error_detail = response.text

    raise ValueError(
        f"API Error: {response.status_code} {response.reason_phrase} - {error_detail}"
    )


@mcp_app.tool()
async def get_channel_unread(
    context: Context, user_id: str, channel_id: str
) -> dict[str, Any]:
    """Get the total unread messages and mentions for a channel for a user.

    Corresponds to the GET /api/v4/users/{user_id}/channels/{channel_id}/unread endpoint.

    Args:
        context: The MCP request context.
        user_id: The ID of the user. Can be 'me' for the current user.
        channel_id: The ID of the channel to check for unread messages.

    Returns:
        A dictionary containing unread count information with the following structure:
        - team_id (str): The ID of the team the channel belongs to.
        - channel_id (str): The ID of the channel.
        - msg_count (int): The total number of unread messages.
        - mention_count (int): The number of unread messages that are mentions.
    """
    config = get_service_config(context)
    async with get_mattermost_client(config) as client:
        try:
            response = await client.get(
                f"/api/v4/users/{user_id}/channels/{channel_id}/unread"
            )
            if response.status_code != 200:
                await handle_api_error(response)
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Request to Mattermost API failed: {e}")
            raise ValueError(f"Failed to connect to the Mattermost API: {e}")


@mcp_app.tool()
async def get_post_thread(
    context: Context,
    post_id: str,
    perPage: int = 0,
    fromPost: str = "",
    fromCreateAt: int = 0,
    fromUpdateAt: int = 0,
    direction: str = "",
    skipFetchThreads: bool = False,
    collapsedThreads: bool = False,
    collapsedThreadsExtended: bool = False,
    updatesOnly: bool = False,
) -> dict[str, Any]:
    """Get a post and the rest of the posts in the same thread.

    Corresponds to the GET /api/v4/posts/{post_id}/thread endpoint.

    Args:
        context: The MCP request context.
        post_id: ID of a post in the thread.
        perPage: The number of posts per page.
        fromPost: The post_id to return the next page of posts from.
        fromCreateAt: The create_at timestamp to return the next page of posts from.
        fromUpdateAt: The update_at timestamp to return the next page of posts from.
        direction: The direction to return the posts. Either 'up' or 'down'.
        skipFetchThreads: Whether to skip fetching threads or not.
        collapsedThreads: Whether the client uses Collapsed Reply Threads or not.
        collapsedThreadsExtended: Whether to return associated users.
        updatesOnly: This flag is used to make the API work with the updateAt value.

    Returns:
        A dictionary representing a list of posts in the thread (PostList).
        - order (List[str]): A list of post IDs in order.
        - posts (Dict[str, Post]): A dictionary of post objects, keyed by post ID.
        - next_post_id (str): The ID of the next post.
        - prev_post_id (str): The ID of the previous post.
        - has_next (bool): Whether there are more items after this page.
    """
    config = get_service_config(context)
    params = {
        "perPage": perPage,
        "fromPost": fromPost,
        "fromCreateAt": fromCreateAt,
        "fromUpdateAt": fromUpdateAt,
        "direction": direction,
        "skipFetchThreads": skipFetchThreads,
        "collapsedThreads": collapsedThreads,
        "collapsedThreadsExtended": collapsedThreadsExtended,
        "updatesOnly": updatesOnly,
    }
    async with get_mattermost_client(config) as client:
        try:
            response = await client.get(
                f"/api/v4/posts/{post_id}/thread", params=params
            )
            if response.status_code != 200:
                await handle_api_error(response)
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Request to Mattermost API failed: {e}")
            raise ValueError(f"Failed to connect to the Mattermost API: {e}")


@mcp_app.tool()
async def create_post(
    context: Context,
    channel_id: str,
    message: str,
    root_id: str = "",
    file_ids: Optional[List[str]] = None,
    props: Optional[dict] = None,
    metadata: Optional[dict] = None,
    set_online: bool = True,
) -> dict[str, Any]:
    """Create a new post in a channel.

    Corresponds to the POST /api/v4/posts endpoint.

    Args:
        context: The MCP request context.
        channel_id: The channel ID to post in.
        message: The message contents, can be formatted with Markdown.
        root_id: The post ID to comment on.
        file_ids: A list of file IDs to associate with the post.
        props: A general JSON property bag to attach to the post.
        metadata: A JSON object to add post metadata, e.g., priority.
        set_online: Whether to set the user status as online or not.

    Returns:
        A dictionary representing the created post object.
        - id (str): The post ID.
        - create_at (int): Creation timestamp.
        - update_at (int): Update timestamp.
        - user_id (str): The user ID of the author.
        - channel_id (str): The channel ID.
        - message (str): The post message.
        ... and other post fields.
    """
    config = get_service_config(context)
    post_data = {
        "channel_id": channel_id,
        "message": message,
        "root_id": root_id,
        "file_ids": file_ids or [],
        "props": props or {},
        "metadata": metadata or {},
    }
    params = {"set_online": set_online}
    async with get_mattermost_client(config) as client:
        try:
            response = await client.post("/api/v4/posts", json=post_data, params=params)
            if response.status_code != 201:
                await handle_api_error(response)
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Request to Mattermost API failed: {e}")
            raise ValueError(f"Failed to connect to the Mattermost API: {e}")


@mcp_app.tool()
async def create_direct_channel(
    context: Context, user_ids: List[str]
) -> dict[str, Any]:
    """Create a new direct message channel between two users.

    Corresponds to the POST /api/v4/channels/direct endpoint.

    Args:
        context: The MCP request context.
        user_ids: A list containing the two user IDs for the direct channel.

    Returns:
        A dictionary representing the created channel object.
        - id (str): The channel ID.
        - type (str): 'D' for direct.
        - team_id (str): The team ID.
        ... and other channel fields.
    """
    config = get_service_config(context)
    if len(user_ids) != 2:
        raise ValueError("Direct channels must have exactly two user IDs.")
    async with get_mattermost_client(config) as client:
        try:
            response = await client.post("/api/v4/channels/direct", json=user_ids)
            if response.status_code != 201:
                await handle_api_error(response)
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Request to Mattermost API failed: {e}")
            raise ValueError(f"Failed to connect to the Mattermost API: {e}")


@mcp_app.tool()
async def create_group_channel(
    context: Context, user_ids: List[str]
) -> dict[str, Any]:
    """Create a new group message channel for a group of users.

    Corresponds to the POST /api/v4/channels/group endpoint.

    Args:
        context: The MCP request context.
        user_ids: A list of user IDs to include in the group channel.

    Returns:
        A dictionary representing the created channel object.
        - id (str): The channel ID.
        - type (str): 'G' for group.
        - team_id (str): The team ID.
        ... and other channel fields.
    """
    config = get_service_config(context)
    if len(user_ids) < 3:
        raise ValueError("Group channels must have at least three user IDs.")
    async with get_mattermost_client(config) as client:
        try:
            response = await client.post("/api/v4/channels/group", json=user_ids)
            if response.status_code != 201:
                await handle_api_error(response)
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Request to Mattermost API failed: {e}")
            raise ValueError(f"Failed to connect to the Mattermost API: {e}")


@mcp_app.tool()
async def create_channel(
    context: Context,
    team_id: str,
    name: str,
    display_name: str,
    channel_type: str,
    purpose: str = "",
    header: str = "",
) -> dict[str, Any]:
    """Create a new channel.

    Corresponds to the POST /api/v4/channels endpoint.

    Args:
        context: The MCP request context.
        team_id: The team ID of the team to create the channel on.
        name: The unique handle for the channel (will be in the URL).
        display_name: The non-unique UI name for the channel.
        channel_type: 'O' for a public channel, 'P' for a private channel.
        purpose: A short description of the channel's purpose.
        header: Markdown-formatted text for the channel header.

    Returns:
        A dictionary representing the created channel object.
        - id (str): The channel ID.
        - name (str): The channel handle.
        - display_name (str): The channel display name.
        - type (str): The channel type ('O' or 'P').
        ... and other channel fields.
    """
    config = get_service_config(context)
    channel_data = {
        "team_id": team_id,
        "name": name,
        "display_name": display_name,
        "type": channel_type,
        "purpose": purpose,
        "header": header,
    }
    async with get_mattermost_client(config) as client:
        try:
            response = await client.post("/api/v4/channels", json=channel_data)
            if response.status_code != 201:
                await handle_api_error(response)
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Request to Mattermost API failed: {e}")
            raise ValueError(f"Failed to connect to the Mattermost API: {e}")


@mcp_app.tool()
async def search_channels(
    context: Context, team_id: str, term: str
) -> List[dict[str, Any]]:
    """Search public channels on a team.

    Corresponds to the POST /api/v4/teams/{team_id}/channels/search endpoint.

    Args:
        context: The MCP request context.
        team_id: The ID of the team to search in.
        term: The search term to match against channel names or display names.

    Returns:
        A list of dictionaries, each representing a channel that matches the search.
        Each dictionary has the standard channel object structure.
    """
    config = get_service_config(context)
    search_data = {"term": term}
    async with get_mattermost_client(config) as client:
        try:
            response = await client.post(
                f"/api/v4/teams/{team_id}/channels/search", json=search_data
            )
            if response.status_code != 201: # Note: API spec says 201, but it's a search...
                await handle_api_error(response)
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Request to Mattermost API failed: {e}")
            raise ValueError(f"Failed to connect to the Mattermost API: {e}")


@mcp_app.tool()
async def search_posts(
    context: Context,
    team_id: str,
    terms: str,
    is_or_search: bool,
    time_zone_offset: int = 0,
    include_deleted_channels: bool = False,
    page: int = 0,
    per_page: int = 60,
) -> dict[str, Any]:
    """Search for posts in a team.

    Corresponds to the POST /api/v4/teams/{team_id}/posts/search endpoint.

    Args:
        context: The MCP request context.
        team_id: The ID of the team to search in.
        terms: The search terms (e.g., 'from:user in:channel text').
        is_or_search: Set to true for an OR search, false for an AND search.
        time_zone_offset: Offset from UTC for date searches.
        include_deleted_channels: Set to true to include archived channels.
        page: The page to select (Elasticsearch only).
        per_page: The number of posts per page (Elasticsearch only).

    Returns:
        A dictionary representing a list of posts with search matches.
        - order (List[str]): A list of post IDs in order.
        - posts (Dict[str, Post]): A dictionary of post objects.
        - matches (Dict[str, List[str]]): A mapping of post IDs to matched terms.
    """
    config = get_service_config(context)
    search_data = {
        "terms": terms,
        "is_or_search": is_or_search,
        "time_zone_offset": time_zone_offset,
        "include_deleted_channels": include_deleted_channels,
        "page": page,
        "per_page": per_page,
    }
    async with get_mattermost_client(config) as client:
        try:
            response = await client.post(
                f"/api/v4/teams/{team_id}/posts/search", json=search_data
            )
            if response.status_code != 200:
                await handle_api_error(response)
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Request to Mattermost API failed: {e}")
            raise ValueError(f"Failed to connect to the Mattermost API: {e}")


@mcp_app.tool()
async def get_posts_for_channel(
    context: Context,
    channel_id: str,
    page: int = 0,
    per_page: int = 60,
    since: Optional[int] = None,
    before: Optional[str] = None,
    after: Optional[str] = None,
    include_deleted: bool = False,
) -> dict[str, Any]:
    """Get a page of posts in a channel.

    Corresponds to the GET /api/v4/channels/{channel_id}/posts endpoint.

    Args:
        context: The MCP request context.
        channel_id: The ID of the channel to get posts for.
        page: The page to select.
        per_page: The number of posts per page.
        since: Get posts modified after this Unix time in ms.
        before: Get posts that came before this post ID.
        after: Get posts that came after this post ID.
        include_deleted: Whether to include deleted posts (admin only).

    Returns:
        A dictionary representing a list of posts (PostList).
        - order (List[str]): A list of post IDs in order.
        - posts (Dict[str, Post]): A dictionary of post objects.
        - next_post_id (str): The ID of the next post.
        - prev_post_id (str): The ID of the previous post.
        - has_next (bool): Whether there are more items after this page.
    """
    config = get_service_config(context)
    params = {
        "page": page,
        "per_page": per_page,
        "since": since,
        "before": before,
        "after": after,
        "include_deleted": include_deleted,
    }
    # Filter out None values so they aren't sent as query params
    params = {k: v for k, v in params.items() if v is not None}
    async with get_mattermost_client(config) as client:
        try:
            response = await client.get(
                f"/api/v4/channels/{channel_id}/posts", params=params
            )
            if response.status_code != 200:
                await handle_api_error(response)
            return response.json()
        except httpx.RequestError as e:
            logger.error(f"Request to Mattermost API failed: {e}")
            raise ValueError(f"Failed to connect to the Mattermost API: {e}")
