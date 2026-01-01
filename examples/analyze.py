"""Simple CLI script to analyze a competitor URL."""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from competitor_hunter.core import AgentState, graph


async def main() -> None:
    """Analyze a competitor URL from command line.

    Usage:
        python examples/analyze.py <URL>
    """
    if len(sys.argv) < 2:
        print("Usage: python examples/analyze.py <URL>")
        print("\nExample:")
        print("  python examples/analyze.py https://example.com/pricing")
        sys.exit(1)

    url = sys.argv[1]

    # Initialize state
    initial_state: AgentState = {
        "url": url,
        "scraped_content": None,
        "product": None,
        "error": None,
    }

    # Run workflow
    print(f"🔍 Analyzing competitor at: {url}\n")
    result = await graph.ainvoke(initial_state)

    # Check for errors
    if result.get("error"):
        print(f"❌ Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    # Display results
    product = result.get("product")
    if product:
        print("✅ Analysis Complete!\n")
        print("=" * 60)
        print(f"Product Name: {product.product_name}")
        print(f"URL: {product.url}")
        print(f"Last Updated: {product.last_updated}")
        print("=" * 60)

        print(f"\n💰 Pricing Tiers ({len(product.pricing_tiers)}):")
        if product.pricing_tiers:
            for tier in product.pricing_tiers:
                print(f"  • {tier.name}: {tier.price} {tier.currency} / {tier.billing_cycle}")
        else:
            print("  (No pricing information found)")

        print(f"\n✨ Core Features ({len(product.core_features)}):")
        if product.core_features:
            for feature in product.core_features:
                print(f"  • {feature}")
        else:
            print("  (No features listed)")

        if product.summary:
            print(f"\n📝 Summary:\n{product.summary}")

        # Optionally save to JSON
        if len(sys.argv) > 2 and sys.argv[2] == "--json":
            output_file = f"product_{product.product_name.replace(' ', '_')}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(product.model_dump_json(indent=2))
            print(f"\n💾 Results saved to: {output_file}")
    else:
        print("⚠️  No product data extracted")


if __name__ == "__main__":
    asyncio.run(main())



