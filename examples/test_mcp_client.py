"""Test script to demonstrate MCP server usage.

This script shows how to interact with the MCP server programmatically.
Note: In production, MCP servers are typically used via Claude Desktop or other MCP clients.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from competitor_hunter.core import AgentState, graph
from competitor_hunter.core.models import CompetitorProduct


async def test_analyze_competitor(url: str) -> None:
    """Test the analyze_competitor workflow directly.

    This demonstrates the core functionality that the MCP server exposes.
    """
    print(f"🔍 Testing competitor analysis for: {url}\n")
    print("=" * 70)

    # Initialize state (same as MCP server does internally)
    initial_state: AgentState = {
        "url": url,
        "scraped_content": None,
        "product": None,
        "error": None,
    }

    try:
        # Run the LangGraph workflow
        print("⏳ Running workflow...")
        result = await graph.ainvoke(initial_state)

        # Check for errors
        if result.get("error"):
            print(f"❌ Error: {result['error']}")
            return

        # Display results
        product: CompetitorProduct | None = result.get("product")
        if product:
            print("\n✅ Analysis Complete!\n")
            print("=" * 70)
            print(f"📦 Product Name: {product.product_name}")
            print(f"🔗 URL: {product.url}")
            print(f"🕒 Last Updated: {product.last_updated}")
            print("=" * 70)

            # Pricing information
            print(f"\n💰 Pricing Tiers ({len(product.pricing_tiers)}):")
            if product.pricing_tiers:
                for tier in product.pricing_tiers:
                    print(f"   • {tier.name}: {tier.price} {tier.currency} / {tier.billing_cycle}")
            else:
                print("   (No pricing information found)")

            # Core features
            print(f"\n✨ Core Features ({len(product.core_features)}):")
            if product.core_features:
                for i, feature in enumerate(product.core_features, 1):
                    print(f"   {i}. {feature}")
            else:
                print("   (No features listed)")

            # Summary
            if product.summary:
                print(f"\n📝 Summary:\n{product.summary}")

            # Save JSON output to reports directory
            from pathlib import Path
            reports_dir = Path("reports")
            reports_dir.mkdir(exist_ok=True)
            safe_name = product.product_name.replace(" ", "_").replace("/", "_")
            output_file = reports_dir / f"product_{safe_name}.json"
            # Use model_dump_json() which handles datetime serialization correctly
            # Then decode and re-encode with ensure_ascii=False to preserve Chinese characters
            import json
            json_str = product.model_dump_json(indent=2, exclude_none=True)
            # Parse and re-serialize with ensure_ascii=False to preserve Unicode
            data = json.loads(json_str)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"\n💾 Full JSON saved to: {output_file}")

        else:
            print("⚠️  No product data extracted")

    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()


async def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python examples/test_mcp_client.py <URL>")
        print("\nExamples:")
        print("  python examples/test_mcp_client.py https://example.com")
        print("  python examples/test_mcp_client.py https://www.notion.so/pricing")
        sys.exit(1)

    url = sys.argv[1]
    
    try:
        await test_analyze_competitor(url)
    finally:
        # Clean up browser service resources to prevent event loop errors
        from competitor_hunter.core.graph import cleanup_resources
        
        try:
            await cleanup_resources()
        except Exception:
            pass  # Ignore cleanup errors during shutdown


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}", file=sys.stderr)
        sys.exit(1)



