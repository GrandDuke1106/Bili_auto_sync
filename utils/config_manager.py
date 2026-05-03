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
        "model": "deepseek-chat" # 新增：可以指定模型，例如 deepseek-reasoner
    },
    "youtube": {
        "target_urls": [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ" 
        ],
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best" # 新增：最高画质格式
    },
    "bilibili": {
        "tid": 122,  
        "tags": ["搬运", "AI翻译", "YouTube"]
    },
    "subtitle": {
        # 注意：这里的路径必须相对于项目根目录是正确的
        "zh_font_path": "configs/fonts/Noto_Sans_SC/NotoSansSC-VariableFont_wght.ttf",
        # 修改为最兼容的内置名称，带不带空格可能导致 FFmpeg 找不到
        "zh_font_name": "NotoSansSC-Regular", 
        "en_font_path": "configs/fonts/Fira_Code_v6.2/ttf/FiraCode-Regular.ttf",
        "en_font_name": "FiraCode-Regular"
    }
}

def init_configs():
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
    init_configs()
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

if __name__ == "__main__":
    config = load_config()
    print("配置加载成功！")
