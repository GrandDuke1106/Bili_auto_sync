# core/composer.py
import os
import subprocess
import sys
import shutil
import textwrap
from pathlib import Path
import pysubs2
import pysrt
from utils.config_manager import load_config

BASE_DIR = Path(__file__).resolve().parent.parent

def generate_ass(srt_path, chinese_texts, english_texts, output_ass_path):
    config = load_config()
    
    # 我们只读取字体名字
    zh_font = config['subtitle']['zh_font_name']
    en_font = config['subtitle']['en_font_name']

    subs_srt = pysrt.open(srt_path)
    subs_ass = pysubs2.SSAFile()
    
    # 中文字幕样式
    style_zh = pysubs2.SSAStyle(
        fontname=zh_font,
        fontsize=20,
        primarycolor=pysubs2.Color(255, 255, 255), 
        outlinecolor=pysubs2.Color(0, 0, 0),       
        outline=0.8,                                 
        shadow=0,
        marginv=15                                 
    )
    
    # 英文字幕样式
    style_en = pysubs2.SSAStyle(
        fontname=en_font,                          
        fontsize=12,
        primarycolor=pysubs2.Color(200, 200, 200), 
        outlinecolor=pysubs2.Color(0, 0, 0),
        outline=0.5,
        shadow=0,
        marginv=3                                 
    )

    subs_ass.styles["Style_ZH"] = style_zh
    subs_ass.styles["Style_EN"] = style_en

    for i, sub in enumerate(subs_srt):
        if i < len(chinese_texts) and i < len(english_texts):
            # 清理掉 AI 或原始字幕中可能带有的换行符，全部变成单行纯文本
            zh_raw = chinese_texts[i].replace('\r', '').replace('\n', '')
            en_raw = english_texts[i].replace('\r', '').replace('\n', ' ')

            # 智能换行：中文超过 25 个字符，尝试在中间偏后的逗号处切开
            zh = zh_raw
            if len(zh_raw) > 25:
                split_idx = zh_raw.rfind('，', 0, 25)
                if split_idx != -1:
                    zh = zh_raw[:split_idx+1] + "\\N" + zh_raw[split_idx+1:]
                else:
                    mid = len(zh_raw) // 2
                    zh = zh_raw[:mid] + "\\N" + zh_raw[mid:]

            # 智能换行：英文按照 50 个字母的宽度进行安全的单词级自动折行
            en_wrapped = textwrap.wrap(en_raw, width=50)
            en = "\\N".join(en_wrapped)

            ass_text = f"{{\\rStyle_ZH}}{zh}\\N{{\\rStyle_EN}}{en}"
            event = pysubs2.SSAEvent(start=sub.start.ordinal, end=sub.end.ordinal, text=ass_text)
            subs_ass.append(event)

    subs_ass.save(output_ass_path, encoding="utf-8")
    print(f"[*] 双语 ASS 字幕生成完毕: {output_ass_path}")


def hardcode_subtitles(video_path, ass_path, output_video_path):
    print(f"[*] 开始 FFmpeg 硬字幕压制...")
    
    # 1. 加载配置
    config = load_config()
    configured_fonts_dir = config.get("subtitle", {}).get("fonts_dir", "configs/fonts")
    
    # 2. 将配置的路径转换为绝对路径
    # 如果用户填的是绝对路径，Path 会直接使用；如果是相对路径，会拼在 BASE_DIR 后面
    fonts_base_dir = (BASE_DIR / configured_fonts_dir).resolve()
    
    # 3. 创建扁平化临时目录
    flat_fonts_dir = BASE_DIR / "data" / "temp_workspace" / "flat_fonts"
    flat_fonts_dir.mkdir(parents=True, exist_ok=True)
    
    # 4. 将配置目录下的所有字体复制到扁平目录
    print(f"[*] 正在从 {fonts_base_dir} 提取字体文件...")
    if not fonts_base_dir.exists():
        print(f"[!] 警告: 字体目录 {fonts_base_dir} 不存在！请检查配置。")
    else:
        for ext in ["*.ttf", "*.otf", "*.TTF", "*.OTF"]:
            for font_file in fonts_base_dir.rglob(ext):
                dest_file = flat_fonts_dir / font_file.name
                if not dest_file.exists():
                    shutil.copy2(font_file, dest_file)
                
    # 5. FFmpeg 指令
    fonts_dir_str = str(flat_fonts_dir).replace('\\', '/')
    ass_path_str = str(ass_path).replace('\\', '/')

    env = os.environ.copy()
    env["FONTCONFIG_PATH"] = fonts_dir_str 

    command = [
        "ffmpeg",
        "-y", 
        "-i", str(video_path),
        "-vf", f"ass='{ass_path_str}':fontsdir='{fonts_dir_str}'", 
        #===cpu预设参数===
        "-c:v", "libx264",        # 使用h264编码
        "-preset", "fast",        # 编码速度
        "-crf", "18",             # 画质质量
        #===英伟达预设参数
        # "-c:v", "h264_nvenc",   # 可以将 libx264 替换为 NVIDIA 硬件编码器
        # "-preset", "p4",        # NVENC 专属预设 (p1-p7，p4 是速度和质量的最佳平衡点)
        # "-cq", "18",            # NVENC 不直接支持 -crf 参数，使用 -cq (Constant Quality) 代替
        # "-b:v", "0",            # 配合 -cq 使用，允许动态码率不受限
        #===预设结束
        "-c:a", "copy",       
        str(output_video_path)
    ]
    
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, 
            text=True,
            env=env,
            bufsize=1, 
            universal_newlines=True
        )

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
