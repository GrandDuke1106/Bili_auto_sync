# core/composer.py
import os
import re
import subprocess
import sys
import shutil
import textwrap
from pathlib import Path
import pysubs2
import pysrt
from utils.config_manager import load_config

# --- jieba 惰性初始化 ---
_jieba_loaded = False

def _get_jieba():
    """惰性加载 jieba 分词器"""
    global _jieba_loaded
    if not _jieba_loaded:
        try:
            import jieba
            _jieba_loaded = True
            return jieba
        except ImportError:
            return None
    try:
        import jieba
        return jieba
    except ImportError:
        return None


def _has_english_word(text):
    """检测文本中是否包含英文单词（连续的拉丁字母）"""
    return bool(re.search(r'[a-zA-Z]{2,}', text))


def _find_english_boundaries(text):
    """返回所有英文单词的 (start, end) 区间，用于保护不被切断"""
    boundaries = []
    for m in re.finditer(r'[a-zA-Z0-9]+', text):
        boundaries.append((m.start(), m.end()))
    return boundaries


def _is_safe_split_position(pos, text, en_boundaries):
    """检查在 pos 处切断是否会截断英文单词"""
    for start, end in en_boundaries:
        # 如果断点在单词内部（start < pos < end），则不安全
        if start < pos < end:
            return False
    return True


def _smart_line_break_chinese(text, max_line_width=25):
    """
    使用 jieba 分词 + 词语边界保护，对中文文本进行智能换行。

    策略：
    1. 长度 ≤ max_line_width → 保持单行
    2. 长度 > max_line_width → 在句子中间附近寻找最佳断点：
       - 优先级 100：中文标点符号后（，。！？；：）
       - 优先级 50：jieba 词语边界
       - 优先级 30：空格位置（中英混排）
       - 自动排除会切断英文单词的位置
    3. 后半段至少保留 MIN_TAIL 个字符，否则不换行
    """
    if not text or len(text) <= max_line_width:
        return text

    MIN_TAIL = 6  # 后半段最小长度
    target = len(text) // 2
    # 搜索范围：target 前后各 40%
    search_radius = max(int(len(text) * 0.4), 10)
    search_start = max(0, target - search_radius)
    search_end = min(len(text), target + search_radius)

    # 获取英文单词边界（用于保护）
    en_boundaries = _find_english_boundaries(text)

    candidates = []  # (position, priority, score_for_sort)

    # ---- 优先级 100：中文标点符号后 ----
    cn_punct_pattern = re.compile(r'[，。！？；：、]')
    for m in cn_punct_pattern.finditer(text):
        pos = m.end()  # 在标点之后换行
        if search_start <= pos <= search_end:
            if _is_safe_split_position(pos, text, en_boundaries):
                # 确保后半段不太短
                if len(text) - pos >= MIN_TAIL:
                    candidates.append((pos, 100))

    # ---- 优先级 50：jieba 词语边界 ----
    jieba = _get_jieba()
    if jieba and not candidates:
        # 使用精确模式分词，获取每个词的起止位置
        tokens = list(jieba.tokenize(text))
        for tok in tokens:
            pos = tok[2]  # end position of the token
            if search_start <= pos <= search_end:
                if _is_safe_split_position(pos, text, en_boundaries):
                    if len(text) - pos >= MIN_TAIL:
                        candidates.append((pos, 50))

    # ---- 优先级 30：空格位置（中英混排的自然断点） ----
    if not candidates:
        for m in re.finditer(r'\s+', text):
            pos = m.start()
            if search_start <= pos <= search_end:
                if _is_safe_split_position(pos, text, en_boundaries):
                    if len(text) - pos >= MIN_TAIL:
                        candidates.append((pos, 30))

    # ---- 无候选：尝试放宽条件，在整个文本中寻找最佳标点 ----
    if not candidates:
        for m in cn_punct_pattern.finditer(text):
            pos = m.end()
            if _is_safe_split_position(pos, text, en_boundaries):
                if len(text) - pos >= MIN_TAIL:
                    candidates.append((pos, 100))

    # 如果依然没有候选，保持单行
    if not candidates:
        return text

    # 选择离 target 最近且优先级最高的位置
    candidates.sort(key=lambda x: (abs(x[0] - target), -x[1]))
    split_pos = candidates[0][0]

    left = text[:split_pos].rstrip()
    right = text[split_pos:].lstrip()

    if not left or not right:
        return text

    return left + "\\N" + right


def _strip_line_end_punctuation(text):
    """去除 ASS 字幕每行结尾的标点符号（行中间的标点保留），让字幕更美观"""
    if "\\N" not in text:
        # 单行：直接去尾部标点
        return re.sub(r'[，。！？；：、,.!?;:]+$', '', text)
    
    lines = text.split("\\N")
    cleaned = []
    for line in lines:
        # 去掉行尾的中文和英文标点
        line = re.sub(r'[，。！？；：、,.!?;:]+$', '', line)
        cleaned.append(line)
    return "\\N".join(cleaned)


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
            # 彻底清理掉 AI 或原始字幕中可能带有的真实换行符，全部变成单行纯文本
            zh_raw = chinese_texts[i].replace('\r', '').replace('\n', '').strip()
            en_raw = english_texts[i].replace('\r', '').replace('\n', ' ').strip()

            # ── 严格单行模式：不再对中文/英文做任何换行 ──
            # 每个 ASS 事件固定为 1 行中文 + 1 行英文
            # 长句分割由上游 optimize_srt / WhisperX 词级切分负责
            zh = _strip_line_end_punctuation(zh_raw)
            en = _strip_line_end_punctuation(en_raw)

            ass_text = f"{{\\rStyle_ZH}}{zh}\\N{{\\rStyle_EN}}{en}"
            event = pysubs2.SSAEvent(start=sub.start.ordinal, end=sub.end.ordinal, text=ass_text)
            subs_ass.append(event)

    subs_ass.save(str(output_ass_path), encoding="utf-8")
    print(f"[*] 双语 ASS 字幕生成完毕: {output_ass_path}")


def hardcode_subtitles(video_path, ass_path, output_video_path):
    print(f"[*] 开始 FFmpeg 硬字幕压制...")
    
    # 1. 加载配置
    config = load_config()
    configured_fonts_dir = config.get("subtitle", {}).get("fonts_dir", "configs/fonts")
    
    # 2. 将配置的路径转换为绝对路径
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

    # 转义 ffmpeg 滤镜参数中的特殊字符(使用反斜杠转义)
    # ffmpeg 滤镜语法中特殊字符: \ ' : , [ ] ; = %
    def _escape_ffmpeg_filter_arg(s):
        for ch in "\\':,[];=%":
            s = s.replace(ch, "\\" + ch)
        return s
    ass_path_escaped = _escape_ffmpeg_filter_arg(ass_path_str)
    fonts_dir_escaped = _escape_ffmpeg_filter_arg(fonts_dir_str)

    env = os.environ.copy()
    env["FONTCONFIG_PATH"] = fonts_dir_str

    command = [
        "ffmpeg",
        "-y",
        "-i", str(video_path),
        "-vf", f"ass='{ass_path_escaped}':fontsdir='{fonts_dir_escaped}'",
        #===cpu预设参数===
        # "-c:v", "libx264",        # 使用h264编码
        # "-preset", "fast",        # 编码速度
        # "-crf", "18",             # 画质质量
        #===英伟达预设参数
        "-c:v", "h264_nvenc",   # 可以将 libx264 替换为 NVIDIA 硬件编码器
        "-preset", "p4",        # NVENC 专属预设 (p1-p7，p4 是速度和质量的最佳平衡点)
        "-cq", "18",            # NVENC 不直接支持 -crf 参数，使用 -cq (Constant Quality) 代替
        "-b:v", "0",            # 配合 -cq 使用，允许动态码率不受限
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
