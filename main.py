# main.py
import os
import shutil
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

    # 2. 遍历处理
    for video_path, srt_path, desc_path, uploader in downloads: 
        video_title = Path(video_path).stem
        print(f"\n{'='*40}")
        print(f">>> 开始处理视频: {video_title}")
        
        if uploader: # 打印一下提取到的频道名
            print(f"[*] 所属频道: {uploader}")

        if not srt_path:
            print("[!] 未找到字幕，跳过。")
            continue

        # 翻译字幕
        chinese_texts, english_texts = translate_subtitles(srt_path)
        if not chinese_texts:
            print("[!] 翻译失败，跳过。")
            continue

        # 【新增】让 AI 生成 B 站专用标题、简介和 Tag
        b_title, b_desc, b_tags = generate_bilibili_meta(video_title, desc_path, chinese_texts, uploader)

        # 生成 ASS 和压制
        ass_path = TEMP_DIR / f"{video_title}.ass"
        generate_ass(srt_path, chinese_texts, english_texts, ass_path)

        output_video_path = TEMP_DIR / f"{video_title}_zh_sub.mp4"
        success = hardcode_subtitles(video_path, ass_path, output_video_path)
        
        if success:
            upload_success = False
            # 判断是否开启上传
            if config['bilibili'].get('enable_upload', False):
                upload_success = upload_to_bilibili(output_video_path, b_title, b_desc, b_tags)
            else:
                print("[*] 配置文件设为不上传，将转入本地收藏。")
            
            # 【核心逻辑】空间管理判定
            if upload_success and config['bilibili'].get('delete_after_upload', True):
                # 成功上传且开启了清理，直接删除源文件和成品
                print("[*] 正在清理已上传的视频残留以释放服务器空间...")
                Path(video_path).unlink(missing_ok=True)
                Path(srt_path).unlink(missing_ok=True)
                Path(ass_path).unlink(missing_ok=True)
                if desc_path: Path(desc_path).unlink(missing_ok=True)
                Path(output_video_path).unlink(missing_ok=True)
                print("[*] 清理完成。")
            else:
                # 没上传，或者配置为不删除，则移动到本地完成库
                COMPLETED_DIR.mkdir(parents=True, exist_ok=True)
                final_path = COMPLETED_DIR / f"{b_title.replace('/', '_')}.mp4"
                shutil.move(str(output_video_path), str(final_path))
                print(f"[*] 视频已保存至本地: {final_path}")
            
    print("\n========================================")
    print("--- 本轮处理任务结束 ---")
    print("========================================\n")

if __name__ == "__main__":
    main()
