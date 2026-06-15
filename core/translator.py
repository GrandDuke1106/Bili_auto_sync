# core/translator.py — DeepSeek AI 字幕翻译 + B 站元数据生成
import json
import re

import pysrt
from openai import OpenAI

from core.srt_optimizer import optimize_srt
from utils.config_manager import load_config


def chunk_list(lst, n):
    """将列表按每 n 个元素切分为多个子列表。"""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


# ==========================================================================
# 编号格式 Prompt 构建与解析
# ==========================================================================


def _build_numbered_prompt(chunk, start_idx):
    """将字幕块构建为编号格式的 prompt，编号从 start_idx+1 开始。"""
    lines = []
    for j, text in enumerate(chunk):
        lines.append(f"[{j + 1}] {text}")
    return "\n".join(lines)


def _parse_numbered_response(response_text, expected_count):
    """从编号格式的 AI 响应中提取每条翻译。

    Returns:
        list: 长度 = expected_count，缺失项为 None。
    """
    lines = []
    for j in range(1, expected_count + 1):
        pattern = rf'\[{j}\]\s*(.+?)(?=\[\d+\]|\Z)'
        match = re.search(pattern, response_text, re.DOTALL)
        if match:
            lines.append(match.group(1).strip())
        else:
            lines.append(None)
    return lines


# ==========================================================================
# 专有名词保留指令
# ==========================================================================


def _build_proper_noun_instruction(uploader_name, uploader_id, config):
    """构建"专有名词保留不翻译"的提示词片段。

    收集来源：
    1. 频道名 / 上传者名（从 yt-dlp 元数据自动获取）
    2. translation.preserve_proper_nouns（全局）
    3. translation.channel_preserve_nouns（按频道 ID）
    """
    proper_nouns = set()

    if uploader_name and uploader_name.strip():
        proper_nouns.add(uploader_name.strip())

    custom_nouns = config.get('translation', {}).get('preserve_proper_nouns', [])
    if isinstance(custom_nouns, list):
        for noun in custom_nouns:
            if noun and str(noun).strip():
                proper_nouns.add(str(noun).strip())

    channel_nouns = (
        config.get('translation', {})
        .get('channel_preserve_nouns', {})
        .get(uploader_id, [])
    )
    if isinstance(channel_nouns, list):
        for noun in channel_nouns:
            if noun and str(noun).strip():
                proper_nouns.add(str(noun).strip())

    if not proper_nouns:
        return ""

    nouns_list = "\n".join(f"  - {n}" for n in sorted(proper_nouns))
    return (
        "\n\n【专有名词保留规则】以下专有名词/品牌名/频道名请保持原文不翻译，"
        f"直接原样保留在中文译文中：\n{nouns_list}"
    )


# ==========================================================================
# AI 字幕翻译
# ==========================================================================


def translate_subtitles(srt_path, uploader_id="", uploader_name=""):
    """使用 DeepSeek API 将 SRT 英文字幕逐条翻译为中文。

    流程：先调用 srt_optimizer.optimize_srt 优化时间轴，再按 20 条一组
    分批请求 API。通过编号格式 [N] 保证输入输出严格一一对应，带重试和
    上下文窗口机制。
    """
    if not srt_path:
        return [], []

    # 第一步：优化 SRT 时间轴
    optimize_srt(srt_path)

    config = load_config()
    api_key = config['deepseek']['api_key']
    base_url = config['deepseek']['base_url']
    model_name = config['deepseek'].get('model', 'deepseek-v4-flash')

    if api_key == "YOUR_DEEPSEEK_API_KEY_HERE":
        print("[!] 请配置 DeepSeek API Key!")
        return [], []

    # 按频道选择翻译风格 prompt
    style_name = config.get('bilibili', {}).get('channel_styles', {}).get(
        uploader_id, 'default'
    )
    sys_prompt = config.get('prompts', {}).get(style_name, {}).get(
        'subtitles', config['prompts']['default']['subtitles']
    )

    proper_noun_instruction = _build_proper_noun_instruction(
        uploader_name, uploader_id, config
    )

    system_message = (
        f"{sys_prompt}{proper_noun_instruction}\n\n"
        "【输出格式要求】\n"
        "1. 输入是一组编号的英文字幕，每条格式为 [N] 原文。\n"
        "2. 你必须逐条翻译，输出格式也必须严格为 [N] 中文译文。\n"
        "3. 编号 [N] 必须原样保留，不得跳过、合并或新增编号。\n"
        "4. 只输出翻译结果，绝对不要添加任何解释、备注或额外文字。"
    )

    client = OpenAI(api_key=api_key, base_url=base_url)
    subs = pysrt.open(srt_path)
    english_texts = [sub.text for sub in subs]
    chinese_texts = []
    chunks = list(chunk_list(english_texts, 20))
    total_chunks = len(chunks)
    print(f"[*] 开始翻译，使用模型: {model_name}，共 {total_chunks} 块...")

    MAX_CONTEXT_TURNS = 3

    for index, chunk in enumerate(chunks):
        chunk_size = len(chunk)
        source_text = _build_numbered_prompt(chunk, index * 20)

        prompt = (
            f"请将以下 {chunk_size} 条英文字幕逐条翻译为中文，"
            f"严格保持 [N] 编号格式：\n\n{source_text}"
        )

        messages = [{"role": "system", "content": system_message}]

        # 附加上下文历史（最近 3 轮 Q&A）以提供翻译连贯性
        context_start = max(0, index - MAX_CONTEXT_TURNS)
        for ctx_idx in range(context_start, index):
            if ctx_idx < len(chunks):
                ctx_chunk = chunks[ctx_idx]
                ctx_prompt = _build_numbered_prompt(ctx_chunk, ctx_idx * 20)
                messages.append({
                    "role": "user",
                    "content": (
                        f"请将以下 {len(ctx_chunk)} 条英文字幕逐条翻译为中文，"
                        f"严格保持 [N] 编号格式：\n\n{ctx_prompt}"
                    ),
                })
                ctx_start_line = ctx_idx * 20
                ctx_end_line = min(ctx_start_line + len(ctx_chunk), len(chinese_texts))
                ctx_translated = chinese_texts[ctx_start_line:ctx_end_line]
                if ctx_translated:
                    ctx_response = "\n".join(
                        f"[{j+1}] {t}" for j, t in enumerate(ctx_translated)
                    )
                    messages.append({"role": "assistant", "content": ctx_response})

        messages.append({"role": "user", "content": prompt})

        translated_lines = None
        max_retries = 2

        for attempt in range(max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=0.2 if style_name == 'science_strict' else 0.4,
                )
                raw_text = response.choices[0].message.content.strip()

                parsed = _parse_numbered_response(raw_text, chunk_size)
                valid_count = sum(1 for x in parsed if x is not None)

                if valid_count == chunk_size:
                    translated_lines = parsed
                    break
                elif attempt < max_retries:
                    missing = [j + 1 for j, x in enumerate(parsed) if x is None]
                    print(f"    [!] 第 {index+1} 块缺失编号 {missing}，第 {attempt+1} 次重试...")
                    retry_hint = (
                        f"你的上一次输出丢失了以下编号的翻译：{missing}。"
                        f"请重新输出完整的 {chunk_size} 条翻译，"
                        f"确保每条都有对应的 [N] 编号。\n\n{source_text}"
                    )
                    messages.append({"role": "user", "content": retry_hint})
                else:
                    print(f"    [!] 第 {index+1} 块经 {max_retries} 次重试仍缺失 {missing}，"
                          f"使用原文填充")
                    for j in range(chunk_size):
                        if parsed[j] is None:
                            parsed[j] = chunk[j]
                    translated_lines = parsed
            except Exception as e:
                if attempt < max_retries:
                    print(f"    [!] 第 {index+1} 块 API 错误: {e}，第 {attempt+1} 次重试...")
                else:
                    print(f"    [!] 第 {index+1} 块翻译失败: {e}，使用原文填充")
                    translated_lines = list(chunk)

        if translated_lines is None:
            translated_lines = list(chunk)

        chinese_texts.extend(translated_lines)
        print(f"    - 完成 {index + 1}/{total_chunks} 块")

    return chinese_texts, english_texts


# ==========================================================================
# B 站元数据生成
# ==========================================================================


def generate_bilibili_meta(title, desc_path, sample_subs,
                           uploader_name="", uploader_id=""):
    """使用 DeepSeek API 根据原标题、原简介和字幕样本生成 B 站标题、简介和标签。

    Returns:
        (final_title, description, tags): 标题已自动添加 [熟肉] 前缀，长度限制 80 字。
    """
    config = load_config()
    api_key = config['deepseek']['api_key']
    base_url = config['deepseek']['base_url']
    model_name = config['deepseek'].get('model', 'deepseek-chat')

    if api_key == "YOUR_DEEPSEEK_API_KEY_HERE":
        return title, " ", []

    desc_text = ""
    if desc_path:
        try:
            with open(desc_path, 'r', encoding='utf-8') as f:
                desc_text = f.read()[:5000]
        except Exception:
            pass

    client = OpenAI(api_key=api_key, base_url=base_url)

    style_name = config.get('bilibili', {}).get('channel_styles', {}).get(
        uploader_id, 'default'
    )
    meta_prompt_base = config.get('prompts', {}).get(style_name, {}).get(
        'meta', config['prompts']['default']['meta']
    )

    sys_prompt = (
        f"{meta_prompt_base}\n\n"
        "你必须严格以合法的 JSON 格式返回结果，不能包含任何其他说明文字，格式如下：\n"
        '{"title": "生成的中文标题", "description": "生成的简介", "tags": ["标签1", "标签2"]}'
    )

    user_prompt = (
        f"原标题: {title}\n"
        f"原简介: {desc_text}\n"
        f"部分字幕: {' '.join(sample_subs[:15])}"
    )

    print("[*] 正在请求 AI 包装视频标题与简介...")
    try:
        response = client.chat.completions.create(
            model=model_name,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
        )

        res_text = response.choices[0].message.content.strip()
        meta_data = json.loads(res_text)

        raw_title = (
            meta_data.get("title", title)
            .replace("[中字]", "")
            .replace("[熟肉]", "")
            .strip()
        )

        if uploader_name:
            final_title = f"[熟肉][{uploader_name}]{raw_title}"
        else:
            final_title = f"[熟肉]{raw_title}"

        return final_title[:80], meta_data.get("description"), meta_data.get("tags", [])

    except Exception as e:
        print(f"[!] 生成AI元数据失败 ({e})，使用默认格式...")
        fallback_prefix = f"[熟肉][{uploader_name}]" if uploader_name else "[熟肉]"
        return f"{fallback_prefix}{title[:60]}", [], []
