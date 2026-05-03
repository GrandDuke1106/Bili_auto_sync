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
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-flash"
    },
    "youtube": {
        "target_urls": [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        ],
        "channels": [
            "https://www.youtube.com/@SomeChannel"
        ],
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "download_archive": "data/archive.txt",
        "max_downloads_per_run": 3  
    },
    "bilibili": {
        "enable_upload": False, 
        "delete_after_upload": True, 
        "tid": 122,          
        "tags": ["搬运", "熟肉", "YouTube"]
        "bilibili": {
        "enable_upload": False,
        "delete_after_upload": True,
        "tid": 122,
        "tags": ["翻译", "AI翻译", "YouTube"],
        # 新增：YouTube频道名到B站合集名的映射表
        "collections": {
            "SomeChannel": "默认搬运合集",
            "MKBHD": "MKBHD官方中字"
        }
    },
    "subtitle": {
        "fonts_dir": "configs/fonts",
        "zh_font_name": "Noto Sans SC", 
        "en_font_name": "Fira Code"
    }
}

def init_configs():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(DEFAULT_CONFIG, f, allow_unicode=True, sort_keys=False)
        print(f"[*] 生成默认配置: {CONFIG_FILE}，请填入 API Key")
    if not COOKIES_FILE.exists():
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
        print(f"[*] 生成空的 cookies 文件: {COOKIES_FILE}")

def load_config():
    init_configs()
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
