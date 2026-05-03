# core/publisher.py
import subprocess
import time
from pathlib import Path
from core.collection import BiliCollectionManager
from utils.config_manager import load_config

BASE_DIR = Path(__file__).resolve().parent.parent
COOKIES_FILE = BASE_DIR / "configs" / "cookies.json"

def upload_to_bilibili(video_path, b_title, b_desc, b_tags, source_url="", uploader="", cover_path=""):
    config = load_config()
    bili_config = config.get('bilibili', {})
    
    print(f"\n[*] 准备上传至 Bilibili: {b_title}")
    
    if not COOKIES_FILE.exists() or COOKIES_FILE.stat().st_size < 10:
        print("[!] 警告：未找到有效的 configs/cookies.json。")
        print("[!] 无法上传，请在服务器执行 'biliup login'！")
        return False

    # 合并配置文件基础标签和 AI 生成的标签
    base_tags = bili_config.get('tags', ["搬运"])
    final_tags = ",".join(list(set(base_tags + b_tags))[:10]) 
    tid = str(bili_config.get('tid', 122))
    
    safe_title = b_title[:80]

    command = [
        "biliup", 
        "-u", str(COOKIES_FILE),
        "upload",
        str(video_path),
        "--title", safe_title,
        "--tid", tid,
        "--tag", final_tags,
        "--desc", b_desc,
        "--copyright", "2"
    ]
    
    if source_url:
        command.extend(["--source", source_url])

    if cover_path:
        command.extend(["--cover", str(cover_path)])
        print(f"[*] 已挂载视频封面...")

    try:
        # 注意加上 cwd 以确保它能读到 cookie
        result = subprocess.run(command, text=True, cwd=str(COOKIES_FILE.parent))
        if result.returncode == 0:
            print(f"[*] Bilibili 命令行上传成功!")
            
            # ================= 新增：自动加入合集逻辑 =================
            if uploader:
                try:
                    collections_map = bili_config.get('collections', {})
                    # 如果配置了映射则用映射名，否则默认使用 uploader 原名
                    target_season_name = collections_map.get(uploader, uploader)
                    
                    print(f"[*] 准备将视频加入合集: {target_season_name}")
                    manager = BiliCollectionManager()
                    
                    # 1. 获取合集及其分区 ID
                    seasons_data = manager.list_seasons()
                    target_section_id = None
                    for s in seasons_data.get('seasons', []):
                        if s['season']['title'] == target_season_name:
                            target_section_id = s['sections']['sections'][0]['id']
                            break
                            
                    if not target_section_id:
                        print(f"[!] 找不到名为 '{target_season_name}' 的合集，请在B站创作中心先手动创建该合集。")
                    else:
                        # 2. 获取刚上传的视频 aid 和 cid
                        time.sleep(3) # 给B站后台一点反应时间
                        aid = manager.get_recent_archive(safe_title)
                        if not aid:
                            print(f"[!] 加入合集失败：未能在最近稿件中找到该视频。")
                        else:
                            v_info = manager.get_video_info(aid)
                            cid = v_info['videos'][0]['cid']
                            
                            # 3. 提交至合集
                            manager.add_to_season(target_section_id, aid, cid, safe_title)
                            
                except Exception as e:
                    print(f"[!] 自动加入合集过程发生错误: {e}")
            # ==========================================================
            
            return True
        else:
            print(f"[!] Bilibili 上传失败，退出码: {result.returncode}")
            return False
    except FileNotFoundError:
        print("[!] 找不到 biliup 命令。请确保已运行: pip install biliup")
        return False
