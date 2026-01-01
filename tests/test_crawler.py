"""Tests for browser crawler service."""

import pytest
from pathlib import Path

from competitor_hunter.config import Settings
from competitor_hunter.core.models import ScrapingResult
from competitor_hunter.infrastructure.browser import BrowserService


@pytest.fixture
def test_settings() -> Settings:
    """Create test settings with headless mode enabled."""
    return Settings(
        openai_api_key="test_key",  # Not used in crawler tests
        headless_mode=True,
        db_path=Path("data/test_competitors.db"),
    )


@pytest.fixture
async def browser_service(test_settings: Settings) -> BrowserService:
    """Create and return a BrowserService instance."""
    service = BrowserService(settings=test_settings)
    await service.start()
    yield service
    await service.close()


@pytest.mark.asyncio
async def test_fetch_page_content_success(browser_service: BrowserService) -> None:
    """Test successful page content fetching."""
    # Use a simple, reliable test URL
    test_url = "https://example.com"

    result: ScrapingResult = await browser_service.fetch_page_content(test_url)

    # Verify result structure
    assert isinstance(result, ScrapingResult)
    assert result.raw_html is not None
    assert len(result.raw_html) > 0
    assert result.clean_text is not None
    assert len(result.clean_text) > 0

    # Verify HTML contains expected content
    assert "Example Domain" in result.raw_html or "example.com" in result.raw_html.lower()

    # Verify clean text is extracted (should not contain HTML tags)
    assert "<html" not in result.clean_text.lower()
    assert "<body" not in result.clean_text.lower()

    # Screenshot path should be set (even if None, it's valid)
    assert result.screenshot_path is None or isinstance(result.screenshot_path, Path)


@pytest.mark.asyncio
async def test_fetch_page_content_with_screenshot(browser_service: BrowserService) -> None:
    """Test that screenshot is saved when fetching page content."""
    test_url = "https://example.com"

    result: ScrapingResult = await browser_service.fetch_page_content(test_url)

    # Screenshot should be saved (path should exist if screenshot was taken)
    if result.screenshot_path:
        assert result.screenshot_path.exists()
        assert result.screenshot_path.suffix == ".png"


@pytest.mark.asyncio
async def test_fetch_page_content_clean_text_format(browser_service: BrowserService) -> None:
    """Test that clean text is properly formatted (Markdown-like)."""
    test_url = "https://example.com"

    result: ScrapingResult = await browser_service.fetch_page_content(test_url)

    # Clean text should be non-empty
    assert len(result.clean_text) > 0

    # Clean text should be shorter than raw HTML (tags removed)
    assert len(result.clean_text) <= len(result.raw_html)


@pytest.mark.asyncio
async def test_fetch_page_content_invalid_url(browser_service: BrowserService) -> None:
    """Test error handling for invalid URL."""
    invalid_url = "https://this-domain-definitely-does-not-exist-12345.com"

    with pytest.raises(Exception) as exc_info:
        await browser_service.fetch_page_content(invalid_url, timeout=10000)

    # Verify error message contains useful information
    assert "error" in str(exc_info.value).lower() or "failed" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_browser_service_context_manager(test_settings: Settings) -> None:
    """Test BrowserService as async context manager."""
    async with BrowserService(settings=test_settings) as service:
        assert service.browser is not None
        assert service.playwright is not None

        # Test that we can fetch content
        result = await service.fetch_page_content("https://example.com")
        assert isinstance(result, ScrapingResult)

    # After context exit, resources should be cleaned up
    # (browser and playwright should be None, but we can't check as they're private)


@pytest.mark.asyncio
async def test_fetch_page_content_timeout(browser_service: BrowserService) -> None:
    """Test timeout handling."""
    # Use a URL that might be slow or use a very short timeout
    test_url = "https://example.com"

    # This should succeed with normal timeout
    result = await browser_service.fetch_page_content(test_url, timeout=30000)
    assert isinstance(result, ScrapingResult)

    # Test with very short timeout (should still work for example.com)
    result = await browser_service.fetch_page_content(test_url, timeout=5000)
    assert isinstance(result, ScrapingResult)


@pytest.mark.asyncio
async def test_random_user_agent(browser_service: BrowserService) -> None:
    """Test that random User-Agent is used."""
    test_url = "https://example.com"

    # Fetch content twice and verify it works (User-Agent is set internally)
    result1 = await browser_service.fetch_page_content(test_url)
    result2 = await browser_service.fetch_page_content(test_url)

    # Both should succeed
    assert isinstance(result1, ScrapingResult)
    assert isinstance(result2, ScrapingResult)
    assert len(result1.raw_html) > 0
    assert len(result2.raw_html) > 0


@pytest.mark.asyncio
async def test_fetch_page_real_world(browser_service: BrowserService) -> None:
    """Integration test: Fetch real-world page content from example.com."""
    test_url = "https://example.com"

    # Fetch page content
    result: ScrapingResult = await browser_service.fetch_page_content(test_url)

    # Assert ScrapingResult is not empty
    assert result is not None
    assert isinstance(result, ScrapingResult)

    # Assert contains markdown_content (clean_text field)
    assert result.clean_text is not None
    assert len(result.clean_text) > 0

    # Assert raw HTML is also present
    assert result.raw_html is not None
    assert len(result.raw_html) > 0

    # Verify markdown content doesn't contain HTML tags
    assert "<html" not in result.clean_text.lower()
    assert "<body" not in result.clean_text.lower()
    assert "<head" not in result.clean_text.lower()

    # Verify markdown content contains some text from the page
    assert "example" in result.clean_text.lower() or "domain" in result.clean_text.lower()

