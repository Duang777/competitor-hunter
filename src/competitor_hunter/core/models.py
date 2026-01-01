"""Core domain models for competitor analysis."""

from datetime import datetime
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


class PricingTier(BaseModel):
    """Pricing tier model representing a product's pricing plan."""

    model_config = ConfigDict(extra="ignore")

    name: str = Field(
        ...,
        description="Name of the pricing tier (e.g., 'Free', 'Pro', 'Enterprise')",
        examples=["Free", "Pro", "Enterprise"],
    )
    price: str = Field(
        ...,
        description="Price as a string (e.g., '0', '29.99', 'Custom')",
        examples=["0", "29.99", "Custom"],
    )
    currency: str = Field(
        default="USD",
        description="Currency code (ISO 4217 format, e.g., 'USD', 'EUR', 'CNY')",
        examples=["USD", "EUR", "CNY"],
    )
    billing_cycle: Literal["monthly", "yearly", "one-time", "custom"] = Field(
        ...,
        description="Billing cycle for the pricing tier",
        examples=["monthly", "yearly"],
    )


class CompetitorProduct(BaseModel):
    """Main model representing a competitor's product information."""

    model_config = ConfigDict(extra="ignore")

    product_name: str = Field(
        ...,
        description="Name of the competitor product",
        examples=["Notion", "Obsidian", "Logseq"],
    )
    url: str = Field(
        ...,
        description="URL of the product's main page or pricing page",
        examples=["https://www.notion.so/pricing"],
    )
    pricing_tiers: List[PricingTier] = Field(
        default_factory=list,
        description="List of pricing tiers available for the product",
    )
    core_features: List[str] = Field(
        default_factory=list,
        description="List of core features or key selling points of the product",
        examples=[["Real-time collaboration", "Markdown support", "API access"]],
    )
    summary: str = Field(
        default="",
        description="Markdown-formatted summary of the product, including key information, use cases, and competitive advantages",
    )
    last_updated: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp when this product information was last updated",
    )


class ScrapingResult(BaseModel):
    """Model for storing raw scraping data before processing."""

    model_config = ConfigDict(extra="ignore")

    raw_html: str = Field(
        ...,
        description="Raw HTML content scraped from the target URL",
    )
    clean_text: str = Field(
        ...,
        description="Cleaned and extracted text content from the HTML (HTML tags removed, formatted for LLM processing)",
    )
    screenshot_path: Optional[Path] = Field(
        default=None,
        description="Optional path to the screenshot of the scraped page",
    )

