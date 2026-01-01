"""Main entry point for Competitor-Hunter application."""

import asyncio
import sys
from pathlib import Path

from loguru import logger

from competitor_hunter.config import get_settings


def setup_logging() -> None:
    """Configure loguru logger."""
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level="INFO",
    )


async def main() -> None:
    """Main application entry point."""
    setup_logging()
    logger.info("Starting Competitor-Hunter application")

    try:
        settings = get_settings()
        logger.info(f"Configuration loaded: DB_PATH={settings.db_path}, HEADLESS_MODE={settings.headless_mode}")

        # TODO: Initialize application components
        # - Initialize database
        # - Initialize browser
        # - Initialize MCP server
        # - Start LangGraph workflow

        logger.info("Application initialized successfully")

    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

