# core/downloader.py
import subprocess
from pathlib import Path
from utils.config_manager import load_config

BASE_DIR = Path(__file__).resolve().parent.parent
TEMP_DIR = BASE_DIR / "data" / "temp_workspace"
ARCHIVE_FILE = BASE_DIR / "data" / "archive.txt"

def download_video():
    """
    下载配置文件中指定的视频或频道的最新视频，并提取英文字幕。
    """
    config = load_config()
    target_url = config['youtube']['target_urls'][0]
    
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_FILE.parent.mkdir(parents=True, exist_ok=True)

    # 每次运行前清空工作区，确保只处理当前任务
    for file in TEMP_DIR.glob("*"):
        if file.name != ".gitkeep":
            file.unlink()

    # yt-dlp 命令
    command = [
        "yt-dlp",
        "--download-archive", str(ARCHIVE_FILE),
        "--max-downloads", "1", # 如果是频道，每次也只下载一个最新的
        "--write-sub",
        "--write-auto-sub",
        "--sub-lang", "en",
        "--sub-format", "srt",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "-o", f"{TEMP_DIR}/%(title)s.%(ext)s",
        target_url
    ]

    print(f"[*] 正在调用 yt-dlp 获取: {target_url}")
    result = subprocess.run(command, text=True)
    
    if result.returncode != 0:
        print("[!] yt-dlp 执行可能遇到错误或被中断。")

    video_file = None
    sub_file = None
    
    for file in TEMP_DIR.glob("*"):
        if file.suffix == ".mp4":
            video_file = str(file)
        elif file.suffix in [".srt", ".vtt", ".en.srt", ".en.vtt"]:
            sub_file = str(file)

    if not video_file:
        print("[*] 没有发现新视频 (可能已经下载过，记录在 archive.txt 中)。")
        return None, None

    if video_file and sub_file:
        print(f"[*] 下载成功！找到视频和字幕。")
        return video_file, sub_file
    else:
        print(f"[!] 下载了视频，但没有找到英文字幕！视频: {video_file}")
        return video_file, None
