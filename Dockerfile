# ==========================================
# TalkToYou - 官方容器构建文件
# ==========================================

FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8086

# 安装系统级依赖：ffmpeg 与 gcc (用于编译 pilk silk 编解码器)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    build-essential \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装 Python 库
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . /app/

# 创建持久化与数据挂载目录
RUN mkdir -p /app/output /app/outputs /app/voices/customs /app/voices/emotions /app/voices/presets

# 暴露服务端口
EXPOSE 8086

# 启动入口
CMD ["python", "server.py"]
