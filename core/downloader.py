# core/downloader.py
import subprocess
import shutil
import json
import re
from pathlib import Path
import pysrt
from utils.config_manager import load_config

BASE_DIR = Path(__file__).resolve().parent.parent
TEMP_DIR = BASE_DIR / "data" / "temp_workspace"
ARCHIVE_FILE = BASE_DIR / "data" / "archive.txt"


def clean_temp_dir():
    """清理临时工作目录中所有文件（保留 .gitkeep）"""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    for item in TEMP_DIR.glob("*"):
        if item.name == ".gitkeep":
            continue
        # 跳过管道状态文件，避免误删中间结果
        if item.name.endswith("_pipeline_state.json"):
            continue
        if item.is_file() or item.is_symlink():
            item.unlink()
        elif item.is_dir():
            shutil.rmtree(item)


def run_yt_dlp():
    """执行 yt-dlp 下载命令"""
    config = load_config()
    yt_config = config.get('youtube', {})

    urls = yt_config.get('target_urls') or []
    channels = yt_config.get('channels') or []
    all_targets = [url for url in (urls + channels) if url.strip()]

    if not all_targets:
        print("[*] 没有配置任何 YouTube 视频或频道 URL。")
        return

    yt_format = yt_config.get('format', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best')
    max_dl = str(yt_config.get('max_downloads_per_run', 3))
    yt_proxy = yt_config.get('proxy', '')

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_FILE.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "yt-dlp",
        "--download-archive", str(ARCHIVE_FILE),
        "--write-info-json",
        "--write-thumbnail",
        "--convert-thumbnails", "png",
        "--ignore-errors",
        "--max-downloads", max_dl,
        "--write-sub",
        "--write-auto-sub",
        "--sub-lang", "en",
        "--sub-format", "json3",
        "--write-description",
        "-f", yt_format,
        "-o", f"{TEMP_DIR}/%(title)s.%(ext)s"
    ]
    if yt_proxy:
        command.extend(["--proxy", yt_proxy])
        print(f"[*] yt-dlp 已启用代理: {yt_proxy}")
    command.extend(all_targets)

    print(f"[*] 正在调用 yt-dlp，单次最多下载 {max_dl} 个新视频...")
    subprocess.run(command, text=True)


def scan_downloaded_files():
    """扫描 TEMP_DIR，返回已下载视频的文件元组列表。
    
    返回格式与 download_video() 一致：
    [(video_path, srt_path, desc_path, uploader_id, uploader_name, source_url, cover_path), ...]
    """
    downloaded_files = []
    for video_file in TEMP_DIR.glob("*.mp4"):
        if "_zh_sub" in video_file.name:
            continue

        sub_file, desc_file = None, None
        uploader_id = ""
        uploader_name = ""
        source_url = ""
        cover_path = ""

        # 解析 info.json 获取频道元数据
        info_file = TEMP_DIR / f"{video_file.stem}.info.json"
        if info_file.exists():
            try:
                with open(info_file, 'r', encoding='utf-8') as f:
                    info_data = json.load(f)
                    uploader_id = info_data.get('channel_id', '')
                    uploader_name = info_data.get('channel', info_data.get('uploader', ''))
                    source_url = info_data.get('webpage_url', 'YouTube')
            except Exception as e:
                print(f"[!] 读取频道元数据失败: {e}")

        # 寻找封面图片
        for ext in [".jpg", ".jpeg", ".png"]:
            possible_covers = list(TEMP_DIR.glob(f"{video_file.stem}*{ext}"))
            if possible_covers:
                cover_path = str(possible_covers[0])
                break

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

        downloaded_files.append((
            str(video_file), sub_file, desc_file,
            uploader_id, uploader_name, source_url, cover_path
        ))

    return downloaded_files


def convert_json3_subtitles():
    """
    将 TEMP_DIR 中所有 .json3 字幕转换为 .srt，保留逐词级精确时间轴。
    
    YouTube 的 json3 格式有词级毫秒精度，而 yt-dlp 自带的 srt 转换会把
    时间间隔很远的词错误地压入同一条目。此函数绕过该 bug。
    """
    json3_files = list(TEMP_DIR.glob("*.json3"))
    if not json3_files:
        return

    print(f"[*] 发现 {len(json3_files)} 个 json3 字幕文件，开始转换为 SRT...")

    for json3_path in json3_files:
        try:
            with open(json3_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            events = data.get('events', [])
            if not events:
                print(f"    - {json3_path.name}: 无字幕事件，跳过")
                continue

            subs = pysrt.SubRipFile()
            for ev in events:
                segs = ev.get('segs', [])
                if not segs:
                    continue

                # 拼接 segs 文本
                text = ''.join(s.get('utf8', '') for s in segs).strip()
                if not text:
                    continue

                # 移除 YouTube ASR 噪声标签：\n[Music]\n, \n[Applause]\n 等
                text = re.sub(r'\s*\[Music\]\s*', ' ', text)
                text = re.sub(r'\s*\[Applause\]\s*', ' ', text)
                text = re.sub(r'\s+', ' ', text).strip()
                if not text:
                    continue

                t_start = ev.get('tStartMs', 0)
                t_dur = ev.get('dDurationMs', 0)
                t_end = t_start + t_dur

                sub = pysrt.SubRipItem(
                    index=len(subs) + 1,
                    start=pysrt.SubRipTime(milliseconds=t_start),
                    end=pysrt.SubRipTime(milliseconds=t_end),
                    text=text,
                )
                subs.append(sub)

            # 输出为同名 .srt
            srt_path = json3_path.with_suffix('.srt')
            subs.save(str(srt_path), encoding='utf-8')
            print(f"    - {json3_path.name} → {srt_path.name} ({len(subs)} 条)")

            # 删除原始 json3，保持 TEMP_DIR 整洁
            json3_path.unlink()

        except Exception as e:
            print(f"    [!] 转换 {json3_path.name} 失败: {e}")


def download_video():
    """运行 yt-dlp 下载 → 转换 json3 字幕 → 扫描结果"""
    run_yt_dlp()
    convert_json3_subtitles()
    return scan_downloaded_files()
