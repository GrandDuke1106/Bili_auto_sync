# test_api.py — B 站 API 连通性测试脚本
import json
from pathlib import Path

from core.collection import BiliCollectionManager


def test_get_video_info():
    """测试 B 站创作中心 API 的连通性。

    验证项：
    1. Cookie 是否有效
    2. 合集列表是否能正常获取
    3. 稿件详情是否能正常解析（含 videos 字段检查）
    """
    print("=" * 40)
    print("开始测试 B站 API...")
    print("=" * 40)

    cookie_path = Path("configs/cookies.json")
    if not cookie_path.exists() or cookie_path.stat().st_size < 10:
        print("[!] 错误: 未找到有效的 configs/cookies.json，"
              "请先确保已通过 biliup login 登录。")
        return

    try:
        manager = BiliCollectionManager()

        print("\n[*] 正在获取账号的合集列表...")
        seasons_data = manager.list_seasons()

        seasons = seasons_data.get('seasons', [])
        if not seasons:
            print("[*] 你的账号目前没有任何合集。")
        else:
            print(f"[*] 成功获取到 {len(seasons)} 个合集:")
            for s in seasons:
                title = s['season']['title']
                sid = s['sections']['sections'][0]['id']
                print(f"    - 合集名称: {title} (分区ID: {sid})")

        print("\n[*] 正在获取最近上传的稿件信息...")
        r = manager.session.get(
            'https://member.bilibili.com/x/web/archives'
            '?status=is_pubing,pubed,not_pubed&pn=1&ps=10',
            timeout=10,
        ).json()

        if r.get('code') == 0:
            arc_list = r['data'].get('arc_audits', [])
            if arc_list:
                print("[*] 获取到最近的稿件:")
                latest_arc = arc_list[0]['Archive']
                aid = latest_arc['aid']
                title = latest_arc['title']
                print(f"    - 稿件标题: {title} (aid: {aid})")

                print(f"\n[*] 正在测试获取该稿件的详细信息 (aid: {aid})...")
                try:
                    v_info = manager.get_video_info(aid)
                    print("[*] 成功获取稿件详情！关键字段如下:")
                    print(f"    - aid: {v_info.get('aid')}")
                    print(f"    - title: {v_info.get('title')}")
                    if 'videos' in v_info and v_info['videos']:
                        print(f"    - cid: {v_info['videos'][0].get('cid')}")
                    else:
                        print("    - [!] 警告: 未找到 videos 字段，完整数据如下:")
                        print(json.dumps(v_info, ensure_ascii=False, indent=2)[:500]
                              + "...")
                except Exception as e:
                    print(f"[!] 测试失败: {e}")
            else:
                print("[*] 你的账号最近没有上传任何稿件。")
        else:
            print(f"[!] 获取稿件列表失败: {r}")

    except Exception as e:
        print(f"\n[!] 发生异常: {e}")


if __name__ == "__main__":
    test_get_video_info()
