# Competitor Hunter Dockerfile
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# 安装 Playwright 浏览器
RUN pip install playwright && \
    playwright install chromium && \
    playwright install-deps chromium

# 复制依赖文件
COPY pyproject.toml ./

# 安装 Python 依赖
RUN pip install --no-cache-dir -e ".[dev]"

# 复制源代码
COPY src/ ./src/
COPY config/ ./config/

# 创建必要的目录
RUN mkdir -p data logs reports

# 设置环境变量
ENV PYTHONPATH=/app/src
ENV HEADLESS_MODE=true

# 暴露端口（如果需要）
# EXPOSE 8000

# 运行 MCP 服务器
CMD ["python", "-m", "src.competitor_hunter.interface.mcp_server.server"]

