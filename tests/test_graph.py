"""Tests for LangGraph workflow."""

import sys
from unittest.mock import AsyncMock, patch

import pytest

from competitor_hunter.core import AgentState
from competitor_hunter.core.models import CompetitorProduct, PricingTier

# Get the actual module object (not the graph instance) for patching
graph_module = sys.modules["competitor_hunter.core.graph"]
from competitor_hunter.core.graph import graph


@pytest.fixture
def mock_scraping_result():
    """Create a mock ScrapingResult for testing."""
    from competitor_hunter.core.models import ScrapingResult

    return ScrapingResult(
        raw_html="<html><body><h1>Test Product</h1><p>Test content</p></body></html>",
        clean_text="# Test Product\n\nTest content",
        screenshot_path=None,
    )


@pytest.fixture
def mock_competitor_product():
    """Create a mock CompetitorProduct for testing."""
    return CompetitorProduct(
        product_name="Test Product",
        url="https://example.com",
        pricing_tiers=[
            PricingTier(
                name="Free",
                price="0",
                currency="USD",
                billing_cycle="monthly",
            )
        ],
        core_features=["Feature 1", "Feature 2"],
        summary="# Test Product\n\nTest summary",
    )


@pytest.mark.asyncio
async def test_workflow_structure() -> None:
    """Test that the LangGraph workflow compiles successfully and processes state correctly."""
    # Verify graph is compiled
    assert graph is not None
    assert hasattr(graph, "ainvoke")

    # Create initial state
    initial_state: AgentState = {
        "url": "https://example.com",
        "scraped_content": None,
        "product": None,
        "error": None,
    }

    # Mock BrowserService.fetch_page_content
    from competitor_hunter.core.models import ScrapingResult

    mock_scraping_result = ScrapingResult(
        raw_html="<html><body>Test</body></html>",
        clean_text="# Test Product\n\nTest content",
        screenshot_path=None,
    )

    # Mock CompetitorExtractor.extract_from_markdown
    mock_product = CompetitorProduct(
        product_name="Test Product",
        url="https://example.com",
        pricing_tiers=[],
        core_features=[],
        summary="Test summary",
    )

    with patch.object(
        graph_module, "_get_browser_service"
    ) as mock_browser_service, patch.object(
        graph_module, "_get_extractor"
    ) as mock_extractor:
        # Setup mocks
        mock_browser = AsyncMock()
        mock_browser.start = AsyncMock()
        mock_browser.fetch_page_content = AsyncMock(return_value=mock_scraping_result)
        mock_browser_service.return_value = mock_browser

        mock_ext = AsyncMock()
        mock_ext.extract_from_markdown = AsyncMock(return_value=mock_product)
        mock_extractor.return_value = mock_ext

        # Invoke the graph
        result: AgentState = await graph.ainvoke(initial_state)

        # Verify output state structure
        assert isinstance(result, dict)
        assert "url" in result
        assert "scraped_content" in result
        assert "product" in result
        assert "error" in result

        # Verify URL is preserved
        assert result["url"] == "https://example.com"

        # Verify scraped_content is set (from mock)
        assert result["scraped_content"] is not None
        assert result["scraped_content"] == "# Test Product\n\nTest content"

        # Verify product is extracted
        assert result["product"] is not None
        assert isinstance(result["product"], CompetitorProduct)
        assert result["product"].product_name == "Test Product"

        # Verify no error occurred
        assert result["error"] is None

        # Verify mocks were called
        mock_browser.start.assert_called_once()
        mock_browser.fetch_page_content.assert_called_once_with("https://example.com")
        mock_ext.extract_from_markdown.assert_called_once()


@pytest.mark.asyncio
async def test_workflow_error_handling() -> None:
    """Test that workflow handles errors correctly."""
    initial_state: AgentState = {
        "url": "https://invalid-url-that-does-not-exist.com",
        "scraped_content": None,
        "product": None,
        "error": None,
    }

    with patch.object(graph_module, "_get_browser_service") as mock_browser_service:
        # Setup mock to raise an error
        mock_browser = AsyncMock()
        mock_browser.start = AsyncMock()
        mock_browser.fetch_page_content = AsyncMock(
            side_effect=Exception("Network error")
        )
        mock_browser_service.return_value = mock_browser

        # Invoke the graph
        result: AgentState = await graph.ainvoke(initial_state)

        # Verify error is set in state
        assert result["error"] is not None
        assert "Network error" in result["error"] or "Failed to scrape" in result["error"]

        # Verify scraped_content is None when error occurs
        assert result["scraped_content"] is None

        # Verify product is None when error occurs
        assert result["product"] is None


@pytest.mark.asyncio
async def test_workflow_conditional_edge() -> None:
    """Test that conditional edge works correctly (error -> end, no error -> extract)."""
    # Test case 1: No error, should proceed to extract
    state_with_content: AgentState = {
        "url": "https://example.com",
        "scraped_content": "# Test\n\nContent",
        "product": None,
        "error": None,
    }

    # Mock extractor
    mock_product = CompetitorProduct(
        product_name="Test",
        url="https://example.com",
        pricing_tiers=[],
        core_features=[],
        summary="Test",
    )

    with patch.object(graph_module, "_get_extractor") as mock_extractor:
        mock_ext = AsyncMock()
        mock_ext.extract_from_markdown = AsyncMock(return_value=mock_product)
        mock_extractor.return_value = mock_ext

        # This should complete successfully (extract node should run)
        result = await graph.ainvoke(state_with_content)

        # Verify extract was called
        mock_ext.extract_from_markdown.assert_called_once()
        assert result["product"] is not None

    # Test case 2: With error from scrape, should end early
    # Note: The workflow always starts with scrape node, so we need to simulate
    # an error during scraping to test the conditional edge
    state_for_error_test: AgentState = {
        "url": "https://example.com",
        "scraped_content": None,
        "product": None,
        "error": None,
    }

    with patch.object(graph_module, "_get_browser_service") as mock_browser_service:
        # Setup mock to raise an error during scraping
        mock_browser = AsyncMock()
        mock_browser.start = AsyncMock()
        mock_browser.fetch_page_content = AsyncMock(
            side_effect=Exception("Scraping failed")
        )
        mock_browser_service.return_value = mock_browser

        # Invoke the graph - should stop after scrape node due to error
        result = await graph.ainvoke(state_for_error_test)

        # Verify error is set and workflow ended early (no extract called)
        assert result["error"] is not None
        assert "Scraping failed" in result["error"] or "Failed to scrape" in result["error"]
        assert result["product"] is None
        assert result["scraped_content"] is None

