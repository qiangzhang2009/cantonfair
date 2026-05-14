FROM python:3.11-slim

LABEL maintainer="CantonFair Pro"
LABEL description="CantonFair Pro — 智能外贸撮合系统"

# ---------- 系统依赖 ----------
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# ---------- Python 依赖 ----------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------- 应用代码 ----------
COPY . .

# ---------- 数据目录 ----------
RUN mkdir -p /app/data /app/models /app/cache
RUN chown -R appuser:appuser /app

# ---------- 环境变量 ----------
ENV ENABLE_STANDALONE_HEALTH=1

# ---------- 非 root 用户运行 ----------
USER appuser

# ---------- 健康检查 ----------
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8503/health || exit 1

# ---------- 启动 ----------
EXPOSE 8502

# Railway 会替换启动命令，这里使用默认
CMD ["python3", "-m", "streamlit", "run", "ui/app.py", \
     "--server.headless=true", \
     "--server.port=8502", \
     "--server.address=0.0.0.0", \
     "--browser.gatherUsageStats=false"]
