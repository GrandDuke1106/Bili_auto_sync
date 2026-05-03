# core/translator.py
import pysrt
from openai import OpenAI
from utils.config_manager import load_config

def chunk_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def translate_subtitles(srt_path):
    if not srt_path:
        print("[!] 缺少字幕文件，跳过翻译。")
        return [], []

    config = load_config()
    api_key = config['deepseek']['api_key']
    base_url = config['deepseek']['base_url']
    
    if api_key == "YOUR_DEEPSEEK_API_KEY_HERE":
        print("[!] 请先在 configs/config.yaml 中配置 DeepSeek API Key!")
        return [], []

    client = OpenAI(api_key=api_key, base_url=base_url)
    
    print(f"[*] 正在解析字幕文件: {srt_path}")
    subs = pysrt.open(srt_path)
    english_texts = [sub.text for sub in subs]
    chinese_texts = []

    chunk_size = 20
    chunks = list(chunk_list(english_texts, chunk_size))
    print(f"[*] 共有 {len(english_texts)} 行字幕，分 {len(chunks)} 次请求翻译...")
    
    for index, chunk in enumerate(chunks):
        source_text = " || ".join(chunk)
        prompt = (
            "你是一个专业的影视字幕翻译。请将以下英文字幕翻译为流畅的中文。"
            "原文的句子由 ' || ' 分隔，请你输出的中文也严格使用 ' || ' 分隔，"
            "并且数量必须与原文完全一致。绝对不要输出任何解释性文字或调整时间轴。\n\n"
            f"原文：\n{source_text}"
        )

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一个严格遵循格式的专业字幕翻译助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            translated_text = response.choices[0].message.content.strip()
            translated_lines = [line.strip() for line in translated_text.split('||')]
            
            # 容错机制：数量不对用原文补齐或截断
            if len(translated_lines) != len(chunk):
                print(f"[!] 警告: 第 {index+1} 块格式错乱，尝试修复...")
                while len(translated_lines) < len(chunk):
                    translated_lines.append(chunk[len(translated_lines)])
                translated_lines = translated_lines[:len(chunk)]
            
            chinese_texts.extend(translated_lines)
            print(f"    - 完成 {index + 1}/{len(chunks)} 块")
            
        except Exception as e:
            print(f"[!] 翻译 API 请求失败: {e}")
            chinese_texts.extend(chunk)

    return chinese_texts, english_texts
