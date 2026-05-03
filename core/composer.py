import pysubs2
from utils.config_manager import load_config

def create_bilingual_ass(chinese_texts, english_texts, times, output_ass_path):
    """
    生成带描边的双语 ASS 字幕文件
    chinese_texts: 中文字幕列表
    english_texts: 英文字幕列表
    times: 时间轴列表，格式为 [(start_ms, end_ms), ...]
    """
    config = load_config()
    font_name = config['subtitle']['font_name']

    # 初始化 ASS 对象
    subs = pysubs2.SSAFile()
    
    # 定义中文字幕样式 (主字幕)
    # 大小 24，纯白，2像素黑色描边，稍微靠上
    style_zh = pysubs2.SSAStyle(
        fontname=font_name,
        fontsize=24,
        primarycolor=pysubs2.Color(255, 255, 255), # 白色
        outlinecolor=pysubs2.Color(0, 0, 0),       # 黑色描边
        outline=2,                                 # 描边粗细
        shadow=0,
        marginv=35                                 # 底部边距（给英文留空间）
    )
    
    # 定义英文字幕样式 (副字幕)
    # 大小 14，浅灰，1像素黑色描边，贴近底部
    style_en = pysubs2.SSAStyle(
        fontname="Arial",                          # 英文一般用 Arial 即可
        fontsize=14,
        primarycolor=pysubs2.Color(200, 200, 200), # 浅灰色 (&H00CCCCCC)
        outlinecolor=pysubs2.Color(0, 0, 0),
        outline=1.5,
        shadow=0,
        marginv=15                                 # 贴近屏幕底部
    )

    subs.styles["Style_ZH"] = style_zh
    subs.styles["Style_EN"] = style_en

    # 将双语合并为 ASS 事件并写入
    for zh, en, (start, end) in zip(chinese_texts, english_texts, times):
        # 使用 ASS 标签 {\rStyle_Name} 来在一行内切换样式，\N 用于换行
        ass_text = f"{{\\rStyle_ZH}}{zh}\\N{{\\rStyle_EN}}{en}"
        
        event = pysubs2.SSAEvent(start=start, end=end, text=ass_text)
        subs.append(event)

    subs.save(output_ass_path, encoding="utf-8")
    print(f"[*] 双语字幕已生成: {output_ass_path}")
