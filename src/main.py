"""
The main entry point for the Mattermost MCP server.

This script handles environment loading, logging configuration, and server execution.
"""

import logging
import os
import sys

from dotenv import load_dotenv


def setup_environment() -> bool:
    """
    Loads environment variables and configures application-wide logging.
    It's expected that the correct .env file is loaded by the process runner (e.g., uv).
    """
    load_dotenv()  # Load environment variables from .env file.

    # Configure logging using a basic, straightforward setup.
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.info("Environment and logging configured.")
    return True


def run_server() -> None:
    """
    Sets up the environment and runs the MCP server.
    """
    if not setup_environment():
        logging.critical("Initial environment setup failed. Exiting.")
        sys.exit(1)

    # Import server components after setup to ensure environment is loaded first.
    from .server import mcp_app, server_config

    logger = logging.getLogger(__name__)
    logger.info(f"--- Mattermost MCP Server ---")
    logger.info("Starting server with transport: %s", server_config.MCP_TRANSPORT)
    if server_config.MCP_TRANSPORT != "stdio":
        logger.info(
            "Server will listen on: %s:%s",
            server_config.MCP_HOST,
            server_config.MCP_PORT,
        )

    # Run the application with the transport defined in the configuration.
    mcp_app.run(transport=server_config.MCP_TRANSPORT)


if __name__ == "__main__":
    run_server()
