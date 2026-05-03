# test_api.py 用于测试b站的api
import json
from pathlib import Path
from core.collection import BiliCollectionManager

def test_get_video_info():
    print("="*40)
    print("开始测试 B站 API...")
    print("="*40)
    
    # 1. 确保 cookies.json 存在
    cookie_path = Path("configs/cookies.json")
    if not cookie_path.exists() or cookie_path.stat().st_size < 10:
        print("[!] 错误: 未找到有效的 configs/cookies.json，请先确保已通过 biliup login 登录。")
        return

    try:
        # 初始化我们写的合集管理器（它会自动加载 cookie）
        manager = BiliCollectionManager()
        
        # 2. 获取所有的合集列表，顺便测试连接是否通畅
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

        # 3. 测试获取最近的稿件信息（用于测试之前的报错）
        print("\n[*] 正在获取最近上传的稿件信息...")
        # 为了测试，我们直接传一个肯定不存在的名字，让它走完重试逻辑，或者如果你刚上传了视频，把名字填在这里
        test_title = "测试获取稿件" 
        
        # 我们直接调用底层的 API 获取最近 10 个稿件
        r = manager.session.get(
            'https://member.bilibili.com/x/web/archives?status=is_pubing,pubed,not_pubed&pn=1&ps=10',
            timeout=10
        ).json()
        
        if r.get('code') == 0:
            arc_list = r['data'].get('arc_audits', [])
            if arc_list:
                print(f"[*] 获取到最近的稿件:")
                # 取最近的一个稿件进行测试
                latest_arc = arc_list[0]['Archive']
                aid = latest_arc['aid']
                title = latest_arc['title']
                print(f"    - 稿件标题: {title} (aid: {aid})")
                
                print(f"\n[*] 正在测试获取该稿件的详细信息 (aid: {aid})...")
                try:
                    v_info = manager.get_video_info(aid)
                    # 打印一下看看有没有 videos 字段
                    print("[*] 成功获取稿件详情！关键字段如下:")
                    print(f"    - aid: {v_info.get('aid')}")
                    print(f"    - title: {v_info.get('title')}")
                    if 'videos' in v_info and v_info['videos']:
                        print(f"    - cid: {v_info['videos'][0].get('cid')}")
                    else:
                        print("    - [!] 警告: 未找到 videos 字段，完整数据如下:")
                        print(json.dumps(v_info, ensure_ascii=False, indent=2)[:500] + "...")
                        
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
