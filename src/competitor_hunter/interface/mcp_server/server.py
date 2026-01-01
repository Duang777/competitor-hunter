"""MCP Server for Competitor-Hunter application."""

import asyncio
import sys
from typing import Any, Optional

from loguru import logger

# Try to import FastMCP first, fallback to standard Server
try:
    from mcp.server.fastmcp import FastMCP

    USE_FASTMCP = True
except ImportError:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent

    USE_FASTMCP = False

from competitor_hunter.core import AgentState, graph
from competitor_hunter.core.models import CompetitorProduct


# Initialize MCP server with clear name
if USE_FASTMCP:
    mcp = FastMCP("Competitor Hunter")
else:
    mcp = Server("competitor-hunter")


async def analyze_competitor(url: str) -> str:
    """Analyze competitor product using LangGraph workflow.

    This tool uses a LangGraph workflow to:
    1. Scrape the webpage content using browser automation
    2. Extract structured product information using LLM
    3. Return a JSON representation of the CompetitorProduct

    Args:
        url: The URL of the competitor's product page or pricing page to analyze.

    Returns:
        JSON string containing structured product information (CompetitorProduct model).

    Raises:
        RuntimeError: If the workflow execution fails or returns an error.
    """
    logger.info(f"Starting analysis for {url}...")

    try:
        # Initialize input state for LangGraph workflow
        initial_state: AgentState = {
            "url": url,
            "scraped_content": None,
            "product": None,
            "error": None,
        }

        # Invoke the LangGraph workflow
        logger.debug(f"Invoking LangGraph workflow for URL: {url}")
        result: AgentState = await graph.ainvoke(initial_state)

        # Check for errors in the workflow result
        if result.get("error"):
            error_msg = f"Workflow error: {result['error']}"
            logger.error(f"Analysis failed for {url}: {error_msg}")
            raise RuntimeError(error_msg)

        # Check if product data was extracted
        product: Optional[CompetitorProduct] = result.get("product")
        if product is None:
            logger.warning(f"No product data found for {url}")
            return '{"status": "no_data", "message": "No data found"}'

        # Serialize CompetitorProduct to JSON
        # Use model_dump_json() first to handle datetime serialization, then re-encode
        # with ensure_ascii=False to preserve Unicode characters (Chinese, etc.)
        import json
        json_str = product.model_dump_json(indent=2, exclude_none=True)
        # Parse and re-serialize with ensure_ascii=False to preserve Unicode
        data = json.loads(json_str)
        json_result = json.dumps(data, indent=2, ensure_ascii=False)

        logger.info(f"Analysis complete for {url}: extracted product '{product.product_name}'")
        return json_result

    except RuntimeError:
        # Re-raise RuntimeError (workflow errors) as-is
        raise

    except Exception as e:
        # Catch any unexpected errors during graph execution
        error_msg = f"Unexpected error during analysis of {url}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise RuntimeError(error_msg) from e


if USE_FASTMCP:
    # Register tool using FastMCP decorator
    @mcp.tool()
    async def analyze_competitor_tool(url: str) -> str:
        """Analyze competitor product using LangGraph workflow.

        This tool uses a complete workflow to scrape webpage content and extract
        structured product information including pricing, features, and SWOT analysis.

        Args:
            url: The URL of the competitor's product page or pricing page to analyze.

        Returns:
            JSON string containing structured CompetitorProduct information with:
            - product_name
            - pricing_tiers (list of pricing plans)
            - core_features (list of key features)
            - summary (Markdown format with SWOT analysis)
            - last_updated timestamp
        """
        try:
            return await analyze_competitor(url)
        except RuntimeError as e:
            # Return error as JSON string for FastMCP
            import json

            return json.dumps(
                {"status": "error", "error": str(e)},
                indent=2,
                ensure_ascii=False,
            )

else:
    # Register tool using standard MCP server
    @mcp.list_tools()
    async def list_tools() -> list[Tool]:
        """List available tools."""
        return [
            Tool(
                name="analyze_competitor",
                description=(
                    "Analyze competitor product using LangGraph workflow. "
                    "Scrapes webpage content and extracts structured product information "
                    "including pricing tiers, core features, and SWOT analysis. "
                    "Returns JSON representation of CompetitorProduct."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The URL of the competitor's product page or pricing page to analyze",
                        }
                    },
                    "required": ["url"],
                },
            )
        ]

    @mcp.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle tool calls."""
        import json

        if name == "analyze_competitor":
            url = arguments.get("url", "")
            if not url:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"status": "error", "error": "URL is required"}),
                    )
                ]

            try:
                result = await analyze_competitor(url)
                return [TextContent(type="text", text=result)]
            except RuntimeError as e:
                # Return error as TextContent
                error_response = json.dumps(
                    {"status": "error", "error": str(e)},
                    indent=2,
                    ensure_ascii=False,
                )
                return [TextContent(type="text", text=error_response)]
        else:
            return [
                TextContent(
                    type="text",
                    text=json.dumps({"status": "error", "error": f"Unknown tool: {name}"}),
                )
            ]


def setup_logging() -> None:
    """Configure loguru logger for MCP server."""
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level="INFO",
    )


def main() -> None:
    """Main entry point for MCP server."""
    setup_logging()
    logger.info("Starting Competitor-Hunter MCP Server")

    if USE_FASTMCP:
        # FastMCP's run() is synchronous and manages its own event loop
        mcp.run()
    else:
        # Run standard MCP server with stdio transport
        from mcp.server.stdio import stdio_server

        async def run_standard_mcp() -> None:
            async with stdio_server() as (read_stream, write_stream):
                await mcp.run(read_stream, write_stream, mcp.create_initialization_options())

        asyncio.run(run_standard_mcp())


if __name__ == "__main__":
    main()

