# main.py — YouTube → Bilibili 自动化搬运管线入口
import os
import shutil
import json
import re
import argparse
import sys
from pathlib import Path

from utils.config_manager import load_config
from utils.logger import setup_logger
from core.downloader import (
    download_video, scan_downloaded_files, clean_temp_dir,
    convert_json3_subtitles, run_whisperx_on_videos,
)
from core.translator import translate_subtitles, generate_bilibili_meta
from core.composer import generate_ass, hardcode_subtitles
from core.publisher import upload_to_bilibili

BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "data" / "temp_workspace"
COMPLETED_DIR = BASE_DIR / "data" / "completed_videos"

STAGE_ORDER = {"download": 1, "translate": 2, "compose": 3}
VALID_STAGES = list(STAGE_ORDER.keys())


def sanitize_filename(name):
    """去除文件名中的非法字符（\\ / : * ? \" < > |）。"""
    return re.sub(r'[\\/*?:"<>|]', "", name)


def remove_from_archive(video_title):
    """从 yt-dlp 的 archive.txt 中移除指定视频记录，以便下次重新下载。"""
    info_file = TEMP_DIR / f"{video_title}.info.json"
    archive_path = BASE_DIR / "data" / "archive.txt"

    if not info_file.exists() or not archive_path.exists():
        return

    try:
        with open(info_file, 'r', encoding='utf-8') as f:
            info_data = json.load(f)
            video_id = info_data.get('id')

        if not video_id:
            return

        with open(archive_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        with open(archive_path, 'w', encoding='utf-8') as f:
            removed = False
            for line in lines:
                if video_id not in line:
                    f.write(line)
                else:
                    removed = True

        if removed:
            print(f"[*] 已将视频 [{video_id}] 从 archive 记录中移除，下次触发时将重新下载。")
    except Exception as e:
        print(f"[!] 清除 archive 记录时发生错误: {e}")


def save_pipeline_state(state_path, chinese_texts, english_texts, b_title, b_desc, b_tags):
    """将翻译阶段的结果序列化到 JSON，供后续 compose 阶段断点续传。"""
    state = {
        "chinese_texts": chinese_texts,
        "english_texts": english_texts,
        "b_title": b_title,
        "b_desc": b_desc,
        "b_tags": b_tags,
    }
    try:
        with open(state_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        print(f"[*] 管道状态已保存: {state_path.name}")
    except Exception as e:
        print(f"[!] 保存管道状态失败: {e}")


def load_pipeline_state(state_path):
    """从 JSON 加载翻译阶段结果，文件不存在或格式不完整时返回 None。"""
    if not state_path.exists():
        print(f"[!] 管道状态文件不存在: {state_path}")
        return None
    try:
        with open(state_path, 'r', encoding='utf-8') as f:
            state = json.load(f)
        required_keys = ["chinese_texts", "english_texts", "b_title", "b_desc", "b_tags"]
        if all(k in state for k in required_keys):
            print(f"[*] 已加载管道状态: {state_path.name}")
            return state
        else:
            print(f"[!] 管道状态文件不完整: {state_path}")
            return None
    except Exception as e:
        print(f"[!] 读取管道状态失败: {e}")
        return None


def parse_args():
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="Bili_auto_sync - YouTube → Bilibili 自动化搬运管线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py                          # 完整运行（默认从下载开始）
  python main.py --start-from translate   # 跳过下载，从 AI 翻译开始
  python main.py --start-from compose     # 跳过下载和翻译，直接压制字幕
        """.strip(),
    )
    parser.add_argument(
        '--start-from',
        choices=VALID_STAGES,
        default=None,
        help=f"指定起始阶段（默认读取 pipeline.start_from 配置，fallback 为 download）。"
             f"可选: {', '.join(VALID_STAGES)}",
    )
    return parser.parse_args()


def main():
    setup_logger()
    print("========================================")
    print("--- Bilibili Auto Sync 生产线启动 ---")

    args = parse_args()
    config = load_config()

    if config['deepseek']['api_key'] == "YOUR_DEEPSEEK_API_KEY_HERE":
        print("[!] 警告: 未配置 API Key。")
        return

    # 起始阶段优先级：CLI 参数 > 配置文件 > 默认 "download"
    cli_stage = args.start_from
    config_stage = config.get('pipeline', {}).get('start_from', 'download')
    start_from = cli_stage or config_stage

    if start_from not in VALID_STAGES:
        print(f"[!] 无效的起始阶段 '{start_from}'，回退为 'download'")
        start_from = 'download'

    print(f"[*] 管道起始阶段: {start_from}")
    print("========================================")

    # ================================================================
    # 阶段 1: 下载
    # ================================================================
    if start_from == 'download':
        print("\n>>> [阶段 1/3] 下载 YouTube 视频")
        clean_temp_dir()
        downloads = download_video()
    else:
        print(f"\n>>> [阶段 1/3] 跳过下载（start_from={start_from}），扫描已有文件...")
        # 兜底：残留 json3 字幕但缺少 srt 时先转换
        json3_files = list(TEMP_DIR.glob("*.json3"))
        srt_files = list(TEMP_DIR.glob("*.srt"))
        if json3_files and not srt_files:
            print("[*] 发现未转换的 json3 字幕，正在转换为 SRT...")
            convert_json3_subtitles()
        # 即使跳过下载，也可对已有视频运行 WhisperX
        run_whisperx_on_videos()
        downloads = scan_downloaded_files()
        if not downloads:
            print("[!] TEMP_DIR 中没有找到已下载的视频文件。")
            print("[!] 请先使用 --start-from download 运行完整下载流程。")
            return

    if not downloads:
        print("[*] 本轮没有新视频需要处理。")
        return

    bili_config = config.get('bilibili', {})
    delete_temp = bili_config.get('delete_temp_files', True)
    delete_final = bili_config.get('delete_final_video', False)

    # ================================================================
    # 遍历处理每个视频
    # ================================================================
    for video_path, srt_path, desc_path, uploader_id, uploader_name, source_url, cover_path in downloads:
        video_title = Path(video_path).stem
        print(f"\n{'='*40}")
        print(f">>> 开始处理视频: {video_title}")

        if uploader_id:
            print(f"[*] 所属频道id: {uploader_id}")
        if uploader_name:
            print(f"[*] 所属频道: {uploader_name}")

        if not srt_path:
            print("[!] 未找到字幕，跳过。")
            continue

        output_video_path = TEMP_DIR / f"{video_title}_zh_sub.mp4"
        ass_path = TEMP_DIR / f"{video_title}.ass"
        state_path = TEMP_DIR / f"{video_title}_pipeline_state.json"

        b_title = video_title
        b_desc = ""
        b_tags = []
        process_success = False

        # ============================================================
        # 阶段 2: AI 翻译
        # ============================================================
        if start_from in ('download', 'translate'):
            print(f"\n>>> [阶段 2/3] AI 翻译字幕与元数据")

            chinese_texts, english_texts = translate_subtitles(
                srt_path, uploader_id, uploader_name
            )
            if not chinese_texts:
                print(f"[!] 视频 {video_title} 字幕翻译失败，跳过。")
                continue

            b_title, b_desc, b_tags = generate_bilibili_meta(
                video_title, desc_path, chinese_texts, uploader_name, uploader_id
            )

            save_pipeline_state(
                state_path, chinese_texts, english_texts, b_title, b_desc, b_tags
            )

        elif start_from == 'compose':
            print(f"\n>>> [阶段 2/3] 跳过翻译（start_from=compose），加载已保存结果...")

            state = load_pipeline_state(state_path)
            if not state:
                print(f"[!] 视频 {video_title} 没有找到翻译结果。")
                print(f"[!] 请先运行 --start-from translate 完成翻译步骤。")
                continue

            chinese_texts = state['chinese_texts']
            english_texts = state['english_texts']
            b_title = state['b_title'] or video_title
            b_desc = state['b_desc']
            b_tags = state['b_tags']

        # ============================================================
        # 阶段 3: FFmpeg 压制
        # ============================================================
        print(f"\n>>> [阶段 3/3] FFmpeg 硬字幕压制")

        generate_ass(srt_path, chinese_texts, english_texts, ass_path)
        process_success = hardcode_subtitles(video_path, ass_path, output_video_path)

        # ============================================================
        # 阶段 4: 上传 B 站（可选）
        # ============================================================
        if process_success:
            if config['bilibili'].get('enable_upload', False):
                print(f"\n>>> [阶段 4/4] 上传至 Bilibili")
                upload_success = upload_to_bilibili(
                    output_video_path, b_title, b_desc, b_tags,
                    source_url, uploader_id, cover_path,
                )
                if not upload_success:
                    print(f"\n[!] 视频 {video_title} 上传失败。")
                    remove_from_archive(video_title)
            else:
                print("\n[*] 配置文件设为不开启上传，跳过。")
        else:
            print(f"\n[!] 视频 {video_title} FFmpeg 压制失败。")
            print(f"[*] 提示: 修复问题后可用 --start-from compose 直接从压制步骤重试。")

        # ============================================================
        # 文件清理与本地归档
        # ============================================================
        if Path(output_video_path).exists():
            if delete_final:
                print("[*] 策略 [删除最终成片]: 正在清理压制产物...")
                Path(output_video_path).unlink(missing_ok=True)
            else:
                COMPLETED_DIR.mkdir(parents=True, exist_ok=True)
                safe_chinese_title = sanitize_filename(b_title)
                final_path = COMPLETED_DIR / f"{safe_chinese_title}.mp4"
                shutil.move(str(output_video_path), str(final_path))
                print(f"[*] 最终成片已保存至本地: {final_path}")

        if delete_temp:
            print("[*] 策略 [删除临时材料]: 正在清理源文件残留...")
            for p in [video_path, srt_path, ass_path, desc_path, cover_path]:
                if p:
                    Path(p).unlink(missing_ok=True)
            info_file = TEMP_DIR / f"{video_title}.info.json"
            info_file.unlink(missing_ok=True)
            state_path.unlink(missing_ok=True)
            print("[*] 临时文件清理完成。")
        else:
            print("[*] 策略 [保留临时材料]: 源文件依然存放在 temp_workspace 目录中。")

    print("\n========================================")
    print("--- 本轮处理任务结束 ---")
    print("========================================\n")


if __name__ == "__main__":
    main()
