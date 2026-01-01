"""LLM-based extractor for competitor product information."""

import tiktoken
from typing import Optional

from loguru import logger
from pydantic import ValidationError
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from competitor_hunter.core.models import CompetitorProduct


# Approximate tokens per character (conservative estimate: ~4 chars per token)
CHARS_PER_TOKEN = 4
MAX_TOKENS = 15000
TRUNCATE_CHARS = MAX_TOKENS * CHARS_PER_TOKEN  # ~60k characters


class CompetitorExtractor:
    """Extract competitor product information from Markdown content using LLM."""

    def __init__(
        self,
        model_name: str = "gpt-4o",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        """Initialize CompetitorExtractor with LLM configuration.

        Args:
            model_name: OpenAI model name to use (default: "gpt-4o").
            api_key: OpenAI API key. If None, will be read from environment.
            base_url: OpenAI API base URL. If None, uses default OpenAI endpoint.
        """
        self.model_name = model_name
        llm_kwargs = {
            "model": model_name,
            "temperature": 0,  # Use temperature=0 for factual extraction
            "api_key": api_key,
        }
        # Add base_url if provided (for custom endpoints)
        if base_url:
            llm_kwargs["base_url"] = base_url

        self.llm = ChatOpenAI(**llm_kwargs)

        # Bind structured output to CompetitorProduct schema
        self.structured_llm = self.llm.with_structured_output(CompetitorProduct)

        # Initialize tokenizer for token counting
        try:
            self.encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            # Fallback to cl100k_base encoding (used by gpt-4)
            self.encoding = tiktoken.get_encoding("cl100k_base")

        logger.info(f"Initialized CompetitorExtractor with model: {model_name}")

    def _count_tokens(self, text: str) -> int:
        """Count the number of tokens in a text string.

        Args:
            text: Input text to count tokens for.

        Returns:
            Number of tokens in the text.
        """
        return len(self.encoding.encode(text))

    def _truncate_content(self, markdown_content: str) -> str:
        """Truncate markdown content if it exceeds token limit.

        Preserves header and footer sections as they often contain key information.

        Args:
            markdown_content: Original markdown content.

        Returns:
            Truncated markdown content if needed, otherwise original content.
        """
        token_count = self._count_tokens(markdown_content)

        if token_count <= MAX_TOKENS:
            return markdown_content

        logger.warning(
            f"Content exceeds token limit ({token_count} > {MAX_TOKENS}). Truncating..."
        )

        # Calculate character limits (approximate)
        # Keep first 40% and last 40% of content
        total_chars = len(markdown_content)
        keep_chars = int(TRUNCATE_CHARS * 0.4)  # 40% of max chars

        if total_chars <= TRUNCATE_CHARS:
            # Content is within character limit but exceeds token limit
            # Use simple truncation
            truncated = markdown_content[:TRUNCATE_CHARS]
        else:
            # Split content: keep header and footer
            header = markdown_content[:keep_chars]
            footer = markdown_content[-keep_chars:]
            truncated = f"{header}\n\n[... content truncated ...]\n\n{footer}"

        logger.info(
            f"Truncated content from {token_count} tokens to "
            f"approximately {self._count_tokens(truncated)} tokens"
        )

        return truncated

    def _create_system_prompt(self) -> str:
        """Create system prompt for competitor analysis.

        Returns:
            System prompt string with instructions for LLM.
        """
        return """你是一位专业的 SaaS 竞品分析师。你的任务是从给定的网页 Markdown 内容中提取精确的产品信息。

**重要规则：**

1. **产品名称 (product_name)**:
   - 提取产品的准确名称，不要添加额外的描述性文字
   - 如果页面标题包含产品名称，优先使用

2. **定价信息 (pricing_tiers)**:
   - 仔细查找页面中的定价信息（价格表、定价页面等）
   - 如果找不到明确的定价信息，将 `pricing_tiers` 设置为空列表 `[]`，**绝对不要编造价格**
   - 如果找到定价，提取以下信息：
     * `name`: 定价层级名称（如 "Free", "Pro", "Enterprise"）
     * `price`: 价格字符串（如 "0", "29.99", "Custom"）
     * `currency`: 货币代码（如 "USD", "EUR", "CNY"）
     * `billing_cycle`: 计费周期（"monthly", "yearly", "one-time", "custom"）

3. **核心功能 (core_features)**:
   - 提取产品的主要功能特性
   - 每个功能应该是简洁的描述（1-3个词）
   - 优先提取页面中明确列出的功能列表
   - 如果没有明确的功能列表，从产品描述中推断

4. **产品摘要 (summary)**:
   - 必须是 Markdown 格式
   - 包含以下部分：
     * 产品概述（1-2段）
     * 主要用例
     * 竞争优势
     * 简短的 SWOT 分析：
       - Strengths（优势）
       - Weaknesses（劣势）
       - Opportunities（机会）
       - Threats（威胁）
   - 保持客观、准确，基于页面内容

5. **URL (url)**:
   - 必须使用提供的 `source_url` 参数值
   - 不要修改或推断 URL

**输出要求：**
- 所有字段必须符合 Pydantic Schema 定义
- 如果某个字段的信息不可用，使用默认值（空列表、空字符串等）
- 不要编造不存在的信息
- 保持数据的准确性和客观性"""

    async def extract_from_markdown(
        self, markdown_content: str, source_url: str
    ) -> CompetitorProduct:
        """Extract competitor product information from Markdown content.

        Args:
            markdown_content: Markdown-formatted content scraped from the webpage.
            source_url: Source URL of the webpage for reference.

        Returns:
            CompetitorProduct object with extracted information.

        Raises:
            ValueError: If extraction fails due to API errors or validation errors.
            Exception: For other unexpected errors.
        """
        logger.info(f"Starting extraction from URL: {source_url}")

        try:
            # Truncate content if it exceeds token limit
            processed_content = self._truncate_content(markdown_content)

            # Create system prompt
            system_prompt = self._create_system_prompt()

            # Create user message with content and URL
            user_message = f"""请从以下网页内容中提取竞品产品信息。

**来源 URL**: {source_url}

**网页内容 (Markdown)**:
{processed_content}

请按照系统提示中的规则提取信息，确保所有字段都符合要求。"""

            # Invoke LLM with structured output
            # Use SystemMessage and HumanMessage for proper message formatting
            logger.debug(f"Invoking LLM with model: {self.model_name}")
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_message),
            ]
            result: CompetitorProduct = await self.structured_llm.ainvoke(messages)

            # Ensure URL is set correctly
            result.url = source_url

            logger.info(
                f"Successfully extracted product: {result.product_name} "
                f"({len(result.pricing_tiers)} pricing tiers, "
                f"{len(result.core_features)} features)"
            )

            return result

        except ValidationError as e:
            error_msg = f"Pydantic validation error during extraction: {e}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e

        except Exception as e:
            error_msg = f"LLM extraction failed for URL {source_url}: {str(e)}"
            logger.error(error_msg)

            # Re-raise with more context
            if "api" in str(e).lower() or "openai" in str(e).lower():
                raise ValueError(f"OpenAI API error: {str(e)}") from e

            raise Exception(error_msg) from e

