#!/bin/bash
# CantonFair Pro — 启动脚本（含云存储预热）

set -e

cd "$(dirname "$0")"

echo "🏭 CantonFair Pro — 智能外贸撮合系统"
echo "=================================="
echo ""

# ---------- 读取 .env ----------
ENV_FILE=".env"
if [ -f "$ENV_FILE" ]; then
    echo "📋 加载环境变量: $ENV_FILE"
    set -a
    source "$ENV_FILE"
    set +a
fi

# ---------- 检查 Python ----------
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装"
    exit 1
fi

# ---------- 检查依赖 ----------
echo "检查依赖..."
python3 -c "import streamlit" 2>/dev/null || { echo "❌ streamlit 未安装，请运行: pip3 install -r requirements.txt"; exit 1; }
python3 -c "import pandas" 2>/dev/null || { echo "❌ pandas 未安装"; exit 1; }
python3 -c "import plotly" 2>/dev/null || { echo "❌ plotly 未安装"; exit 1; }
echo "✅ 依赖检查通过"
echo ""

# ---------- 数据准备（云存储或本地）----------
echo "📦 准备数据文件..."
if [ -n "$R2_ACCOUNT_ID" ] && [ -n "$R2_ACCESS_KEY_ID" ]; then
    echo "   模式: Cloudflare R2 云存储"
    python3 cloud_storage.py --force
else
    echo "   模式: 本地文件"
    DATA_FILE_LOCAL="${LOCAL_DATA_FILE:-../广交会数据综合整理_标准格式.xlsx}"
    if [ ! -f "$DATA_FILE_LOCAL" ]; then
        echo "❌ 数据文件不存在: $DATA_FILE_LOCAL"
        exit 1
    fi
    echo "   ✅ 数据文件: $DATA_FILE_LOCAL"
    FILESIZE=$(stat -f%z "$DATA_FILE_LOCAL" 2>/dev/null || stat -c%s "$DATA_FILE_LOCAL" 2>/dev/null)
    echo "   文件大小: $(echo "scale=1; $FILESIZE/1024/1024" | bc 2>/dev/null || echo "$FILESIZE bytes")"
fi
echo ""

# ---------- 启动应用 ----------
PORT="${PORT:-8502}"
echo "🚀 启动应用..."
echo "   访问地址: http://localhost:$PORT"
echo "   按 Ctrl+C 停止服务"
echo ""

exec python3 -m streamlit run ui/app.py \
    --server.headless true \
    --server.port "$PORT" \
    --server.address 0.0.0.0 \
    --browser.gatherUsageStats false \
    --theme.base dark
