# main.py
import os
import shutil
import json
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

    downloads = download_video()
    if not downloads:
        return

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
        upload_success = False

        # === 重试循环机制 ===
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    print(f"\n[*] 第 {attempt + 1} 次尝试处理/上传...")

                chinese_texts, english_texts = translate_subtitles(srt_path, uploader_id)
                if not chinese_texts:
                    print("[!] 字幕翻译失败，准备重试...")
                    continue

                b_title, b_desc, b_tags = generate_bilibili_meta(video_title, desc_path, chinese_texts, uploader_name, uploader_id)
                ass_path = TEMP_DIR / f"{video_title}.ass"
                generate_ass(srt_path, chinese_texts, english_texts, ass_path)

                output_video_path = TEMP_DIR / f"{video_title}_zh_sub.mp4"
                success = hardcode_subtitles(video_path, ass_path, output_video_path)
                
                if success:
                    if config['bilibili'].get('enable_upload', False):
                        upload_success = upload_to_bilibili(output_video_path, b_title, b_desc, b_tags, source_url, uploader_id, cover_path)
                    else:
                        print("[*] 配置文件设为不上传，将转入本地收藏逻辑。")
                        upload_success = True

                    if upload_success:
                        break  # 如果最终成功，跳出重试循环
                    else:
                        print("[!] 上传步骤失败，准备重试...")
                else:
                    print("[!] 压制步骤失败，准备重试...")

            except Exception as e:
                print(f"[!] 处理过程中发生异常: {e}")
        
        # === 失败惩罚机制 ===
        if not upload_success:
            print(f"\n[!] 视频 {video_title} 经过 {max_retries} 次重试依然彻底失败。")
            remove_from_archive(video_title)

        # === 绝对的物理清理逻辑 ===
        if config['bilibili'].get('delete_after_upload', True):
            print("[*] 正在执行彻底清理，释放服务器存储空间...")
            Path(video_path).unlink(missing_ok=True)
            Path(srt_path).unlink(missing_ok=True)
            Path(ass_path).unlink(missing_ok=True)
            if desc_path: Path(desc_path).unlink(missing_ok=True)
            if cover_path: Path(cover_path).unlink(missing_ok=True)
            
            # 不论成败，干掉最终压制好的视频和信息流
            Path(output_video_path).unlink(missing_ok=True)
            info_file = TEMP_DIR / f"{video_title}.info.json"
            info_file.unlink(missing_ok=True)
            print("[*] 清理完成。")
            
        elif not upload_success:
            # 只有在配置了“不删除”且“失败/没开启上传”的情况下，才扔进 complete 文件夹以备查验
            COMPLETED_DIR.mkdir(parents=True, exist_ok=True)
            final_path = COMPLETED_DIR / f"{b_title.replace('/', '_')}.mp4"
            if Path(output_video_path).exists():
                shutil.move(str(output_video_path), str(final_path))
                print(f"[*] 视频已保存至本地: {final_path}")
            
    print("\n========================================")
    print("--- 本轮处理任务结束 ---")
    print("========================================\n")

if __name__ == "__main__":
    main()
