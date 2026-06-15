# core/translator.py
import pysrt
import re
import json
from openai import OpenAI
from utils.config_manager import load_config

def chunk_list(lst, n):
    for i in range(0, len(lst), n): yield lst[i:i + n]

# --- NLTK 惰性初始化 ---
_nltk_ready = False

def _ensure_nltk_punkt():
    """确保 NLTK punkt 分词器数据可用（惰性下载）"""
    global _nltk_ready
    if _nltk_ready:
        return
    try:
        import nltk
        # 优先尝试新版 punkt_tab (NLTK >= 3.9)
        try:
            nltk.data.find('tokenizers/punkt_tab')
        except LookupError:
            try:
                nltk.download('punkt_tab', quiet=True)
            except Exception:
                pass
        # 回退到经典 punkt
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt', quiet=True)
        _nltk_ready = True
    except Exception:
        pass  # 如果 NLTK 完全不可用，后续会回退到正则模式


def _build_time_map(full_text, merged_items):
    """为 full_text 的每个字符位置建立 → 毫秒时间戳的线性映射"""
    time_map = [0] * len(full_text)
    text_pos = 0

    for item in merged_items:
        # 处理条目之间的空格（不属于任何条目的文本）
        if text_pos > 0 and text_pos < len(full_text):
            time_map[text_pos] = item['start']
            text_pos += 1

        item_text = item['text']
        item_chars = len(item_text)
        item_dur = item['end'] - item['start']

        for i in range(item_chars):
            if text_pos >= len(full_text):
                break
            if item_chars <= 1:
                time_map[text_pos] = item['start']
            else:
                # 字符在条目时间跨度内线性插值
                time_map[text_pos] = item['start'] + int(
                    i / (item_chars - 1) * item_dur
                )
            text_pos += 1

    return time_map


def _rebalance_sentence_splits(sentences, max_len=65):
    """修正糟糕的分割：将结尾是连接词/开头是残片的块合并回一起。

    典型坏分割案例：
      "so please keep" | "that in mind for the video"
      → "so please keep that in mind for the video"

      "like that this" | "is a pre-release build"
      → "like that this is a pre-release build"
    """
    if len(sentences) <= 1:
        return sentences

    # 不应当作为句子结尾的短词（通常是连接词、代词开头等）
    bad_endings = {
        'this', 'that', 'these', 'those', 'so', 'and', 'but',
        'or', 'nor', 'yet', 'for', 'please', 'although',
        'though', 'because', 'if', 'when', 'where', 'which', 'who',
        'what', 'how', 'why', 'while', 'whereas', 'unless', 'until',
        'however', 'therefore', 'thus', 'hence', 'then', 'also',
        'just', 'still', 'even', 'only', 'maybe', 'perhaps',
        'keep', 'make', 'let', 'get', 'put',
    }
    # 不应当作为句子开头的极短残片（助动词、be 动词等）
    bad_beginnings = {
        'is', 'are', 'was', 'were', 'am', 'be', 'been',
        'has', 'have', 'had', 'do', 'does', 'did',
        'can', 'could', 'will', 'would', 'shall', 'should',
        'may', 'might', 'must', 'it', 'them', 'us', 'me',
        'him', 'her', 'to', 'of', 'in', 'on', 'at', 'by',
    }

    result = []
    i = 0
    while i < len(sentences):
        current = sentences[i]
        merged = False

        if i + 1 < len(sentences):
            next_sent = sentences[i + 1]
            cur_words = current.split()
            next_words = next_sent.split()

            cur_last = cur_words[-1].lower().rstrip(',.;!?') if cur_words else ''
            next_first = next_words[0].lower().rstrip(',.;!?') if next_words else ''

            should_merge = False

            # Case 1: 当前句子以连接词/代词结尾 → 合并
            if cur_last in bad_endings:
                should_merge = True
            # Case 2: 下一句以残片开头 → 合并
            elif next_first in bad_beginnings:
                should_merge = True
            # Case 3: 当前句子极短（孤儿碎片）→ 合并
            elif len(current) < 15:
                should_merge = True
            # Case 4: 下一句极短 → 合并
            elif len(next_sent) < 10:
                should_merge = True

            if should_merge and len(current) + len(next_sent) + 1 <= max_len:
                result.append(current + ' ' + next_sent)
                i += 2
                merged = True

        if not merged:
            result.append(current)
            i += 1

    return result


def _split_long_english_sentence(sentence, max_len=60):
    """按从句连词、逗号或语义边界对超长英文句子进行软分割（递归），
    保证不在单词中间切断，并通过后处理修正不良分割。
    
    max_len=60 确保英文能在 ASS 字幕中单行显示（Fira Code 12px ≈ 78 chars/行）"""
    if len(sentence) <= max_len:
        return [sentence]

    target = len(sentence) // 2
    search_radius = max(target // 2, 20)
    search_start = max(0, target - search_radius)
    search_end = min(len(sentence), target + search_radius)

    candidates = []  # (position, priority)

    # ── 优先级 100：逗号 + 从句连词 — ", and", ", but", ", because" 等 ──
    clause_re = re.compile(
        r',\s+(?:and|but|because|which|who|so|or|yet|nor'
        r'|while|although|however|therefore|if|when|where'
        r'|whereas|unless|until|though|thus|hence)\s+',
        re.IGNORECASE
    )
    for m in clause_re.finditer(sentence):
        pos = m.start() + 1  # 在逗号之后切开
        if search_start <= pos <= search_end:
            candidates.append((pos, 100))

    # ── 优先级 80：独立从句引导词（无需逗号）──
    # YouTube ASR 文本通常缺少标点，这些词经常标志新从句的开始
    # 限制：前后都需要 ≥12 个字符，防止把 "and" / "so" 在短语内部误切
    standalone_re = re.compile(
        r'\s+(so|and|but|because|if|although|which|who|where'
        r'|when|however|therefore|thus|hence|unless|until'
        r'|though|while|whereas|yet|or|nor)\s+',
        re.IGNORECASE
    )
    if not candidates:
        for m in standalone_re.finditer(sentence):
            pos = m.start() + 1  # 在连词之前切开
            if search_start <= pos <= search_end:
                left_len = pos
                right_len = len(sentence) - (m.end() - 1)
                # 两侧都要有足够内容，避免孤立短词
                if left_len >= 15 and right_len >= 15:
                    candidates.append((pos, 80))

    # ── 优先级 50：普通逗号 ──
    if not candidates:
        for m in re.finditer(r',\s+', sentence):
            pos = m.start() + 1
            if search_start <= pos <= search_end:
                candidates.append((pos, 50))

    # ── 优先级 40：分号 ──
    if not candidates:
        for m in re.finditer(r';\s+', sentence):
            pos = m.start() + 1
            if search_start <= pos <= search_end:
                candidates.append((pos, 40))

    # ── 优先级 20：空格（带智能约束，防止切断紧耦合短词）──
    if not candidates:
        # 极短词（≤3 字符）很可能与相邻词紧耦合，不应在其前/后切断
        SHORT_WORD_MAX = 3
        MIN_HALF = 15  # 每半句最少字符数
        for m in re.finditer(r'\s+', sentence):
            pos = m.start()
            if search_start <= pos <= search_end:
                # 检查下一词是否过短（如 "is", "a", "the", "it", "to" →
                # 切断后下一句变成 "is xxx" 很别扭）
                next_word_m = re.search(r'\S+', sentence[pos + 1:])
                next_word_len = len(next_word_m.group()) if next_word_m else 99
                if next_word_len <= SHORT_WORD_MAX:
                    continue

                # 检查上一词是否过短（切断后上一句以 "this"/"keep" 结尾）
                prev_text = sentence[:pos]
                prev_word_m = re.search(r'(\S+)\s*$', prev_text)
                prev_word_len = len(prev_word_m.group(1)) if prev_word_m else 99
                if prev_word_len <= SHORT_WORD_MAX:
                    continue

                if pos >= MIN_HALF and len(sentence) - pos - 1 >= MIN_HALF:
                    candidates.append((pos, 20))

    if not candidates:
        return [sentence]  # 无法分割，保持原样

    # 选择离 target 最近且优先级最高的位置
    candidates.sort(key=lambda x: (abs(x[0] - target), -x[1]))
    split_pos = candidates[0][0]

    left = sentence[:split_pos].strip().rstrip(',')
    right = sentence[split_pos:].strip()

    if not left or not right:
        return [sentence]

    # 递归分割（防止分割后的子句依然超长）
    result = []
    result.extend(_split_long_english_sentence(left, max_len))
    result.extend(_split_long_english_sentence(right, max_len))

    # ── 后处理：修正递归分割产生的不良断点 ──
    result = _rebalance_sentence_splits(result, max_len)
    return result


def _smart_sentence_tokenize(full_text):
    """使用 NLTK 进行句子分割；若 NLTK 不可用则回退到正则模式"""
    try:
        import nltk
        _ensure_nltk_punkt()
        if _nltk_ready:
            return nltk.sent_tokenize(full_text)
    except Exception:
        pass

    # 回退：正则句子分割（处理 .?! 后跟空格+大写字母 或 行尾）
    return re.split(r'(?<=[.?!])\s+(?=[A-Z"])', full_text)


def optimize_srt(srt_path):
    """使用 NLTK 句子分割 + 从句级软断句 + 等比时间轴重组
    
    关键改进：检测相邻碎片之间的时间间隔（gap），若超过阈值则强制断开，
    防止说话人长时间停顿后，不同段落的文字被错误合并到同一条字幕中。
    """
    GAP_THRESHOLD_MS = 2000  # 相邻条目间隔超过 2 秒视为独立段落

    if not srt_path:
        return
    subs = pysrt.open(srt_path)
    if not subs:
        return

    # ── 第一步：收集所有碎片并构建映射 ──
    merged_items = []
    for sub in subs:
        clean_text = re.sub(r'\s+', ' ', sub.text.replace('\n', ' ')).strip()
        # 清理 YouTube ASR 噪声标签（防御性，json3 转换时已做但旧 SRT 可能残留）
        clean_text = re.sub(r'\s*\[Music\]\s*', ' ', clean_text)
        clean_text = re.sub(r'\s*\[Applause\]\s*', ' ', clean_text)
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        if not clean_text:
            continue
        merged_items.append({
            'start': sub.start.ordinal,
            'end': sub.end.ordinal,
            'text': clean_text,
        })

    if not merged_items:
        return

    # ── 第一步半：按时间间隔切分为独立段落 ──
    # 关键：检测相邻条目间的大间隔（如说话人长时间停顿、音乐片段等），
    # 在间隔处强制断开，防止 9s 的 "so" 和 27s 的 "hello..." 被合并。
    segments = []       # 每段是一个 [items] 列表
    current_segment = [merged_items[0]]

    for i in range(1, len(merged_items)):
        gap = merged_items[i]['start'] - merged_items[i - 1]['end']
        if gap > GAP_THRESHOLD_MS:
            segments.append(current_segment)
            current_segment = [merged_items[i]]
        else:
            current_segment.append(merged_items[i])
    segments.append(current_segment)  # 最后一段

    # ── 第二步：逐段处理（每段独立做 NLTK 句子分割 + 时间重分配）──
    optimized_subs = pysrt.SubRipFile()

    for seg_items in segments:
        # 拼接段落文本
        seg_text = ' '.join(item['text'] for item in seg_items)
        if not seg_text.strip():
            continue

        # 建立段落内的 字符位置 → 时间(ms) 映射
        time_map = _build_time_map(seg_text, seg_items)
        text_len = len(seg_text)
        if text_len == 0:
            continue

        # NLTK 句子分割（仅在段落内部）
        raw_sentences = _smart_sentence_tokenize(seg_text)

        # ── 收集段落内所有句子（含超长句子的子分割）──
        all_sentences = []
        for sentence in raw_sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            if len(sentence) <= 60:
                all_sentences.append(sentence)
            else:
                all_sentences.extend(_split_long_english_sentence(sentence))

        # ── 段落级后处理：修正跨句子边界的不良分割 ──
        # （例如 NLTK 的 "this is..." → 子分割 "so please keep" | "that in mind"）
        all_sentences = _rebalance_sentence_splits(all_sentences, max_len=65)

        # ── 逐句分配时间轴 ──
        search_pos = 0
        for sentence in all_sentences:
            if not sentence.strip():
                continue

            pos = seg_text.find(sentence, search_pos)
            if pos == -1:
                continue
            sent_end = pos + len(sentence)
            search_pos = sent_end

            start_ms = time_map[min(pos, text_len - 1)]
            end_ms = time_map[min(sent_end - 1, text_len - 1)]
            if end_ms <= start_ms:
                end_ms = start_ms + 500

            new_sub = pysrt.SubRipItem(
                index=len(optimized_subs) + 1,
                start=pysrt.SubRipTime(milliseconds=start_ms),
                end=pysrt.SubRipTime(milliseconds=end_ms),
                text=sentence,
            )
            optimized_subs.append(new_sub)

    # ── 第三步：消除时间轴微小重叠 ──
    for i in range(len(optimized_subs) - 1):
        if optimized_subs[i].end > optimized_subs[i + 1].start:
            mid_time = (
                optimized_subs[i].end.ordinal + optimized_subs[i + 1].start.ordinal
            ) // 2
            optimized_subs[i].end = pysrt.SubRipTime(milliseconds=mid_time)
            optimized_subs[i + 1].start = pysrt.SubRipTime(milliseconds=mid_time)

    # ── 第四步：消除过短字幕（闪屏字幕），合并到相邻条目 ──
    MIN_DURATION_MS = 800  # 最短显示时长（毫秒）

    merged_subs = []
    skip_next = False

    for i in range(len(optimized_subs)):
        if skip_next:
            skip_next = False
            continue

        sub = optimized_subs[i]
        duration = sub.end.ordinal - sub.start.ordinal

        if duration >= MIN_DURATION_MS:
            merged_subs.append(sub)
        elif i + 1 < len(optimized_subs):
            # 过短：合并到下一条字幕
            next_sub = optimized_subs[i + 1]
            sub.text = sub.text.strip() + " " + next_sub.text.strip()
            sub.end = next_sub.end
            merged_subs.append(sub)
            skip_next = True
        else:
            # 最后一条过短：延长到至少 MIN_DURATION_MS
            sub.end = pysrt.SubRipTime(milliseconds=sub.start.ordinal + MIN_DURATION_MS)
            merged_subs.append(sub)

    # 重新编号并保存
    final_subs = pysrt.SubRipFile()
    for i, sub in enumerate(merged_subs):
        sub.index = i + 1
        final_subs.append(sub)

    final_subs.save(srt_path, encoding='utf-8')

def _build_numbered_prompt(chunk, start_idx):
    """将字幕块构建为编号格式的 prompt，编号从 start_idx+1 开始"""
    lines = []
    for j, text in enumerate(chunk):
        lines.append(f"[{j + 1}] {text}")
    return "\n".join(lines)


def _parse_numbered_response(response_text, expected_count):
    """从编号格式的 AI 响应中提取每条翻译，返回 (lines_list, is_valid)"""
    lines = []
    for j in range(1, expected_count + 1):
        # 匹配 [N] 开头的内容，直到下一个 [N] 或文本末尾
        pattern = rf'\[{j}\]\s*(.+?)(?=\[\d+\]|\Z)'
        match = re.search(pattern, response_text, re.DOTALL)
        if match:
            lines.append(match.group(1).strip())
        else:
            lines.append(None)  # 标记缺失
    return lines


def translate_subtitles(srt_path, uploader_id="", uploader_name=""):
    if not srt_path:
        return [], []
    optimize_srt(srt_path)
    config = load_config()
    api_key = config['deepseek']['api_key']
    base_url = config['deepseek']['base_url']
    model_name = config['deepseek'].get('model', 'deepseek-v4-flash')

    if api_key == "YOUR_DEEPSEEK_API_KEY_HERE":
        print("[!] 请配置 DeepSeek API Key!")
        return [], []

    style_name = config.get('bilibili', {}).get('channel_styles', {}).get(uploader_id, 'default')
    sys_prompt = config.get('prompts', {}).get(style_name, {}).get(
        'subtitles', config['prompts']['default']['subtitles']
    )

    proper_noun_instruction = _build_proper_noun_instruction(uploader_name, uploader_id, config)

    # ── 系统消息（编号格式指令）──
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

    # ── 上下文窗口：保留最近几轮对话以提供翻译连贯性 ──
    MAX_CONTEXT_TURNS = 3  # 保留最近 3 轮 Q&A

    for index, chunk in enumerate(chunks):
        chunk_size = len(chunk)
        source_text = _build_numbered_prompt(chunk, index * 20)

        prompt = (
            f"请将以下 {chunk_size} 条英文字幕逐条翻译为中文，"
            f"严格保持 [N] 编号格式：\n\n{source_text}"
        )

        # 构建带上下文的 messages
        messages = [{"role": "system", "content": system_message}]

        # 添加上下文历史（前几轮的 Q&A）
        context_start = max(0, index - MAX_CONTEXT_TURNS)
        for ctx_idx in range(context_start, index):
            if ctx_idx < len(chunks):
                ctx_chunk = chunks[ctx_idx]
                ctx_prompt = _build_numbered_prompt(ctx_chunk, ctx_idx * 20)
                messages.append({
                    "role": "user",
                    "content": f"请将以下 {len(ctx_chunk)} 条英文字幕逐条翻译为中文，严格保持 [N] 编号格式：\n\n{ctx_prompt}"
                })
                # 从已翻译结果中取对应部分
                ctx_start_line = ctx_idx * 20
                ctx_end_line = min(ctx_start_line + len(ctx_chunk), len(chinese_texts))
                ctx_translated = chinese_texts[ctx_start_line:ctx_end_line]
                if ctx_translated:
                    ctx_response = "\n".join(
                        f"[{j+1}] {t}" for j, t in enumerate(ctx_translated)
                    )
                    messages.append({"role": "assistant", "content": ctx_response})

        messages.append({"role": "user", "content": prompt})

        # ── 翻译 + 重试逻辑 ──
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

                # 解析编号格式
                parsed = _parse_numbered_response(raw_text, chunk_size)
                valid_count = sum(1 for x in parsed if x is not None)

                if valid_count == chunk_size:
                    translated_lines = parsed
                    break
                elif attempt < max_retries:
                    # 重试：强调缺失的编号
                    missing = [j+1 for j, x in enumerate(parsed) if x is None]
                    print(f"    [!] 第 {index+1} 块缺失编号 {missing}，第 {attempt+1} 次重试...")
                    retry_hint = (
                        f"你的上一次输出丢失了以下编号的翻译：{missing}。"
                        f"请重新输出完整的 {chunk_size} 条翻译，确保每条都有对应的 [N] 编号。\n\n{source_text}"
                    )
                    messages.append({"role": "user", "content": retry_hint})
                else:
                    # 最终回退：缺失的用英文原文填充（标为未翻译）
                    print(f"    [!] 第 {index+1} 块经 {max_retries} 次重试仍缺失 {missing}，使用原文填充")
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


def _build_proper_noun_instruction(uploader_name, uploader_id, config):
    """构建专有名词保留不翻译的指令，追加到系统提示词末尾"""
    proper_nouns = set()

    # 1. 频道名 / 上传者名（如 "320 sim pilot"，从 yt-dlp 元数据自动获取）
    if uploader_name and uploader_name.strip():
        proper_nouns.add(uploader_name.strip())

    # 2. 全局专用名词列表（translation.preserve_proper_nouns）
    custom_nouns = config.get('translation', {}).get('preserve_proper_nouns', [])
    if isinstance(custom_nouns, list):
        for noun in custom_nouns:
            if noun and str(noun).strip():
                proper_nouns.add(str(noun).strip())

    # 3. 按频道 ID 匹配的专用名词（translation.channel_preserve_nouns）
    channel_nouns = config.get('translation', {}).get('channel_preserve_nouns', {}).get(uploader_id, [])
    if isinstance(channel_nouns, list):
        for noun in channel_nouns:
            if noun and str(noun).strip():
                proper_nouns.add(str(noun).strip())

    if not proper_nouns:
        return ""

    nouns_list = "\n".join(f"  - {n}" for n in sorted(proper_nouns))
    return (
        f"\n\n【专有名词保留规则】以下专有名词/品牌名/频道名请保持原文不翻译，"
        f"直接原样保留在中文译文中：\n{nouns_list}"
    )


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
