# main.py
import os
from pathlib import Path
from utils.config_manager import load_config
from core.downloader import download_video
from core.translator import translate_subtitles
from core.composer import generate_ass, hardcode_subtitles

BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "data" / "temp_workspace"

def main():
    print("--- Bilibili Auto Sync 启动 ---")
    config = load_config()
    
    if config['deepseek']['api_key'] == "YOUR_DEEPSEEK_API_KEY_HERE":
        print("[!] 错误: API Key 未配置，程序终止。")
        return

    # 第一步：下载视频和英文字幕
    video_path, srt_path = download_video()
    
    if not video_path:
        print("[*] 流程结束。")
        return
        
    if not srt_path:
        print("[!] 只有视频没有字幕，暂不支持无字幕翻译，流程结束。")
        return

    # 第二步：翻译字幕
    chinese_texts, english_texts = translate_subtitles(srt_path)
    
    if not chinese_texts:
        print("[!] 翻译失败或字幕为空，流程结束。")
        return

    # 第三步：生成双语 ASS 字幕
    ass_path = TEMP_DIR / "bilingual.ass"
    generate_ass(srt_path, chinese_texts, english_texts, ass_path)

    # 第四步：压制视频
    # 在原视频名后加上 _zh_sub
    output_video_path = TEMP_DIR / f"{Path(video_path).stem}_zh_sub.mp4"
    success = hardcode_subtitles(video_path, ass_path, output_video_path)

    if success:
        print("\n🎉 第一阶段任务完成！请检查 data/temp_workspace/ 目录下的成品视频。")

if __name__ == "__main__":
    main()
