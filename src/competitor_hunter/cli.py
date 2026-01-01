#!/usr/bin/env python
"""Competitor Hunter CLI - 竞品分析命令行工具."""

import asyncio
import json
import sys
from pathlib import Path

from competitor_hunter.core import AgentState, graph, cleanup_resources
from competitor_hunter.core.models import CompetitorProduct


async def analyze_competitor(url: str, output_file: str | None = None) -> CompetitorProduct | None:
    """分析竞品网站。

    Args:
        url: 要分析的网站 URL
        output_file: 可选，输出 JSON 文件路径

    Returns:
        CompetitorProduct 对象，如果分析失败则返回 None
    """
    print(f"🔍 正在分析: {url}\n")

    # 初始化工作流状态
    initial_state: AgentState = {
        "url": url,
        "scraped_content": None,
        "product": None,
        "error": None,
    }

    try:
        # 运行 LangGraph 工作流
        result = await graph.ainvoke(initial_state)

        # 检查错误
        if result.get("error"):
            print(f"❌ 错误: {result['error']}")
            return None

        # 获取产品信息
        product: CompetitorProduct | None = result.get("product")
        if not product:
            print("⚠️  未能提取产品数据")
            return None

        # 显示结果
        print("✅ 分析完成！\n")
        print("=" * 70)
        print(f"📦 产品名称: {product.product_name}")
        print(f"🔗 URL: {product.url}")
        print(f"🕒 更新时间: {product.last_updated}")
        print("=" * 70)

        # 定价信息
        print(f"\n💰 定价方案 ({len(product.pricing_tiers)} 个):")
        if product.pricing_tiers:
            for tier in product.pricing_tiers:
                print(f"   • {tier.name}: {tier.price} {tier.currency} / {tier.billing_cycle}")
        else:
            print("   (未找到定价信息)")

        # 核心功能
        print(f"\n✨ 核心功能 ({len(product.core_features)} 个):")
        if product.core_features:
            for i, feature in enumerate(product.core_features, 1):
                print(f"   {i}. {feature}")
        else:
            print("   (未列出功能)")

        # 摘要
        if product.summary:
            print(f"\n📝 产品摘要:\n{product.summary}")

        # 保存 JSON 到 reports 目录
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)

        if output_file:
            save_path = Path(output_file)
            # 如果指定了相对路径，保存到 reports 目录
            if not save_path.is_absolute():
                save_path = reports_dir / save_path.name
        else:
            safe_name = product.product_name.replace(" ", "_").replace("/", "_")
            save_path = reports_dir / f"product_{safe_name}.json"

        # 使用正确的编码保存
        json_str = product.model_dump_json(indent=2, exclude_none=True)
        data = json.loads(json_str)
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"\n💾 结果已保存到: {save_path}")

        return product

    except Exception as e:
        print(f"❌ 分析失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None


async def _main_async() -> None:
    """异步主函数。"""
    if len(sys.argv) < 2:
        print("使用方法: competitor-hunter <URL> [输出文件]")
        print("\n示例:")
        print("  competitor-hunter https://www.notion.so/pricing")
        print("  competitor-hunter https://example.com output.json")
        print("\n或者批量分析:")
        print("  competitor-hunter https://site1.com https://site2.com")
        sys.exit(1)

    urls = sys.argv[1:]
    output_file = None

    # 如果最后一个参数看起来像文件路径，作为输出文件
    if len(urls) > 1 and urls[-1].endswith(".json"):
        output_file = urls.pop()

    try:
        # 分析所有 URL
        results = []
        for url in urls:
            product = await analyze_competitor(url, output_file)
            if product:
                results.append(product)
            if len(urls) > 1:
                print("\n" + "=" * 70 + "\n")

        # 如果批量分析，可以生成汇总报告
        if len(results) > 1:
            print(f"\n📊 共分析了 {len(results)} 个产品")

    finally:
        # 清理资源
        await cleanup_resources()


def main() -> None:
    """CLI 入口点（同步包装器）。"""
    try:
        asyncio.run(_main_async())
    except KeyboardInterrupt:
        print("\n⚠️  用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 致命错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

