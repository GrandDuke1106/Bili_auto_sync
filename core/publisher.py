# core/publisher.py
import subprocess
from pathlib import Path
from utils.config_manager import load_config

BASE_DIR = Path(__file__).resolve().parent.parent
COOKIES_FILE = BASE_DIR / "configs" / "cookies.json"

def upload_to_bilibili(video_path, b_title, b_desc, b_tags):
    config = load_config()
    bili_config = config.get('bilibili', {})
    
    print(f"\n[*] 准备上传至 Bilibili: {b_title}")
    
    if not COOKIES_FILE.exists() or COOKIES_FILE.stat().st_size < 10:
        print("[!] 警告：未找到有效的 configs/cookies.json。")
        print("[!] 无法上传，请在服务器执行 'biliup login'！")
        return False

    # 合并配置文件基础标签和 AI 生成的标签
    base_tags = bili_config.get('tags', ["搬运"])
    final_tags = ",".join(list(set(base_tags + b_tags))[:10]) # 去重且最多保留10个
    tid = str(bili_config.get('tid', 122))
    
    safe_title = b_title[:80]

    command = [
        "biliup", "upload",
        str(video_path),
        "--title", safe_title,
        "--tid", tid,
        "--tag", final_tags,
        "-c", str(COOKIES_FILE),
        "--desc", b_desc  # 去掉了那句宣发文案，完全使用 AI 生成的简介
    ]
    
    try:
        result = subprocess.run(command, text=True)
        if result.returncode == 0:
            print(f"[*] Bilibili 上传成功！")
            return True
        else:
            print(f"[!] Bilibili 上传失败，退出码: {result.returncode}")
            return False
    except FileNotFoundError:
        print("[!] 找不到 biliup 命令。请确保已运行: pip install biliup")
        return False
