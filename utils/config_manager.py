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
        # 目标链接：支持具体某个视频的 URL，也支持频道主页的 URL
        "target_urls": [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ" # 替换为你想测试的视频链接
        ]
    },
    "bilibili": {
        "tid": 122,  # 默认分区：野生技术协会
        "tags": ["搬运", "AI翻译", "YouTube"]
    },
    "subtitle": {
        # 根据你传给我的文件结构，设置真实的字体路径
        "zh_font_path": "configs/fonts/Noto_Sans_SC/NotoSansSC-VariableFont_wght.ttf",
        "zh_font_name": "Noto Sans SC",
        "en_font_path": "configs/fonts/Fira_Code_v6.2/ttf/FiraCode-Regular.ttf", # 使用普通的等宽字重
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
        print(f"[*] 已生成空的 B站 cookies 文件: {COOKIES_FILE}。")

def load_config():
    """加载配置"""
    init_configs()
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

if __name__ == "__main__":
    config = load_config()
    print("配置加载成功！")
