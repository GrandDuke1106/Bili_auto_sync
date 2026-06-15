# Bili_auto_sync - YouTube → Bilibili 自动化搬运管线
#
# 镜像策略：仅包含核心依赖，WhisperX (~3GB) 和其模型 (~4.2GB) 在运行时按需下载
# 最终镜像体积约 400MB

FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.description="YouTube → Bilibili 自动搬运 + AI 翻译 + 硬字幕压制"
LABEL maintainer="Bili_auto_sync"

# ── 系统依赖：ffmpeg（字幕压制 + 音频提取）、fontconfig（字体渲染）──
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Python 依赖（分层缓存：先复制 requirements 再 pip install）──
COPY requirements.txt .

# 安装核心依赖 + yt-dlp/biliup 的命令行入口
RUN pip install --no-cache-dir -r requirements.txt

# ── 预下载 NLTK 分词数据（仅 ~10MB，避免运行时网络问题）──
RUN python -c "import nltk; nltk.download('punkt_tab', quiet=True); nltk.download('punkt', quiet=True)"

# ── 预下载 jieba 词典（确保存在）──
RUN python -c "import jieba; jieba.initialize()"

# ── 复制项目代码与入口脚本 ──
COPY . .
COPY scripts/docker-entrypoint.sh /usr/local/bin/entrypoint
RUN chmod +x /usr/local/bin/entrypoint

# ── 确保运行时目录存在 ──
RUN mkdir -p /app/data/temp_workspace /app/data/completed_videos /app/logs

# ── 运行时按需下载的目录（通过卷挂载持久化）──
# /root/.cache/huggingface  → WhisperX 模型缓存（~4.2GB）
# /root/nltk_data           → NLTK 分词数据
# /app/configs              → 用户配置 + cookies
# /app/data                 → 下载视频 + 成品输出
# /app/logs                 → 运行日志

ENTRYPOINT ["/usr/local/bin/entrypoint"]
