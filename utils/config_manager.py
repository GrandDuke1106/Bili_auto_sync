# utils/config_manager.py
import os
import json
import yaml
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "configs"
CONFIG_FILE = CONFIG_DIR / "config.yaml"
COOKIES_FILE = CONFIG_DIR / "cookies.json"

DEFAULT_CONFIG = {
    "deepseek": {
        "api_key": "YOUR_DEEPSEEK_API_KEY_HERE",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-flash"
    },
    "youtube": {
        "target_urls": [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        ],
        "channels": [
            "https://www.youtube.com/@ExampleChannel/videos"
        ],
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "download_archive": "data/archive.txt",
        "max_downloads_per_run": 3,
        "proxy": "http://127.0.0.1:7890"
    },
    "bilibili": {
        "enable_upload": False,
        "delete_temp_files": True,
        "delete_final_video": False,
        "tid": 122,
        "tags": ["翻译", "YouTube"],
        "collections": {
            "UCuAXFkgsw1L7xaCfnd5JJOw": "示例合集1",
            "UCexample": "示例合集2"
        },
        "channel_styles": {
            "UCuAXFkgsw1L7xaCfnd5JJOw": "default",
            "UCexample": "literature_art"
        }
    },
    "prompts": {
        "default": {
            "subtitles": "你是一个专业的字幕翻译员。请准确、流畅地将以下英文翻译为中文，保持口语化和自然。",
            "meta": "你是一个B站内容运营。请忠实翻译原标题和原简介。标题请直接平直翻译；简介请清晰、完整地翻译原文的所有有效内容，绝对不要做额外的概括和总结。请自动识别并剔除原文中的广告、赞助或与视频内容无关的推广链接；最后根据内容生成3个相关Tag。"
        },
        "pure_math": {
            "subtitles": "你是一位拥有深厚数学背景的翻译专家。请准确翻译以下英文。要求：严谨对待每一个定理、公式和逻辑推导过程，确保专业术语（如拓扑学、代数几何、微积分等）完全符合中文高等教育学术规范，宁可直译也不要意译导致逻辑歧义。",
            "meta": "你是一个B站硬核数学频道的运营。请忠实翻译原标题和原简介。标题翻译要直击数学核心概念，严谨且拒绝标题党；简介请原原本本地翻译原文，保留原文所有的数学推导或前置知识描述，绝对不要自行总结缩写，请剔除原文中的广告和商业赞助信息；最后生成3个精准的学术标签(Tags)。"
        },
        "popular_science": {
            "subtitles": "你是一位擅长把复杂科学原理解释得通俗易懂的科普作家。请翻译以下英文。要求：在保证科学原理绝对准确的前提下，语言尽量生动、有趣，遇到晦涩的物理/天文概念时，翻译得更有利于大众理解。",
            "meta": "你是一个B站硬核科普频道的运营。请忠实翻译原标题和原简介。标题请直接翻译，语言上适当保留能激发大众好奇心和探索欲的科普感，拒绝标题党；简介请完整且生动地翻译原文，不要擅自概括，请自动忽略并剔除原文中的商单广告内容；最后生成3个高度相关的科普或科学标签(Tags)。"
        },
        "tea_culture": {
            "subtitles": "你是一位精通中国传统文化的茶道与美学专家。请将以下英文翻译为优美的中文。要求：遣词造句要古朴、宁静，富有诗意，精准传达出茶的色、香、味，以及品茶时的禅意和悠然的心境。",
            "meta": "你是一个B站茶文化与慢生活频道的运营。请忠实翻译原标题和原简介。标题翻译在忠于原意的基础上，尽量遣词古朴、意境悠远；简介请完整翻译全文，语气要如散文般娓娓道来，传达出茶的韵味与宁静氛围，切勿自行删减总结，同时剔除原文中的商品推销和广告；最后生成3个具有文化底蕴的标签(Tags)。"
        },
        "literature_art": {
            "subtitles": "你是一位精通中西方文学的散文家和评论家。请将以下英文翻译为中文。要求：文笔必须优美、典雅，注意保留原作者的修辞手法和隐喻，多用贴切的成语和四字词语，翻译出文学的诗意与厚重感，切忌干瘪的机翻味。",
            "meta": "你是一个B站文艺频道的运营。请忠实翻译原标题和原简介。标题翻译需保留原作的修辞与诗意；简介请全文翻译，语气要像是一篇典雅的文艺评论，保留文学厚重感，不要擅自缩写或提炼，并剔除原文中的商业广告部分；最后生成3个文学、艺术或哲学相关的标签(Tags)。"
        },
        "tech_hardware": {
            "subtitles": "你是一位资深的系统工程师和PC硬件发烧友。请准确翻译以下英文。要求：确保所有关于Linux系统管理、开源软件生态、PC硬件超频（如CPU电压、内存时序）的术语翻译绝对准确，保持极客硬核、干练的技术风口吻。",
            "meta": "你是一个B站硬核科技与硬件频道的运营。请精准翻译原标题和原简介。标题翻译要干练、硬核，体现极客精神；简介请完整翻译原文中的技术方案、折腾经验或超频测试结论等所有细节，务必做到术语精准，不要自行概括，自动剔除原文中的恰饭推广与广告；最后生成3个极客技术标签(Tags)。"
        },
        "mechanical_engineering": {
            "subtitles": "你是一位拥有丰富经验的机械设计工程师。请翻译以下英文。要求：严格遵守工业标准词汇，准确翻译CAD建模、非线性有限元分析（FEA）、疲劳测试、气动系统等工程术语，语言要求严谨、务实。",
            "meta": "你是一个B站硬核工业与机械频道的运营。请精准翻译原标题和原简介。标题要求术语严谨，精准对译专有名词；简介需原原本本地翻译原文，确保机械设计、力学测试参数等信息的绝对准确和完整，绝不要做任何省略或总结，剔除原文的广告赞助部分；最后生成3个工程/工业标签(Tags)。"
        },
        "aviation_sim": {
            "subtitles": "你是一位资深的真实飞行员兼硬核模拟飞行机长。请准确翻译以下英文。要求：熟练且极其准确地使用航空术语、ATC陆空对话规范以及驾驶舱程序词汇（如IFR、进近、航图阅读、FMC操作），绝对符合民航标准用语。",
            "meta": "你是一个B站硬核航空与模拟飞行频道的运营。请精准翻译原标题和原简介。标题翻译必须保留确切的机型或飞行阶段等关键信息；简介请完整翻译原文，确保气象条件、操作流程或评测细节等航理知识准确无误流失，不要自行简述，忽略并剔除原文中的外设推广等广告内容；最后生成3个硬核航空相关的标签(Tags)。"
        },
        "ACG_3d": {
            "subtitles": "你是一位专业的3D角色建模师和技术动画师。请翻译以下英文。要求：精准翻译关于Blender/maya/3dmax等等软件的建模、面部拓扑结构、人体解剖学布线、骨骼绑定以及VTuber动捕的技术术语，语言风格完全契合CG艺术圈的交流习惯。",
            "meta": "你是一个B站3D美术与VUP/ACG技术频道的运营。请精准翻译原标题和原简介。标题翻译要切中建模拓扑或角色表现的行业术语；简介请逐字逐句翻译原文中的拓扑思路、材质渲染或骨骼绑定技巧等干货，绝不可自行删减或概述，但需剔除原文中的模型售卖等广告推广部分；最后生成3个CG建模或V圈相关的标签(Tags)。"
        }
    },
    "subtitle": {
        "fonts_dir": "configs/fonts",
        "zh_font_name": "Noto Sans SC", 
        "en_font_name": "Fira Code"
    }
}

def init_configs():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(DEFAULT_CONFIG, f, allow_unicode=True, sort_keys=False)
        print(f"[*] 生成默认配置: {CONFIG_FILE}，请填入 API Key")
    if not COOKIES_FILE.exists():
        with open(COOKIES_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
        print(f"[*] 生成空的 cookies 文件: {COOKIES_FILE}")

def load_config():
    init_configs()
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
