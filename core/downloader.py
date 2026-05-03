# core/downloader.py
import subprocess
from pathlib import Path
from utils.config_manager import load_config

BASE_DIR = Path(__file__).resolve().parent.parent
TEMP_DIR = BASE_DIR / "data" / "temp_workspace"
ARCHIVE_FILE = BASE_DIR / "data" / "archive.txt"

def download_video():
    config = load_config()
    target_url = config['youtube']['target_urls'][0]
    yt_format = config['youtube'].get('format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best')
    
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_FILE.parent.mkdir(parents=True, exist_ok=True)

    for file in TEMP_DIR.glob("*"):
        if file.name != ".gitkeep":
            file.unlink()

    command = [
        "yt-dlp",
        "--download-archive", str(ARCHIVE_FILE),
        "--max-downloads", "1",
        "--write-sub",
        "--write-auto-sub",
        "--sub-lang", "en",
        "--sub-format", "srt",
        "-f", yt_format, # 使用配置的最高画质
        "-o", f"{TEMP_DIR}/%(title)s.%(ext)s",
        target_url
    ]

    print(f"[*] 正在调用 yt-dlp 获取: {target_url} (使用最高画质)")
    result = subprocess.run(command, text=True)
    
    if result.returncode != 0:
        print("[!] yt-dlp 执行可能遇到错误或被中断。")

    video_file, sub_file = None, None
    for file in TEMP_DIR.glob("*"):
        if file.suffix == ".mp4": video_file = str(file)
        elif file.suffix in [".srt", ".vtt", ".en.srt", ".en.vtt"]: sub_file = str(file)

    if not video_file:
        print("[*] 没有发现新视频 (可能已经下载过)。")
        return None, None
    
    if sub_file:
        print(f"[*] 下载成功！视频: {video_file} | 字幕: {sub_file}")
    else:
        print(f"[!] 下载了视频，但未找到英文字幕！")
    return video_file, sub_file
