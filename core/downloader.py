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

# ── WhisperX 惰性导入 ──
_whisperx_available = None

def _check_whisperx():
    """检查 WhisperX 是否已安装"""
    global _whisperx_available
    if _whisperx_available is None:
        try:
            import whisperx
            _whisperx_available = True
        except ImportError:
            _whisperx_available = False
    return _whisperx_available


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


def _whisperx_segments_to_srt(segments, srt_path, max_chars_per_sub=55):
    """将 WhisperX 的 segments 输出（含词级时间戳）转换为 SRT 文件。

    核心改进：利用 WhisperX 的**词级毫秒时间戳**，将过长的 segment
    在自然词语边界处精确切开。每个子条目用对应词的时间戳，
    确保字幕时间轴与发音完美对齐。

    WhisperX 词级数据结构：
      {
        "start": 0.0, "end": 5.2,
        "text": "hello world this is a test",
        "words": [
          {"word": "hello", "start": 0.00, "end": 0.52, "score": 0.9},
          {"word": "world", "start": 0.58, "end": 1.05, "score": 0.95},
          ...
        ]
      }
    """
    subs = pysrt.SubRipFile()
    for seg in segments:
        text = seg.get('text', '').strip()
        if not text:
            continue
        text = re.sub(r'\s+', ' ', text).strip()
        if not text:
            continue

        words = seg.get('words', [])
        if not words:
            # 无词级数据：回退到段级时间戳
            start_ms = int(seg['start'] * 1000)
            end_ms = int(seg['end'] * 1000)
            if end_ms <= start_ms:
                end_ms = start_ms + 500
            sub = pysrt.SubRipItem(
                index=len(subs) + 1,
                start=pysrt.SubRipTime(milliseconds=start_ms),
                end=pysrt.SubRipTime(milliseconds=end_ms),
                text=text,
            )
            subs.append(sub)
            continue

        # ── 利用词级时间戳：将长 segment 在词边界切开 ──
        if len(text) <= max_chars_per_sub:
            # 短文本：直接作为一个条目，使用首尾词精确时间
            start_ms = int(words[0].get('start', seg['start']) * 1000)
            end_ms = int(words[-1].get('end', seg['end']) * 1000)
            if end_ms <= start_ms:
                end_ms = start_ms + 500
            sub = pysrt.SubRipItem(
                index=len(subs) + 1,
                start=pysrt.SubRipTime(milliseconds=start_ms),
                end=pysrt.SubRipTime(milliseconds=end_ms),
                text=text,
            )
            subs.append(sub)
        else:
            # 长文本：按 max_chars_per_sub 分组，在词边界处切开
            chunks = _split_words_into_chunks(words, max_chars_per_sub)
            for chunk_words in chunks:
                if not chunk_words:
                    continue
                chunk_text = ' '.join(w.get('word', '').strip() for w in chunk_words)
                chunk_text = re.sub(r'\s+', ' ', chunk_text).strip()
                if not chunk_text:
                    continue

                # 精确时间：第一个词的 start → 最后一个词的 end
                chunk_start = int(chunk_words[0].get('start', 0) * 1000)
                chunk_end = int(chunk_words[-1].get('end', 0) * 1000)
                if chunk_end <= chunk_start:
                    chunk_end = chunk_start + 500

                sub = pysrt.SubRipItem(
                    index=len(subs) + 1,
                    start=pysrt.SubRipTime(milliseconds=chunk_start),
                    end=pysrt.SubRipTime(milliseconds=chunk_end),
                    text=chunk_text,
                )
                subs.append(sub)

    subs.save(str(srt_path), encoding='utf-8')
    return str(srt_path)


def _split_words_into_chunks(words, max_chars=55):
    """将词列表按 max_chars 分组，保证在词边界切开。

    返回 [[word_dict, ...], ...] 每个子列表是一个分块。
    """
    chunks = []
    current_chunk = []
    current_len = 0

    for w in words:
        word_text = w.get('word', '').strip()
        if not word_text:
            continue
        word_len = len(word_text)
        # +1 for leading space (except first word in chunk)
        effective_len = word_len + (1 if current_chunk else 0)

        if current_chunk and current_len + effective_len > max_chars:
            # 当前块已满，保存并开始新块
            chunks.append(current_chunk)
            current_chunk = [w]
            current_len = word_len
        else:
            current_chunk.append(w)
            current_len += effective_len

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def run_whisperx_on_videos():
    """
    对 TEMP_DIR 中所有已下载视频使用 WhisperX 进行词级时间戳转录。

    仅在配置中启用且 WhisperX 已安装时执行。生成的 SRT 会替换
    yt-dlp 下载的原始字幕，提供毫秒级精确的时间轴对齐。

    模型缓存：WhisperX 模型首次下载后永久缓存在 ~/.cache/huggingface/hub/，
    后续运行不会重复下载。国内用户需设置 hf_endpoint 镜像或 hf_proxy 代理。
    """
    import os

    config = load_config()
    wx_config = config.get('whisperx', {})
    if not wx_config.get('enabled', False):
        return

    if not _check_whisperx():
        print("[!] WhisperX 未安装，无法使用词级时间戳转录。")
        print("[*] 安装方法: pip install whisperx")
        print("[*] 将回退使用 yt-dlp 自带字幕。")
        return

    # ── 在 import whisperx 之前设置 HuggingFace Hub 环境变量 ──
    # 关键：huggingface_hub 在 import 时读取环境变量，必须提前设置
    hf_endpoint = wx_config.get('hf_endpoint', '')
    hf_proxy = wx_config.get('hf_proxy', '')
    hf_offline = wx_config.get('hf_offline', False)

    if hf_endpoint:
        os.environ['HF_ENDPOINT'] = hf_endpoint
        print(f"[*] HuggingFace 镜像: {hf_endpoint}")
    if hf_proxy:
        os.environ['HTTPS_PROXY'] = hf_proxy
        os.environ['HTTP_PROXY'] = hf_proxy
        print(f"[*] HuggingFace 代理: {hf_proxy}")
    if hf_offline:
        os.environ['HF_HUB_OFFLINE'] = '1'
        print(f"[*] HuggingFace 离线模式（仅使用本地缓存）")

    import whisperx

    model_name = wx_config.get('model', 'large-v3')
    device = wx_config.get('device', 'cuda')
    compute_type = wx_config.get('compute_type', 'float16')
    language = wx_config.get('language', 'en')
    batch_size = wx_config.get('batch_size', 16)

    video_files = [
        f for f in TEMP_DIR.glob("*.mp4")
        if "_zh_sub" not in f.name
    ]
    if not video_files:
        return

    print(f"\n[*] WhisperX 词级时间戳转录已启用 (模型: {model_name}, 设备: {device})")
    print(f"[*] 共 {len(video_files)} 个视频待处理...")

    # 加载模型（所有视频共用，避免重复加载）
    try:
        print(f"[*] 正在加载 WhisperX 模型 '{model_name}'（首次下载约需 4.2GB，缓存后无需重复）...")
        model = whisperx.load_model(model_name, device, compute_type=compute_type)
        model_a, align_metadata = whisperx.load_align_model(
            language_code=language, device=device
        )
        print(f"[*] WhisperX 模型加载完成")
    except Exception as e:
        print(f"[!] WhisperX 模型加载失败: {e}")
        if not hf_endpoint and not hf_proxy and not hf_offline:
            print("[*] 提示：国内服务器需要配置 HuggingFace 镜像或代理才能下载模型：")
            print("    whisperx:")
            print("      hf_endpoint: https://hf-mirror.com   # 国内镜像（推荐）")
            print("      hf_proxy: http://127.0.0.1:7897       # 或使用代理")
            print("[*] 模型只需下载一次，缓存于 ~/.cache/huggingface/hub/")
        print("[*] 将回退使用 yt-dlp 自带字幕。")
        return

    for video_path in video_files:
        video_stem = video_path.stem
        print(f"\n  - 转录: {video_stem}")

        # 检查是否已有 WhisperX 生成的 SRT（避免重复转录）
        whisperx_srt = TEMP_DIR / f"{video_stem}.whisperx.srt"
        if whisperx_srt.exists():
            print(f"    [*] 已有 WhisperX SRT，跳过")
            continue

        audio_path = TEMP_DIR / f"{video_stem}_audio.wav"

        try:
            # 1. 提取音频 (16kHz mono WAV)
            print(f"    [*] 提取音频...")
            ffmpeg_cmd = [
                'ffmpeg', '-y', '-i', str(video_path),
                '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1',
                str(audio_path)
            ]
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"    [!] 音频提取失败: {result.stderr[:200]}")
                continue

            # 2. WhisperX 转录
            print(f"    [*] WhisperX 转录中...")
            audio = whisperx.load_audio(str(audio_path))
            transcribe_result = model.transcribe(
                audio, batch_size=batch_size, language=language
            )

            # 3. 词级对齐
            print(f"    [*] 词级时间戳对齐...")
            aligned = whisperx.align(
                transcribe_result["segments"],
                model_a, align_metadata,
                audio, device,
                return_char_alignments=False,
            )

            # 4. 转换为 SRT
            srt_target = TEMP_DIR / f"{video_stem}.srt"
            _whisperx_segments_to_srt(aligned["segments"], srt_target)
            print(f"    [✓] WhisperX SRT 已生成: {srt_target.name} "
                  f"({len(aligned['segments'])} 段)")

            # 清理旧字幕文件（yt-dlp 生成的）
            for old_srt in TEMP_DIR.glob(f"{video_stem}*.en.srt"):
                old_srt.unlink()
                print(f"    [*] 已清理旧字幕: {old_srt.name}")

        except Exception as e:
            print(f"    [!] WhisperX 转录失败: {e}")
            print(f"    [*] 将回退使用 yt-dlp 自带字幕（如存在）")

        finally:
            # 清理临时音频
            if audio_path.exists():
                audio_path.unlink()

    # 清理 WhisperX 模型释放 GPU 显存
    del model
    del model_a
    try:
        import gc
        gc.collect()
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass

    print(f"\n[*] WhisperX 转录阶段完成")


def download_video():
    """运行 yt-dlp 下载 → 转换 json3 字幕 → WhisperX 转录(可选) → 扫描结果"""
    run_yt_dlp()
    convert_json3_subtitles()
    run_whisperx_on_videos()  # 如果配置启用，会替换 SRT 为词级时间戳版本
    return scan_downloaded_files()
