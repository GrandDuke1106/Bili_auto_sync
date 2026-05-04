# core/translator.py
import pysrt
import re
import json
from openai import OpenAI
from utils.config_manager import load_config

def chunk_list(lst, n):
    for i in range(0, len(lst), n): yield lst[i:i + n]

def optimize_srt(srt_path):
    """终极修复：彻底重组 YouTube 破碎的自动字幕时间轴和断句"""
    if not srt_path: return
    subs = pysrt.open(srt_path)
    if not subs: return
    
    # 第一步：把所有破碎的字幕拼成一条时间连续的“长蛇”
    merged_items = []
    for sub in subs:
        # 无情地删掉所有的换行符，用空格代替，并清理多余空格
        clean_text = re.sub(r'\s+', ' ', sub.text.replace('\n', ' ')).strip()
        if not clean_text: continue
        
        # 记录每一个碎片块的时间和文字
        merged_items.append({
            'start': sub.start.ordinal,
            'end': sub.end.ordinal,
            'text': clean_text
        })
        
    # 第二步：基于标点符号，重新把这条“长蛇”切分成完美的语义句子
    optimized_subs = pysrt.SubRipFile()
    
    current_sentence = ""
    current_start = -1
    current_end = -1
    
    for item in merged_items:
        # 初始化句子的起始时间
        if current_start == -1:
            current_start = item['start']
            
        # 累加文字
        if current_sentence:
            current_sentence += " " + item['text']
        else:
            current_sentence = item['text']
            
        # 更新当前句子的结束时间为这个碎片的结束时间
        current_end = item['end']
        
        # 核心判断：如果这句话遇到了结尾标点，或者实在太长了（比如没有标点瞎说了一通，强制 120 字符截断）
        if re.search(r'[.?!]\s*$', current_sentence) or len(current_sentence) > 120:
            # 建立一个全新的字幕块
            new_sub = pysrt.SubRipItem(
                index=len(optimized_subs) + 1,
                start=pysrt.SubRipTime(milliseconds=current_start),
                end=pysrt.SubRipTime(milliseconds=current_end),
                text=current_sentence.strip()
            )
            optimized_subs.append(new_sub)
            
            # 清空缓存，准备迎接下一句话
            current_sentence = ""
            current_start = -1
            
    # 收尾：把最后可能还没遇到标点的话也加进去
    if current_sentence:
        new_sub = pysrt.SubRipItem(
            index=len(optimized_subs) + 1,
            start=pysrt.SubRipTime(milliseconds=current_start),
            end=pysrt.SubRipTime(milliseconds=current_end),
            text=current_sentence.strip()
        )
        optimized_subs.append(new_sub)
        
    # 第三步：消除由于重新切分导致的时间轴微小重叠
    for i in range(len(optimized_subs) - 1):
        if optimized_subs[i].end > optimized_subs[i+1].start:
            # 各让一步，取中点
            mid_time = (optimized_subs[i].end.ordinal + optimized_subs[i+1].start.ordinal) // 2
            optimized_subs[i].end = pysrt.SubRipTime(milliseconds=mid_time)
            optimized_subs[i+1].start = pysrt.SubRipTime(milliseconds=mid_time)

    optimized_subs.save(srt_path, encoding='utf-8')

def translate_subtitles(srt_path, uploader_id=""):
    if not srt_path: return [], []
    optimize_srt(srt_path)
    config = load_config()
    api_key = config['deepseek']['api_key']
    base_url = config['deepseek']['base_url']
    model_name = config['deepseek'].get('model', 'deepseek-v4-flash') # 读取模型名称
    
    if api_key == "YOUR_DEEPSEEK_API_KEY_HERE":
        print("[!] 请配置 DeepSeek API Key!")
        return [], []

    style_name = config.get('bilibili', {}).get('channel_styles', {}).get(uploader_id, 'default')
    sys_prompt = config.get('prompts', {}).get(style_name, {}).get('subtitles', config['prompts']['default']['subtitles'])

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
                model=model_name,
                messages=[
                    # 使用动态获取的系统提示词，并且强调分隔符规则
                    {"role": "system", "content": f"{sys_prompt}\n\n重要：你必须严格保持输入文本的结构，英文输入是以 ' || ' 分隔的句子，你的中文输出也必须使用 ' || ' 作为分隔符，且输出的句子数量必须与输入完全一致。"},
                    {"role": "user", "content": prompt}
                ],
                # 如果是严谨科学，可以适当调低 temperature 让输出更稳定
                temperature=0.2 if style_name == 'science_strict' else 0.4 
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


def generate_bilibili_meta(title, desc_path, sample_subs, uploader_name="", uploader_id=""):
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
                desc_text = f.read()[:5000]
        except Exception:
            pass
            
    client = OpenAI(api_key=api_key, base_url=base_url)

    style_name = config.get('bilibili', {}).get('channel_styles', {}).get(uploader_id, 'default')
    meta_prompt_base = config.get('prompts', {}).get(style_name, {}).get('meta', config['prompts']['default']['meta'])

    sys_prompt = f"""
    {meta_prompt_base}
    
    你必须严格以合法的 JSON 格式返回结果，不能包含任何其他说明文字，格式如下：
    {{"title": "生成的中文标题", "description": "生成的简介", "tags": ["标签1", "标签2"]}}
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
        
        if uploader_name:
            final_title = f"[熟肉][{uploader_name}]{raw_title}"
        else:
            final_title = f"[熟肉]{raw_title}"
        
        return final_title[:80], meta_data.get("description"), meta_data.get("tags", [])
        
    except Exception as e:
        print(f"[!] 生成AI元数据失败 ({e})，使用默认格式...")
        fallback_prefix = f"[熟肉][{uploader_name}]" if uploader_name else "[熟肉]"
        return f"{fallback_prefix}{title[:60]}", []
