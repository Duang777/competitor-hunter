"""Browser crawler service using Playwright for web scraping."""

import asyncio
import random
from datetime import datetime
from pathlib import Path
from typing import Optional

import html2text
from loguru import logger
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
)

from competitor_hunter.config import Settings, get_settings
from competitor_hunter.core.models import ScrapingResult


# Common User-Agent strings to avoid detection
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
]


class BrowserService:
    """Service for web scraping using Playwright with anti-detection features."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        """Initialize BrowserService with configuration.

        Args:
            settings: Application settings. If None, will load from environment.
        """
        self.settings: Settings = settings or get_settings()
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self._html_converter = html2text.HTML2Text()
        self._html_converter.ignore_links = False
        self._html_converter.ignore_images = False
        self._html_converter.body_width = 0  # Don't wrap lines

    async def __aenter__(self) -> "BrowserService":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()

    async def start(self) -> None:
        """Start the browser instance."""
        if self.playwright is None:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.settings.headless_mode,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )
            logger.info(f"Browser started (headless={self.settings.headless_mode})")

    async def close(self) -> None:
        """Close the browser instance and cleanup resources."""
        if self.context:
            await self.context.close()
            self.context = None
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
        logger.info("Browser closed")

    def _get_random_user_agent(self) -> str:
        """Get a random User-Agent string.

        Returns:
            Random User-Agent string from the predefined list.
        """
        return random.choice(USER_AGENTS)

    async def _create_context(self) -> BrowserContext:
        """Create a new browser context with random User-Agent.

        Returns:
            Browser context with anti-detection settings.
        """
        if self.browser is None:
            await self.start()

        user_agent = self._get_random_user_agent()
        context = await self.browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York",
        )

        # Add stealth scripts to avoid detection
        await context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            """
        )

        logger.debug(f"Created browser context with User-Agent: {user_agent[:50]}...")
        return context

    async def _auto_scroll(self, page: Page, max_scrolls: int = 10) -> None:
        """Automatically scroll page to bottom to trigger lazy-loaded content.

        Args:
            page: Playwright page object.
            max_scrolls: Maximum number of scroll iterations.
        """
        scroll_pause_time = 1.0  # seconds

        for i in range(max_scrolls):
            # Get current scroll position
            previous_height = await page.evaluate("document.body.scrollHeight")

            # Scroll to bottom
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

            # Wait for content to load
            await asyncio.sleep(scroll_pause_time)

            # Calculate new scroll height
            new_height = await page.evaluate("document.body.scrollHeight")

            # If heights are the same, we've reached the bottom
            if previous_height == new_height:
                logger.debug(f"Reached page bottom after {i + 1} scrolls")
                break

        # Scroll back to top
        await page.evaluate("window.scrollTo(0, 0)")
        await asyncio.sleep(0.5)

    async def _save_error_screenshot(
        self, page: Page, url: str
    ) -> Optional[Path]:
        """Save screenshot when an error occurs.

        Args:
            page: Playwright page object.
            url: URL that caused the error.

        Returns:
            Path to saved screenshot, or None if saving failed.
        """
        try:
            logs_dir = Path("logs")
            logs_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_url = url.replace("https://", "").replace("http://", "").replace("/", "_")[:50]
            screenshot_path = logs_dir / f"error_{safe_url}_{timestamp}.png"

            await page.screenshot(path=str(screenshot_path), full_page=True)
            logger.error(f"Error screenshot saved to: {screenshot_path}")
            return screenshot_path
        except Exception as e:
            logger.error(f"Failed to save error screenshot: {e}")
            return None

    async def fetch_page_content(self, url: str, timeout: int = 30000) -> ScrapingResult:
        """Fetch page content from a URL with anti-detection features.

        Args:
            url: URL to fetch content from.
            timeout: Page load timeout in milliseconds.

        Returns:
            ScrapingResult containing raw HTML, clean text, and optional screenshot.

        Raises:
            Exception: If page fetch fails after all retry attempts.
        """
        page: Optional[Page] = None
        context: Optional[BrowserContext] = None

        try:
            # Create context with random User-Agent
            context = await self._create_context()
            self.context = context

            # Create new page
            page = await context.new_page()

            logger.info(f"Fetching content from: {url}")

            # Navigate to URL with timeout
            await page.goto(url, wait_until="networkidle", timeout=timeout)

            # Auto-scroll to trigger lazy-loaded content
            await self._auto_scroll(page)

            # Wait a bit for any remaining dynamic content
            await asyncio.sleep(2)

            # Get raw HTML
            raw_html = await page.content()

            # Convert HTML to Markdown using html2text
            clean_text = self._html_converter.handle(raw_html)

            # Take screenshot for reference
            logs_dir = Path("logs")
            logs_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_url = url.replace("https://", "").replace("http://", "").replace("/", "_")[:50]
            screenshot_path = logs_dir / f"success_{safe_url}_{timestamp}.png"

            try:
                await page.screenshot(path=str(screenshot_path), full_page=True)
                logger.debug(f"Screenshot saved to: {screenshot_path}")
            except Exception as e:
                logger.warning(f"Failed to save screenshot: {e}")
                screenshot_path = None

            # Close page
            await page.close()

            logger.info(f"Successfully fetched content from: {url} ({len(raw_html)} bytes HTML)")

            return ScrapingResult(
                raw_html=raw_html,
                clean_text=clean_text,
                screenshot_path=screenshot_path,
            )

        except PlaywrightTimeoutError as e:
            error_msg = f"Timeout while fetching {url}: {e}"
            logger.error(error_msg)

            if page:
                screenshot_path = await self._save_error_screenshot(page, url)
            else:
                screenshot_path = None

            raise Exception(error_msg) from e

        except Exception as e:
            error_msg = f"Error fetching content from {url}: {e}"
            logger.error(error_msg)

            if page:
                screenshot_path = await self._save_error_screenshot(page, url)
            else:
                screenshot_path = None

            raise Exception(error_msg) from e

        finally:
            # Cleanup page if it wasn't closed
            if page and not page.is_closed():
                try:
                    await page.close()
                except Exception as e:
                    logger.warning(f"Error closing page: {e}")

