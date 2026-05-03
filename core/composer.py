# core/composer.py
import os
import subprocess
import sys
from pathlib import Path
import pysubs2
import pysrt
from utils.config_manager import load_config

BASE_DIR = Path(__file__).resolve().parent.parent

def generate_ass(srt_path, chinese_texts, english_texts, output_ass_path):
    config = load_config()
    
    zh_font = config['subtitle']['zh_font_name']
    en_font = config['subtitle']['en_font_name']

    subs_srt = pysrt.open(srt_path)
    subs_ass = pysubs2.SSAFile()
    
    # 中文字幕样式
    style_zh = pysubs2.SSAStyle(
        fontname=zh_font,
        fontsize=24,
        primarycolor=pysubs2.Color(255, 255, 255), 
        outlinecolor=pysubs2.Color(0, 0, 0),       
        outline=2,                                 
        shadow=0,
        marginv=35                                 
    )
    
    # 英文字幕样式
    style_en = pysubs2.SSAStyle(
        fontname=en_font,                          
        fontsize=14,
        primarycolor=pysubs2.Color(200, 200, 200), 
        outlinecolor=pysubs2.Color(0, 0, 0),
        outline=1.2,
        shadow=0,
        marginv=15                                 
    )

    subs_ass.styles["Style_ZH"] = style_zh
    subs_ass.styles["Style_EN"] = style_en

    for i, sub in enumerate(subs_srt):
        if i < len(chinese_texts) and i < len(english_texts):
            zh = chinese_texts[i]
            en = english_texts[i]
            ass_text = f"{{\\rStyle_ZH}}{zh}\\N{{\\rStyle_EN}}{en}"
            event = pysubs2.SSAEvent(start=sub.start.ordinal, end=sub.end.ordinal, text=ass_text)
            subs_ass.append(event)

    subs_ass.save(output_ass_path, encoding="utf-8")
    print(f"[*] 双语 ASS 字幕生成完毕: {output_ass_path}")


def hardcode_subtitles(video_path, ass_path, output_video_path):
    print(f"[*] 开始 FFmpeg 硬字幕压制 (H.265/HEVC 高压缩率模式)...")
    
    # 强制指定字体目录，包含你的中文字体和英文字体所在位置
    fonts_dir = str(BASE_DIR / "configs" / "fonts")
    fonts_dir_fira = str(BASE_DIR / "configs" / "fonts" / "Fira_Code_v6.2" / "ttf")
    ass_path_str = str(ass_path).replace('\\', '/')
    
    # Linux 下多个目录用冒号 : 隔开
    fallback_fonts = f"{fonts_dir}:{fonts_dir_fira}"

    # 设置环境变量，指引 FFmpeg 的字体配置器去哪里找字体
    env = os.environ.copy()
    env["FONTCONFIG_PATH"] = fonts_dir 

    command = [
        "ffmpeg",
        "-y", 
        "-i", str(video_path),
        "-vf", f"ass='{ass_path_str}':fontsdir='{fallback_fonts}'", 
        "-c:v", "libx265",    # 改为 H.265 (HEVC) 编码器
        "-preset", "fast",    # H.265 用 fast 可以在速度和体积间取得较好的平衡
        "-crf", "20",         # H.265 的 23 相当于 H.264 的 18~20 视觉质量，文件会明显变小
        "-c:a", "copy",       # 音频直接复制，不重新编码
        str(output_video_path)
    ]
    
    try:
        # 使用 Popen 来劫持底层输出，将 stderr 合并到 stdout
        # 这样 Python 的 Logger 就能顺利把 FFmpeg 的日志也写进 txt 文件了
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, 
            text=True,
            env=env,
            bufsize=1, 
            universal_newlines=True
        )

        # 实时逐行打印输出
        for line in process.stdout:
            print(line, end='')

        process.wait()
        
        if process.returncode == 0:
            print(f"\n[*] 视频压制成功: {output_video_path}")
            return True
        else:
            print(f"\n[!] FFmpeg 压制失败！错误码: {process.returncode}")
            return False

    except Exception as e:
        print(f"\n[!] FFmpeg 运行出错: {e}")
        return False
