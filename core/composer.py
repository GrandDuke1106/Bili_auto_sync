# core/composer.py
import subprocess
from pathlib import Path
import pysubs2
import pysrt
from utils.config_manager import load_config

BASE_DIR = Path(__file__).resolve().parent.parent

def generate_ass(srt_path, chinese_texts, english_texts, output_ass_path):
    config = load_config()
    
    # 获取字体名称，不包含路径
    zh_font = config['subtitle']['zh_font_name']
    en_font = config['subtitle']['en_font_name']

    subs_srt = pysrt.open(srt_path)
    
    subs_ass = pysubs2.SSAFile()
    
    # 中文字幕样式：大字号，白色主体，黑色描边
    style_zh = pysubs2.SSAStyle(
        fontname=zh_font,
        fontsize=24,
        primarycolor=pysubs2.Color(255, 255, 255), 
        outlinecolor=pysubs2.Color(0, 0, 0),       
        outline=2,                                 
        shadow=0,
        marginv=35                                 
    )
    
    # 英文字幕样式：等宽字体，较小，灰色，细描边
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
            
            event = pysubs2.SSAEvent(
                start=sub.start.ordinal, 
                end=sub.end.ordinal, 
                text=ass_text
            )
            subs_ass.append(event)

    subs_ass.save(output_ass_path, encoding="utf-8")
    print(f"[*] 双语 ASS 字幕生成完毕: {output_ass_path}")


def hardcode_subtitles(video_path, ass_path, output_video_path):
    print(f"[*] 开始 FFmpeg 硬字幕压制 (这可能会花费一些时间)...")
    
    # 在 Linux/Debian 环境下处理路径
    config = load_config()
    # 为了让 FFmpeg 找到自定义字体，我们需要将包含字体的文件夹挂载到命令环境中
    fonts_dir = str(BASE_DIR / "configs" / "fonts")
    ass_path_str = str(ass_path)
    
    # 关键：使用 :fontsdir 参数告诉 ffmpeg 去哪里找我们放的 TTF 文件
    vf_filter = f"ass='{ass_path_str}':fontsdir='{fonts_dir}'"

    command = [
        "ffmpeg",
        "-y", 
        "-i", str(video_path),
        "-vf", vf_filter, 
        "-c:v", "libx264",
        "-preset", "fast",  # 使用 fast 预设平衡速度和压缩率
        "-crf", "23",       # 控制画质 (数值越小画质越好，体积越大。23 是一个合理的默认值)
        "-c:a", "copy",     # 音频不重编码
        str(output_video_path)
    ]
    
    try:
        # 使用 check=True，如果 ffmpeg 报错会抛出异常
        subprocess.run(command, check=True)
        print(f"[*] 视频压制成功: {output_video_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[!] FFmpeg 压制失败！请检查视频格式或字体路径。错误码: {e.returncode}")
        return False
