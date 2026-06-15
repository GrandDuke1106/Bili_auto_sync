#!/bin/bash
# Bili_auto_sync Docker 入口脚本
# 
# 职责:
#   1. 检测 WhisperX 是否在配置中启用但未安装 → 给出友好提示
#   2. 确保运行时目录存在
#   3. 透传参数给 main.py

set -e

echo "=========================================="
echo "  Bili_auto_sync - Docker 容器启动"
echo "=========================================="

# ── 确保运行时目录存在 ──
mkdir -p /app/data/temp_workspace /app/data/completed_videos /app/logs

# ── WhisperX 智能检测 ──
python3 -c "
import yaml, sys, os

config_path = '/app/configs/config.yaml'
if not os.path.exists(config_path):
    sys.exit(0)

try:
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
except Exception:
    sys.exit(0)

if cfg.get('whisperx', {}).get('enabled', False):
    try:
        import whisperx
        print('[*] WhisperX 已安装，词级时间戳转录就绪')
    except ImportError:
        print('', file=sys.stderr)
        print('═' * 50, file=sys.stderr)
        print('  [!] 检测到 whisperx.enabled=true 但 WhisperX 未安装', file=sys.stderr)
        print('  [!] 本次将自动回退使用 yt-dlp 附带字幕', file=sys.stderr)
        print('  [*] 如需词级时间戳转录，请运行:', file=sys.stderr)
        print('      docker compose run --rm bili-sync pip install whisperx', file=sys.stderr)
        print('  [*] 模型文件 (~4.2GB) 将在首次转录时自动下载并缓存到卷', file=sys.stderr)
        print('═' * 50, file=sys.stderr)
        print('', file=sys.stderr)
" 2>/dev/null || true

echo "[*] 启动主程序..."
exec python3 /app/main.py "$@"
