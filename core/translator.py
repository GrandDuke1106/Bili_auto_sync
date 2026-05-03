# core/translator.py
import pysrt
import json
from openai import OpenAI
from utils.config_manager import load_config

def chunk_list(lst, n):
    for i in range(0, len(lst), n): yield lst[i:i + n]

def translate_subtitles(srt_path):
    if not srt_path: return [], []
    config = load_config()
    api_key = config['deepseek']['api_key']
    base_url = config['deepseek']['base_url']
    model_name = config['deepseek'].get('model', 'deepseek-v4-flash') # 读取模型名称
    
    if api_key == "YOUR_DEEPSEEK_API_KEY_HERE":
        print("[!] 请配置 DeepSeek API Key!")
        return [], []

    client = OpenAI(api_key=api_key, base_url=base_url)
    subs = pysrt.open(srt_path)
    english_texts = [sub.text for sub in subs]
    chinese_texts = []
    chunks = list(chunk_list(english_texts, 100))
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


def generate_bilibili_meta(title, desc_path, sample_subs, uploader=""):
    """使用 AI 根据原标题、原简介和部分字幕内容，生成 B 站专属的标题、简介和 Tag"""
    config = load_config()
    api_key = config['deepseek']['api_key']
    base_url = config['deepseek']['base_url']
    model_name = config['deepseek'].get('model', 'deepseek-chat')
    
    if api_key == "YOUR_DEEPSEEK_API_KEY_HERE":
        return title, " ", []

    # 读取原版简介
    desc_text = ""
    if desc_path:
        try:
            with open(desc_path, 'r', encoding='utf-8') as f:
                desc_text = f.read()[:1000] # 只取前1000个字符防超长
        except Exception:
            pass
            
    client = OpenAI(api_key=api_key, base_url=base_url)
    
    sys_prompt = """
    你是一个 Bilibili 专业的视频搬运兼翻译运营。请根据提供的 YouTube 视频标题、简介和部分字幕内容，生成 B 站适合发布的元数据。
    要求：
    1. 标题 (title)：请根据视频所属的类别情景，翻译成中文。限制在 30 字符内。
    2. 简介 (description)：根据视频所属的类别情景，翻译视频的简介。不要带原作者广告链接。
    3. 标签 (tags)：根据内容提取 2 到 3 个精准的中文标签词汇。
    总之，人名以及专有名词或者难翻译为中文的不翻译，尽量做到“信达雅”。

    你必须且只能返回纯粹的 JSON 格式数据，格式如下：
    {"title": "翻译后的标题", "description": "翻译后的简介", "tags": ["标签1", "标签2"]}
    """
    
    user_prompt = f"原标题: {title}\n原简介: {desc_text}\n部分字幕: {' '.join(sample_subs[:15])}"
    
    print(f"[*] 正在请求 AI 包装视频标题与简介...")
    try:
        response = client.chat.completions.create(
            model=model_name,
            response_format={ "type": "json_object" }, # 强制要求返回 JSON
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.5
        )
        
        res_text = response.choices[0].message.content.strip()
        meta_data = json.loads(res_text)

        raw_title = meta_data.get("title", title).replace("[中字]", "").replace("[熟肉]", "").strip()
        
        if uploader:
            final_title = f"[熟肉][@{uploader}]{raw_title}"
        else:
            final_title = f"[熟肉]{raw_title}"
        
        return final_title[:80], meta_data.get("description"), meta_data.get("tags", [])
        
    except Exception as e:
        print(f"[!] 生成AI元数据失败 ({e})，使用默认格式...")
        # 失败时的降级处理也加上频道名
        fallback_prefix = f"[熟肉][{uploader}]" if uploader else "[熟肉]"
        return f"{fallback_prefix}{title[:60]}", []
