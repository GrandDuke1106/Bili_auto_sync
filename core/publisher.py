# core/publisher.py — B 站上传（biliup 封装）+ 自动合集归类
import subprocess
import time
from pathlib import Path

from core.collection import BiliCollectionManager
from utils.config_manager import load_config

BASE_DIR = Path(__file__).resolve().parent.parent
COOKIES_FILE = BASE_DIR / "configs" / "cookies.json"


def upload_to_bilibili(video_path, b_title, b_desc, b_tags,
                       source_url="", uploader="", cover_path=""):
    """使用 biliup 上传视频到 B 站，并按配置自动加入对应合集。

    Returns:
        bool: 上传成功返回 True，否则返回 False。
    """
    config = load_config()
    bili_config = config.get('bilibili', {})

    print(f"\n[*] 准备上传至 Bilibili: {b_title}")

    if not COOKIES_FILE.exists() or COOKIES_FILE.stat().st_size < 10:
        print("[!] 警告：未找到有效的 configs/cookies.json。")
        print("[!] 无法上传，请在服务器执行 'biliup login'！")
        return False

    # 合并配置文件基础标签和 AI 生成的标签，去重后取前 10 个
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
        "--copyright", "2",
    ]

    if source_url:
        command.extend(["--source", source_url])

    if cover_path:
        command.extend(["--cover", str(cover_path)])
        print("[*] 已挂载视频封面...")

    try:
        result = subprocess.run(
            command, text=True,
            cwd=str(COOKIES_FILE.parent),  # biliup 需要在此目录找到 cookie
        )
        if result.returncode == 0:
            print("[*] Bilibili 命令行上传成功!")

            # 自动加入合集
            if uploader:
                try:
                    _add_to_collection(uploader, safe_title, bili_config)
                except Exception as e:
                    print(f"[!] 自动加入合集过程发生错误: {e}")

            return True
        else:
            print(f"[!] Bilibili 上传失败，退出码: {result.returncode}")
            return False
    except FileNotFoundError:
        print("[!] 找不到 biliup 命令。请确保已运行: pip install biliup")
        return False


def _add_to_collection(uploader, safe_title, bili_config):
    """将刚上传的视频加入配置中指定的 B 站合集。"""
    collections_map = bili_config.get('collections', {})
    target_season_name = collections_map.get(uploader, uploader)

    print(f"[*] 准备将视频加入合集: {target_season_name}")
    manager = BiliCollectionManager()

    # 查找目标合集的分区 ID
    seasons_data = manager.list_seasons()
    target_section_id = None
    for s in seasons_data.get('seasons', []):
        if s['season']['title'] == target_season_name:
            target_section_id = s['sections']['sections'][0]['id']
            break

    if not target_section_id:
        print(f"[!] 找不到名为 '{target_season_name}' 的合集，请在 B 站创作中心先手动创建。")
        return

    # 获取刚上传的视频 aid 和 cid（等待 B 站后台同步）
    time.sleep(3)
    aid = manager.get_recent_archive(safe_title)
    if not aid:
        print("[!] 加入合集失败：未能在最近稿件中找到该视频。")
        return

    v_info = manager.get_video_info(aid)
    cid = v_info['videos'][0]['cid']
    manager.add_to_season(target_section_id, aid, cid, safe_title)
