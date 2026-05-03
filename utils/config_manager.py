import os
import json
import yaml
from pathlib import Path

# 定义基础路径
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "configs"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
COOKIES_FILE = CONFIG_DIR / "cookies.json"

# 默认配置模板
DEFAULT_CONFIG = {
    "deepseek": {
        "api_key": "YOUR_DEEPSEEK_API_KEY_HERE",
        "base_url": "https://api.deepseek.com"
    },
    "youtube": {
        "channels": [
            "https://www.youtube.com/@example_channel"
        ]
    },
    "bilibili": {
        "tid": 122,  # 默认分区：野生技术协会
        "tags": ["搬运", "AI翻译", "YouTube"]
    },
    "subtitle": {
        # 对应你项目里的字体路径
        "font_path": "configs/fonts/Noto_Sans_SC/NotoSansSC-VariableFont_wght.ttf",
        "font_name": "Noto Sans SC"
    }
}

def init_configs():
    """初始化配置文件，如果不存在则创建模板"""
    # 确保 configs 目录存在
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # 检查并生成 config.yaml
    if not CONFIG_FILE.exists():
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(DEFAULT_CONFIG, f, allow_unicode=True, sort_keys=False)
        print(f"[*] 已生成默认配置文件: {CONFIG_FILE}，请填入你的 API Key。")

    # 检查并生成 cookies.json 模板
    if not COOKIES_FILE.exists():
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
        print(f"[*] 已生成空的 B站 cookies 文件: {COOKIES_FILE}，请使用 biliup 登录填充。")

def load_config():
    """加载配置"""
    init_configs()
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

if __name__ == "__main__":
    # 直接运行此文件可以测试初始化功能
    config = load_config()
    print("配置加载成功！")
