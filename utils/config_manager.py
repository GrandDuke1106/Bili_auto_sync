# utils/config_manager.py
import os
import json
import yaml
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "configs"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
COOKIES_FILE = CONFIG_DIR / "cookies.json"

DEFAULT_CONFIG = {
    "deepseek": {
        "api_key": "YOUR_DEEPSEEK_API_KEY_HERE",
        "base_url": "https://api.deepseek.com"
    },
    "youtube": {
        # 这里可以是频道主页链接，也可以是单个视频的链接
        "target_urls": [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ" # 替换为你想测试的视频或频道
        ]
    },
    "subtitle": {
        # 中文字体 (建议：思源黑体)
        "zh_font_path": "configs/fonts/Noto_Sans_SC/NotoSansSC-VariableFont_wght.ttf",
        "zh_font_name": "Noto Sans SC",
        # 英文字体 (免费商用等宽，建议：Fira Code)
        "en_font_path": "configs/fonts/FiraCode-Regular.ttf",
        "en_font_name": "Fira Code"
    }
}

def init_configs():
    """初始化配置文件，如果不存在则创建模板"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_FILE.exists():
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(DEFAULT_CONFIG, f, allow_unicode=True, sort_keys=False)
        print(f"[*] 已生成默认配置文件: {CONFIG_FILE}，请填入你的 API Key。")

    if not COOKIES_FILE.exists():
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
        print(f"[*] 已生成空的 B站 cookies 文件: {COOKIES_FILE}")

def load_config():
    """加载配置"""
    init_configs()
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

if __name__ == "__main__":
    config = load_config()
    print("配置加载成功！")
