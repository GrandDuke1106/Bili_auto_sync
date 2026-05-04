# main.py
import os
import shutil
import json
import re
from pathlib import Path
from utils.config_manager import load_config
from utils.logger import setup_logger
from core.downloader import download_video
from core.translator import translate_subtitles, generate_bilibili_meta
from core.composer import generate_ass, hardcode_subtitles
from core.publisher import upload_to_bilibili

BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "data" / "temp_workspace"
COMPLETED_DIR = BASE_DIR / "data" / "completed_videos"

def sanitize_filename(name):
    """清理文件名中的非法字符，防止因特殊符号导致中文名保存失败"""
    return re.sub(r'[\\/*?:"<>|]', "", name)

def remove_from_archive(video_title):
    """如果处理彻底失败，从 yt-dlp 的 archive 中删除记录，以便下次重新下载"""
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
            print(f"[*] 连续重试失败，已将视频 [{video_id}] 从 archive 记录中移除，下次触发时将重新下载。")
    except Exception as e:
        print(f"[!] 清除 archive 记录时发生错误: {e}")

def main():
    setup_logger()
    print("========================================")
    print("--- Bilibili Auto Sync 生产线启动 ---")
    
    config = load_config()
    if config['deepseek']['api_key'] == "YOUR_DEEPSEEK_API_KEY_HERE":
        print("[!] 警告: 未配置 API Key。")
        return

    # 1. 获取视频 (受 max_downloads_per_run 限制)
    downloads = download_video()
    if not downloads:
        return

    # 读取清理策略配置 (默认只删临时文件，保留中字成片)
    bili_config = config.get('bilibili', {})
    delete_temp = bili_config.get('delete_temp_files', True) 
    delete_final = bili_config.get('delete_final_video', False) 

    # 2. 遍历处理
    for video_path, srt_path, desc_path, uploader_id, uploader_name, source_url, cover_path in downloads: 
        video_title = Path(video_path).stem
        print(f"\n{'='*40}")
        print(f">>> 开始处理视频: {video_title}")
        
        if uploader_id: print(f"[*] 所属频道id: {uploader_id}")
        if uploader_name: print(f"[*] 所属频道: {uploader_name}")

        if not srt_path:
            print("[!] 未找到字幕，跳过。")
            continue

        max_retries = 3
        process_success = False
        upload_success = False
        b_title = video_title # 给一个默认标题保底
        
        output_video_path = TEMP_DIR / f"{video_title}_zh_sub.mp4"
        ass_path = TEMP_DIR / f"{video_title}.ass"

        # === AI翻译与压制：重试循环 ===
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    print(f"\n[*] 第 {attempt + 1} 次尝试处理...")

                # 翻译字幕
                chinese_texts, english_texts = translate_subtitles(srt_path, uploader_id)
                if not chinese_texts:
                    print("[!] 字幕翻译失败，准备重试...")
                    continue

                # 让 AI 生成 B 站专用标题、简介和 Tag
                b_title, b_desc, b_tags = generate_bilibili_meta(video_title, desc_path, chinese_texts, uploader_name, uploader_id)

                # 生成 ASS 和压制
                generate_ass(srt_path, chinese_texts, english_texts, ass_path)
                process_success = hardcode_subtitles(video_path, ass_path, output_video_path)
                
                if process_success:
                    break # 压制成功，跳出重试循环
                else:
                    print("[!] 压制步骤失败，准备重试...")
                    
            except Exception as e:
                print(f"[!] 处理过程中发生异常: {e}")

        # === 循环结束后的分发逻辑 ===
        if process_success:
            if config['bilibili'].get('enable_upload', False):
                upload_success = upload_to_bilibili(output_video_path, b_title, b_desc, b_tags, source_url, uploader_id, cover_path)
                if not upload_success:
                    print(f"\n[!] 视频 {video_title} 上传失败。")
                    remove_from_archive(video_title)
            else:
                print("[*] 配置文件设为不开启上传，直接转入本地归档逻辑。")
        else:
            print(f"\n[!] 视频 {video_title} 经过 {max_retries} 次重试依然无法完成翻译或压制。")
            remove_from_archive(video_title)

        # === 文件清理与本地归档 (完全独立于是否开启上传) ===
        
        # 1. 处理带有硬字幕的最终成片
        if Path(output_video_path).exists():
            if delete_final:
                print("[*] 策略 [删除最终成片]: 正在清理压制产物...")
                Path(output_video_path).unlink(missing_ok=True)
            else:
                COMPLETED_DIR.mkdir(parents=True, exist_ok=True)
                # 使用安全函数保证中文名顺利保存
                safe_chinese_title = sanitize_filename(b_title)
                final_path = COMPLETED_DIR / f"{safe_chinese_title}.mp4"
                shutil.move(str(output_video_path), str(final_path))
                print(f"[*] 最终成片已保存至本地: {final_path}")
        
        # 2. 处理原视频、字幕等临时材料
        if delete_temp:
            print("[*] 策略 [删除临时材料]: 正在清理源文件残留...")
            Path(video_path).unlink(missing_ok=True)
            Path(srt_path).unlink(missing_ok=True)
            Path(ass_path).unlink(missing_ok=True)
            if desc_path: Path(desc_path).unlink(missing_ok=True)
            if cover_path: Path(cover_path).unlink(missing_ok=True)
            info_file = TEMP_DIR / f"{video_title}.info.json"
            info_file.unlink(missing_ok=True)
            print("[*] 临时文件清理完成。")
        else:
            print("[*] 策略 [保留临时材料]: 源文件依然存放在 temp_workspace 目录中。")

    print("\n========================================")
    print("--- 本轮处理任务结束 ---")
    print("========================================\n")

if __name__ == "__main__":
    main()
