#!/usr/bin/env bash
# ==========================================
# TalkToYou - Linux / 服务器一键启动脚本
# ==========================================

set -e

# 获取脚本所在根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 默认绑定 0.0.0.0 与 8086 端口
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-8086}"

echo "===================================================="
echo "       TalkToYou - AI 语音第二人代发系统 (Linux)"
echo "===================================================="
echo "当前绑定: http://${HOST}:${PORT}"
echo "----------------------------------------------------"

# 优先使用项目目录下的虚拟环境 Python
if [ -f "$SCRIPT_DIR/venv/bin/python3" ]; then
    PY_BIN="$SCRIPT_DIR/venv/bin/python3"
elif [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
    PY_BIN="$SCRIPT_DIR/venv/bin/python"
elif command -v python3 &>/dev/null; then
    PY_BIN="python3"
elif command -v python &>/dev/null; then
    PY_BIN="python"
else
    echo "❌ 错误: 未检测到 Python 环境，请先安装 Python 3.10+ 并配置 PATH"
    exit 1
fi

# 检查 FFmpeg
if ! command -v ffmpeg &>/dev/null; then
    echo "⚠️ 提示: 未检测到系统 ffmpeg，QQ Silk 原生语音转换可能受限"
    echo "   Ubuntu / Debian 用户建议运行: sudo apt update && sudo apt install -y ffmpeg"
    echo "   CentOS / RHEL 用户建议运行: sudo yum install -y ffmpeg"
fi

# 启动 Web 服务
exec "$PY_BIN" server.py
