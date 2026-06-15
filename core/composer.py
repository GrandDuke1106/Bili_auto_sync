# core/composer.py — 双语 ASS 字幕生成 + FFmpeg 硬字幕压制
import os
import re
import subprocess
import sys
import shutil
from pathlib import Path

import pysubs2
import pysrt

from utils.config_manager import load_config

BASE_DIR = Path(__file__).resolve().parent.parent


def _strip_line_end_punctuation(text):
    """移除 ASS 字幕每行末尾的标点符号，行中间的标点保留。"""
    if "\\N" not in text:
        return re.sub(r'[，。！？；：、,.!?;:]+$', '', text)

    lines = text.split("\\N")
    cleaned = [re.sub(r'[，。！？；：、,.!?;:]+$', '', line) for line in lines]
    return "\\N".join(cleaned)


def generate_ass(srt_path, chinese_texts, english_texts, output_ass_path):
    """根据 SRT 时间轴和中英文文本生成双语 ASS 字幕文件。

    每条字幕固定为两行：上行中文（Style_ZH）、下行英文（Style_EN）。
    字体名称、字号等样式参数从 config.yaml 的 subtitle 段读取。
    """
    config = load_config()
    zh_font = config['subtitle']['zh_font_name']
    en_font = config['subtitle']['en_font_name']

    subs_srt = pysrt.open(srt_path)
    subs_ass = pysubs2.SSAFile()

    style_zh = pysubs2.SSAStyle(
        fontname=zh_font,
        fontsize=20,
        primarycolor=pysubs2.Color(255, 255, 255),
        outlinecolor=pysubs2.Color(0, 0, 0),
        outline=0.8,
        shadow=0,
        marginv=15,
    )

    style_en = pysubs2.SSAStyle(
        fontname=en_font,
        fontsize=12,
        primarycolor=pysubs2.Color(200, 200, 200),
        outlinecolor=pysubs2.Color(0, 0, 0),
        outline=0.5,
        shadow=0,
        marginv=3,
    )

    subs_ass.styles["Style_ZH"] = style_zh
    subs_ass.styles["Style_EN"] = style_en

    for i, sub in enumerate(subs_srt):
        if i < len(chinese_texts) and i < len(english_texts):
            # 清理 AI 输出或原始字幕中可能混入的换行符，统一为单行纯文本
            zh_raw = chinese_texts[i].replace('\r', '').replace('\n', '').strip()
            en_raw = english_texts[i].replace('\r', '').replace('\n', ' ').strip()

            zh = _strip_line_end_punctuation(zh_raw)
            en = _strip_line_end_punctuation(en_raw)

            ass_text = f"{{\\rStyle_ZH}}{zh}\\N{{\\rStyle_EN}}{en}"
            event = pysubs2.SSAEvent(
                start=sub.start.ordinal, end=sub.end.ordinal, text=ass_text
            )
            subs_ass.append(event)

    subs_ass.save(str(output_ass_path), encoding="utf-8")
    print(f"[*] 双语 ASS 字幕生成完毕: {output_ass_path}")


def hardcode_subtitles(video_path, ass_path, output_video_path):
    """使用 FFmpeg 将 ASS 字幕烧录到视频中（硬字幕压制）。

    字体目录从 config.yaml 的 subtitle.fonts_dir 读取，递归收集所有 ttf/otf
    文件后传递给 FFmpeg 的 ass 滤镜。视频编码参数从 ffmpeg 段读取。
    """
    config = load_config()
    configured_fonts_dir = config.get("subtitle", {}).get("fonts_dir", "configs/fonts")
    fonts_base_dir = (BASE_DIR / configured_fonts_dir).resolve()

    # 将字体文件扁平复制到临时目录，供 FFmpeg fontsdir 参数使用
    flat_fonts_dir = BASE_DIR / "data" / "temp_workspace" / "flat_fonts"
    flat_fonts_dir.mkdir(parents=True, exist_ok=True)

    if not fonts_base_dir.exists():
        print(f"[!] 警告: 字体目录 {fonts_base_dir} 不存在，请检查配置。")
    else:
        for ext in ["*.ttf", "*.otf", "*.TTF", "*.OTF"]:
            for font_file in fonts_base_dir.rglob(ext):
                dest_file = flat_fonts_dir / font_file.name
                if not dest_file.exists():
                    shutil.copy2(font_file, dest_file)

    ffmpeg_cfg = config.get("ffmpeg", {})
    video_args = ffmpeg_cfg.get(
        "video_args", ["-c:v", "libx264", "-preset", "medium", "-crf", "23"]
    )
    audio_encoder = ffmpeg_cfg.get("audio_encoder", "copy")

    print(f"[*] FFmpeg 视频参数: {' '.join(video_args)}")

    fonts_dir_str = str(flat_fonts_dir).replace('\\', '/')

    # 将 ASS 复制为安全文件名，避免特殊字符导致 ffmpeg 滤镜参数转义问题
    safe_ass_path = flat_fonts_dir.parent / "subtitle_safe.ass"
    shutil.copy2(str(ass_path), safe_ass_path)
    safe_ass_path_str = str(safe_ass_path).replace('\\', '/')

    env = os.environ.copy()
    env["FONTCONFIG_PATH"] = fonts_dir_str

    command = [
        "ffmpeg",
        "-y",
        "-i", str(video_path),
        "-vf", f"ass={safe_ass_path_str}:fontsdir={fonts_dir_str}",
        *video_args,
        "-c:a", audio_encoder,
        str(output_video_path),
    ]

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
            bufsize=1,
            universal_newlines=True,
        )

        for line in process.stdout:
            print(line, end='')

        process.wait()

        if process.returncode == 0:
            print(f"\n[*] 视频压制成功: {output_video_path}")
            return True
        else:
            print(f"\n[!] FFmpeg 压制失败，错误码: {process.returncode}")
            return False

    except Exception as e:
        print(f"\n[!] FFmpeg 运行出错: {e}")
        return False
    finally:
        if safe_ass_path.exists():
            safe_ass_path.unlink()
