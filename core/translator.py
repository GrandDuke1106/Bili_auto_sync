# core/translator.py
import pysrt
from openai import OpenAI
from utils.config_manager import load_config

def chunk_list(lst, n):
    for i in range(0, len(lst), n): yield lst[i:i + n]

def translate_subtitles(srt_path):
    if not srt_path: return [], []
    config = load_config()
    api_key = config['deepseek']['api_key']
    base_url = config['deepseek']['base_url']
    model_name = config['deepseek'].get('model', 'deepseek-chat') # 读取模型名称
    
    if api_key == "YOUR_DEEPSEEK_API_KEY_HERE":
        print("[!] 请配置 DeepSeek API Key!")
        return [], []

    client = OpenAI(api_key=api_key, base_url=base_url)
    subs = pysrt.open(srt_path)
    english_texts = [sub.text for sub in subs]
    chinese_texts = []
    chunks = list(chunk_list(english_texts, 20))
    print(f"[*] 开始翻译，使用模型: {model_name}...")
    
    for index, chunk in enumerate(chunks):
        source_text = " || ".join(chunk)
        prompt = (
            "你是一个专业的影视字幕翻译。请将以下英文字幕翻译为流畅的中文。"
            "原文的句子由 ' || ' 分隔，请你输出的中文也严格使用 ' || ' 分隔，"
            "数量必须与原文完全一致。绝对不要输出解释性文字。\n\n"
            f"原文：\n{source_text}"
        )
        try:
            response = client.chat.completions.create(
                model=model_name, # 使用配置的模型
                messages=[
                    {"role": "system", "content": "你是一个严格遵循格式的字幕翻译助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            translated_text = response.choices[0].message.content.strip()
            translated_lines = [line.strip() for line in translated_text.split('||')]
            
            if len(translated_lines) != len(chunk):
                print(f"[!] 第 {index+1} 块行数不匹配，尝试修复...")
                while len(translated_lines) < len(chunk): translated_lines.append(chunk[len(translated_lines)])
                translated_lines = translated_lines[:len(chunk)]
            
            chinese_texts.extend(translated_lines)
            print(f"    - 完成 {index + 1}/{len(chunks)} 块")
        except Exception as e:
            print(f"[!] 翻译失败: {e}")
            chinese_texts.extend(chunk)

    return chinese_texts, english_texts
