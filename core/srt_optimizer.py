# core/srt_optimizer.py — SRT 字幕智能优化：句子分割 + 时间轴重组
import re

import pysrt


# ==========================================================================
# NLTK 惰性初始化（用于句子分割）
# ==========================================================================

_nltk_ready = False


def _ensure_nltk_punkt():
    """确保 NLTK punkt 分词器数据可用，首次调用时自动下载。"""
    global _nltk_ready
    if _nltk_ready:
        return
    try:
        import nltk
        try:
            nltk.data.find('tokenizers/punkt_tab')
        except LookupError:
            try:
                nltk.download('punkt_tab', quiet=True)
            except Exception:
                pass
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt', quiet=True)
        _nltk_ready = True
    except Exception:
        pass


# ==========================================================================
# 内部辅助函数
# ==========================================================================


def _build_time_map(full_text, merged_items):
    """为 full_text 的每个字符位置建立到毫秒时间戳的线性映射。

    在条目时间跨度内对字符做线性插值，确保切分后的子句能分配到合理的时间。
    """
    time_map = [0] * len(full_text)
    text_pos = 0

    for item in merged_items:
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
                time_map[text_pos] = item['start'] + int(
                    i / (item_chars - 1) * item_dur
                )
            text_pos += 1

    return time_map


def _rebalance_sentence_splits(sentences, max_len=65):
    """修正不良句子分割：将以连接词结尾或以残片开头的相邻句子合并。

    典型坏分割案例：
      "so please keep" | "that in mind for the video"
      → "so please keep that in mind for the video"
    """
    if len(sentences) <= 1:
        return sentences

    bad_endings = {
        'this', 'that', 'these', 'those', 'so', 'and', 'but',
        'or', 'nor', 'yet', 'for', 'please', 'although',
        'though', 'because', 'if', 'when', 'where', 'which', 'who',
        'what', 'how', 'why', 'while', 'whereas', 'unless', 'until',
        'however', 'therefore', 'thus', 'hence', 'then', 'also',
        'just', 'still', 'even', 'only', 'maybe', 'perhaps',
        'keep', 'make', 'let', 'get', 'put',
    }
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
            if cur_last in bad_endings:
                should_merge = True
            elif next_first in bad_beginnings:
                should_merge = True
            elif len(current) < 15:
                should_merge = True
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
    """将超长英文句子在从句连词或逗号处递归软分割。

    优先级：
      100 — 逗号 + 从句连词（", and", ", but", ", because" 等）
       80 — 独立从句引导词（"so", "and", "which" 等，前后均需 ≥15 字符）
       50 — 普通逗号
       40 — 分号
       20 — 空格（排除 ≤3 字符的紧耦合短词）
    分割后通过 _rebalance_sentence_splits 修正递归产生的坏断点。
    """
    if len(sentence) <= max_len:
        return [sentence]

    target = len(sentence) // 2
    search_radius = max(target // 2, 20)
    search_start = max(0, target - search_radius)
    search_end = min(len(sentence), target + search_radius)

    candidates = []

    # 优先级 100: 逗号 + 从句连词
    clause_re = re.compile(
        r',\s+(?:and|but|because|which|who|so|or|yet|nor'
        r'|while|although|however|therefore|if|when|where'
        r'|whereas|unless|until|though|thus|hence)\s+',
        re.IGNORECASE,
    )
    for m in clause_re.finditer(sentence):
        pos = m.start() + 1
        if search_start <= pos <= search_end:
            candidates.append((pos, 100))

    # 优先级 80: 独立从句引导词（无逗号时）
    standalone_re = re.compile(
        r'\s+(so|and|but|because|if|although|which|who|where'
        r'|when|however|therefore|thus|hence|unless|until'
        r'|though|while|whereas|yet|or|nor)\s+',
        re.IGNORECASE,
    )
    if not candidates:
        for m in standalone_re.finditer(sentence):
            pos = m.start() + 1
            if search_start <= pos <= search_end:
                left_len = pos
                right_len = len(sentence) - (m.end() - 1)
                if left_len >= 15 and right_len >= 15:
                    candidates.append((pos, 80))

    # 优先级 50: 普通逗号
    if not candidates:
        for m in re.finditer(r',\s+', sentence):
            pos = m.start() + 1
            if search_start <= pos <= search_end:
                candidates.append((pos, 50))

    # 优先级 40: 分号
    if not candidates:
        for m in re.finditer(r';\s+', sentence):
            pos = m.start() + 1
            if search_start <= pos <= search_end:
                candidates.append((pos, 40))

    # 优先级 20: 空格（排除 ≤3 字符的紧耦合短词）
    if not candidates:
        SHORT_WORD_MAX = 3
        MIN_HALF = 15
        for m in re.finditer(r'\s+', sentence):
            pos = m.start()
            if search_start <= pos <= search_end:
                next_word_m = re.search(r'\S+', sentence[pos + 1:])
                next_word_len = len(next_word_m.group()) if next_word_m else 99
                if next_word_len <= SHORT_WORD_MAX:
                    continue
                prev_text = sentence[:pos]
                prev_word_m = re.search(r'(\S+)\s*$', prev_text)
                prev_word_len = len(prev_word_m.group(1)) if prev_word_m else 99
                if prev_word_len <= SHORT_WORD_MAX:
                    continue
                if pos >= MIN_HALF and len(sentence) - pos - 1 >= MIN_HALF:
                    candidates.append((pos, 20))

    if not candidates:
        return [sentence]

    candidates.sort(key=lambda x: (abs(x[0] - target), -x[1]))
    split_pos = candidates[0][0]

    left = sentence[:split_pos].strip().rstrip(',')
    right = sentence[split_pos:].strip()

    if not left or not right:
        return [sentence]

    result = []
    result.extend(_split_long_english_sentence(left, max_len))
    result.extend(_split_long_english_sentence(right, max_len))
    result = _rebalance_sentence_splits(result, max_len)
    return result


def _smart_sentence_tokenize(full_text):
    """使用 NLTK 进行句子分割；若不可用则回退到正则模式。"""
    try:
        import nltk
        _ensure_nltk_punkt()
        if _nltk_ready:
            return nltk.sent_tokenize(full_text)
    except Exception:
        pass
    return re.split(r'(?<=[.?!])\s+(?=[A-Z"])', full_text)


# ==========================================================================
# 公开 API
# ==========================================================================


def optimize_srt(srt_path):
    """对 SRT 字幕进行智能优化：NLTK 句子分割 + 从句软断句 + 等比时间轴重组。

    关键改进：
    1. 检测相邻字幕条目之间的时间间隔（gap），超过 2 秒则强制断段，
       防止说话人停顿后不同段落被错误合并。
    2. 在每段内使用 NLTK 做句子分割，超长句子进一步从句级软断句。
    3. 利用字符→毫秒线性映射为新句子分配合理时间轴。
    4. 消除时间轴微小重叠，合并过短字幕（<800ms）避免闪屏。
    """
    GAP_THRESHOLD_MS = 2000

    if not srt_path:
        return
    subs = pysrt.open(srt_path)
    if not subs:
        return

    # 第一步：收集所有碎片并清理噪声标签
    merged_items = []
    for sub in subs:
        clean_text = re.sub(r'\s+', ' ', sub.text.replace('\n', ' ')).strip()
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

    # 按时间间隔切分为独立段落
    segments = []
    current_segment = [merged_items[0]]

    for i in range(1, len(merged_items)):
        gap = merged_items[i]['start'] - merged_items[i - 1]['end']
        if gap > GAP_THRESHOLD_MS:
            segments.append(current_segment)
            current_segment = [merged_items[i]]
        else:
            current_segment.append(merged_items[i])
    segments.append(current_segment)

    # 逐段处理
    optimized_subs = pysrt.SubRipFile()

    for seg_items in segments:
        seg_text = ' '.join(item['text'] for item in seg_items)
        if not seg_text.strip():
            continue

        time_map = _build_time_map(seg_text, seg_items)
        text_len = len(seg_text)
        if text_len == 0:
            continue

        raw_sentences = _smart_sentence_tokenize(seg_text)

        all_sentences = []
        for sentence in raw_sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            if len(sentence) <= 60:
                all_sentences.append(sentence)
            else:
                all_sentences.extend(_split_long_english_sentence(sentence))

        all_sentences = _rebalance_sentence_splits(all_sentences, max_len=65)

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

    # 消除时间轴微小重叠
    for i in range(len(optimized_subs) - 1):
        if optimized_subs[i].end > optimized_subs[i + 1].start:
            mid_time = (
                optimized_subs[i].end.ordinal + optimized_subs[i + 1].start.ordinal
            ) // 2
            optimized_subs[i].end = pysrt.SubRipTime(milliseconds=mid_time)
            optimized_subs[i + 1].start = pysrt.SubRipTime(milliseconds=mid_time)

    # 消除过短字幕（<800ms），合并到相邻条目
    MIN_DURATION_MS = 800
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
            next_sub = optimized_subs[i + 1]
            sub.text = sub.text.strip() + " " + next_sub.text.strip()
            sub.end = next_sub.end
            merged_subs.append(sub)
            skip_next = True
        else:
            sub.end = pysrt.SubRipTime(milliseconds=sub.start.ordinal + MIN_DURATION_MS)
            merged_subs.append(sub)

    final_subs = pysrt.SubRipFile()
    for i, sub in enumerate(merged_subs):
        sub.index = i + 1
        final_subs.append(sub)

    final_subs.save(srt_path, encoding='utf-8')
