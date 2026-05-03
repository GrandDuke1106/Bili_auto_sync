# core/downloader.py
import subprocess
import shutil
from pathlib import Path
from utils.config_manager import load_config

BASE_DIR = Path(__file__).resolve().parent.parent
TEMP_DIR = BASE_DIR / "data" / "temp_workspace"
ARCHIVE_FILE = BASE_DIR / "data" / "archive.txt"

def download_video():
    config = load_config()
    yt_config = config.get('youtube', {})
    
    urls = yt_config.get('target_urls', [])
    channels = yt_config.get('channels', [])
    all_targets = [url for url in (urls + channels) if url.strip()]
    
    if not all_targets:
        print("[*] 没有配置任何 YouTube 视频或频道 URL。")
        return []

    yt_format = yt_config.get('format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best')
    max_dl = str(yt_config.get('max_downloads_per_run', 3))
    
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_FILE.parent.mkdir(parents=True, exist_ok=True)

    # 智能清理
    for item in TEMP_DIR.glob("*"):
        if item.name != ".gitkeep":
            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)

    command = [
        "yt-dlp",
        "--download-archive", str(ARCHIVE_FILE),
        "--ignore-errors",
        "--max-downloads", max_dl,  # 限制最大下载数
        "--write-sub",
        "--write-auto-sub",
        "--sub-lang", "en",
        "--sub-format", "srt",
        "--write-description",      # 【新增】下载 YouTube 原版简介
        "-f", yt_format,
        "-o", f"{TEMP_DIR}/%(title)s.%(ext)s"
    ]
    command.extend(all_targets)

    print(f"[*] 正在调用 yt-dlp，单次最多下载 {max_dl} 个新视频...")
    subprocess.run(command, text=True)

    downloaded_files = []
    for video_file in TEMP_DIR.glob("*.mp4"):
        if "_zh_sub" in video_file.name: 
            continue
            
        sub_file, desc_file = None, None
        
        # 寻找字幕
        for ext in [".srt", ".vtt"]:
            possible_subs = list(TEMP_DIR.glob(f"{video_file.stem}*{ext}"))
            if possible_subs:
                sub_file = str(possible_subs[0])
                break
        
        # 寻找简介文件
        possible_desc = list(TEMP_DIR.glob(f"{video_file.stem}*.description"))
        if possible_desc:
            desc_file = str(possible_desc[0])
                
        downloaded_files.append((str(video_file), sub_file, desc_file))

    return downloaded_files
