"""LangGraph workflow for competitor analysis."""

from typing import Literal, Optional, TypedDict

from loguru import logger
from langgraph.graph import END, START, StateGraph

from competitor_hunter.config import Settings, get_settings
from competitor_hunter.core.models import CompetitorProduct
from competitor_hunter.infrastructure.browser import BrowserService
from competitor_hunter.infrastructure.llm import CompetitorExtractor


class AgentState(TypedDict):
    """State definition for the competitor analysis workflow.

    This TypedDict defines the state that flows through the LangGraph workflow.
    Each node can read from and update this state.

    Attributes:
        url: Input URL of the competitor's product page to analyze.
        scraped_content: Markdown-formatted content scraped from the webpage.
            Set by the scrape node if successful.
        product: Structured CompetitorProduct object extracted by LLM.
            Set by the extract node if successful.
        error: Error message if any step fails. If set, workflow terminates.
    """

    url: str
    scraped_content: Optional[str]
    product: Optional[CompetitorProduct]
    error: Optional[str]


# Initialize services at module level
# These are initialized once when the module is imported
_settings: Settings = get_settings()
_browser_service: Optional[BrowserService] = None
_extractor: Optional[CompetitorExtractor] = None


def _get_browser_service() -> BrowserService:
    """Get or create BrowserService instance.

    Returns:
        BrowserService instance configured with settings.
    """
    global _browser_service
    if _browser_service is None:
        _browser_service = BrowserService(settings=_settings)
    return _browser_service


async def cleanup_resources() -> None:
    """Clean up global resources (browser service, etc.).

    This should be called when the application is shutting down
    to prevent event loop errors.
    """
    global _browser_service
    if _browser_service is not None:
        try:
            await _browser_service.close()
            _browser_service = None
        except Exception:
            pass  # Ignore errors during cleanup


def _get_extractor() -> CompetitorExtractor:
    """Get or create CompetitorExtractor instance.

    Returns:
        CompetitorExtractor instance configured with API key, base URL, and model from settings.
    """
    global _extractor
    if _extractor is None:
        _extractor = CompetitorExtractor(
            model_name=_settings.openai_model_name,
            api_key=_settings.openai_api_key,
            base_url=_settings.openai_base_url,
        )
    return _extractor


async def node_scrape(state: AgentState) -> AgentState:
    """Scrape webpage content using BrowserService.

    This node:
    1. Reads the `url` from state
    2. Calls BrowserService to fetch page content
    3. Extracts the clean_text (Markdown) from ScrapingResult
    4. Updates state with `scraped_content` on success, or `error` on failure

    Args:
        state: Current workflow state containing the URL to scrape.

    Returns:
        Updated state with `scraped_content` (if successful) or `error` (if failed).
    """
    url = state["url"]
    logger.info(f"Scraping node: Starting scrape for URL: {url}")

    try:
        browser_service = _get_browser_service()

        # Ensure browser is started (fetch_page_content will start it if needed)
        await browser_service.start()

        # Fetch page content
        # Note: fetch_page_content internally manages page and context lifecycle
        result = await browser_service.fetch_page_content(url)

        # Extract clean_text (Markdown format) from ScrapingResult
        scraped_content = result.clean_text

        logger.info(
            f"Scraping node: Successfully scraped {len(scraped_content)} characters "
            f"from {url}"
        )

        # Update state with scraped content
        return {
            **state,
            "scraped_content": scraped_content,
            "error": None,  # Clear any previous errors
        }

    except Exception as e:
        error_msg = f"Failed to scrape URL {url}: {str(e)}"
        logger.error(error_msg)

        # Update state with error
        return {
            **state,
            "error": error_msg,
            "scraped_content": None,
        }


async def node_extract(state: AgentState) -> AgentState:
    """Extract structured product information using LLM.

    This node:
    1. Reads `scraped_content` and `url` from state
    2. Calls CompetitorExtractor to extract structured information
    3. Updates state with `product` on success, or `error` on failure

    Only executes if `scraped_content` exists and there's no error.

    Args:
        state: Current workflow state containing scraped content and URL.

    Returns:
        Updated state with `product` (if successful) or `error` (if failed).
    """
    url = state["url"]
    scraped_content = state.get("scraped_content")

    # Safety check: should not be called if content is missing
    if not scraped_content:
        error_msg = "Cannot extract: scraped_content is missing"
        logger.error(error_msg)
        return {
            **state,
            "error": error_msg,
            "product": None,
        }

    logger.info(f"Extraction node: Starting LLM extraction for URL: {url}")

    try:
        extractor = _get_extractor()

        # Extract structured product information from Markdown content
        product = await extractor.extract_from_markdown(
            markdown_content=scraped_content,
            source_url=url,
        )

        logger.info(
            f"Extraction node: Successfully extracted product '{product.product_name}' "
            f"with {len(product.pricing_tiers)} pricing tiers and "
            f"{len(product.core_features)} features"
        )

        # Update state with extracted product
        return {
            **state,
            "product": product,
            "error": None,  # Clear any previous errors
        }

    except Exception as e:
        error_msg = f"Failed to extract product information from {url}: {str(e)}"
        logger.error(error_msg)

        # Update state with error
        return {
            **state,
            "error": error_msg,
            "product": None,
        }


def should_continue(state: AgentState) -> Literal["extract", "end"]:
    """Conditional edge function to determine next step after scraping.

    This function checks if there's an error in the state:
    - If error exists: return "end" to terminate workflow
    - If no error: return "extract" to proceed to extraction node

    Args:
        state: Current workflow state.

    Returns:
        "end" if there's an error, "extract" otherwise.
    """
    if state.get("error"):
        logger.warning(f"Workflow terminating due to error: {state['error']}")
        return "end"
    return "extract"


# Build the LangGraph workflow
# ============================
# Workflow structure:
#   START -> scrape -> (conditional) -> extract -> END
#                      (if error) -> END

# Create StateGraph with AgentState as the state type
workflow = StateGraph(AgentState)

# Add nodes to the graph
# Each node is an async function that takes state and returns updated state
workflow.add_node("scrape", node_scrape)
workflow.add_node("extract", node_extract)

# Define edges (connections between nodes)
# START -> scrape: Begin workflow with URL
workflow.set_entry_point("scrape")

# scrape -> (conditional) -> extract or end
# Use conditional edge to check for errors
workflow.add_conditional_edges(
    "scrape",
    should_continue,  # Function that returns next node name
    {
        "extract": "extract",  # If no error, go to extract node
        "end": END,  # If error, end workflow
    },
)

# extract -> END: Final step, always ends workflow
workflow.add_edge("extract", END)

# Compile the graph to create an executable workflow
# The compiled graph can be invoked with an initial state
graph = workflow.compile()

logger.info("LangGraph workflow compiled successfully")

