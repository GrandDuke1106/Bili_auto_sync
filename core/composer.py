# core/composer.py
import os
import subprocess
from pathlib import Path
import pysubs2
import pysrt
from utils.config_manager import load_config

BASE_DIR = Path(__file__).resolve().parent.parent

def generate_ass(srt_path, chinese_texts, english_texts, output_ass_path):
    config = load_config()
    
    # 获取我们在配置中定义的准确的 FontName
    zh_font = config['subtitle']['zh_font_name']
    en_font = config['subtitle']['en_font_name']

    subs_srt = pysrt.open(srt_path)
    subs_ass = pysubs2.SSAFile()
    
    style_zh = pysubs2.SSAStyle(
        fontname=zh_font,
        fontsize=24,
        primarycolor=pysubs2.Color(255, 255, 255), 
        outlinecolor=pysubs2.Color(0, 0, 0),       
        outline=2,                                 
        shadow=0,
        marginv=35                                 
    )
    
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
    print(f"[*] 开始 FFmpeg 硬字幕压制 (保画质模式)...")
    config = load_config()
    
    # 获取字体的绝对路径
    zh_font_file = str(BASE_DIR / config['subtitle']['zh_font_path']).replace('\\', '/')
    en_font_file = str(BASE_DIR / config['subtitle']['en_font_path']).replace('\\', '/')
    ass_path_str = str(ass_path).replace('\\', '/')
    
    # Linux 环境下 FFmpeg 解决字体找不到的终极方案：
    # 强制将包含我们字体的目录作为 fontconfig 的目录
    fonts_dir = str(BASE_DIR / "configs" / "fonts")
    
    # 关键修改 1：不光指定 fontsdir，还可以使用 FFmpeg 内部变量
    # 关键修改 2：使用 -crf 18 保证几乎无损的画质 (18~20被认为是视觉无损)
    command = [
        "ffmpeg",
        "-y", 
        "-i", str(video_path),
        "-vf", f"ass='{ass_path_str}':fontsdir='{fonts_dir}'", 
        "-c:v", "libx264",
        "-preset", "medium", # 将 fast 改为 medium 以获得更好的压缩比和画质保留
        "-crf", "18",        # 极高画质
        "-c:a", "copy",     
        str(output_video_path)
    ]
    
    # 临时设置环境变量，告诉 fontconfig 我们字体的存放位置
    # 这是解决 Linux 找不到字体的杀手锏
    env = os.environ.copy()
    env["FONTCONFIG_PATH"] = fonts_dir 
    
    try:
        # 使用自定义的 env 运行
        subprocess.run(command, check=True, env=env)
        print(f"[*] 视频压制成功: {output_video_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[!] FFmpeg 压制失败！错误码: {e.returncode}")
        return False
