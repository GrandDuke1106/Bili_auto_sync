# core/collection.py
import json
import time
import requests
from utils.config_manager import COOKIES_FILE

class BiliCollectionManager:
    def __init__(self):
        self.cookies = {}
        if COOKIES_FILE.exists():
            with open(COOKIES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 兼容 stream-gears (Rust) 生成的最新版 cookie 格式
                if 'cookie_info' in data and 'cookies' in data['cookie_info']:
                    for c in data['cookie_info']['cookies']:
                        self.cookies[c['name']] = c['value']
                else:
                    # 兼容老版本格式
                    for k, v in data.items():
                        if isinstance(v, str): self.cookies[k] = v
                        
        self.bili_jct = self.cookies.get("bili_jct", "")
        
        self.session = requests.Session()
        self.session.cookies.update(self.cookies)
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://member.bilibili.com/"
        })

    def list_seasons(self):
        """获取UP主所有的合集列表"""
        r = self.session.get(
            'https://member.bilibili.com/x2/creative/web/seasons',
            params={'pn': 1, 'ps': 50, 'order': 'mtime', 'sort': 'desc', 'draft': 1},
            timeout=10
        ).json()
        if r.get('code') != 0:
            raise Exception(f"获取合集列表失败: {r}")
        return r['data']

    def get_recent_archive(self, title, retries=3):
        """获取最近上传稿件的 aid（带重试机制以防B站数据延迟）"""
        for _ in range(retries):
            r = self.session.get(
                'https://member.bilibili.com/x/web/archives?status=is_pubing,pubed,not_pubed&pn=1&ps=10',
                timeout=10
            ).json()
            if r.get('code') == 0:
                for arc in r['data'].get('arc_audits', []):
                    # 匹配刚刚上传的视频标题
                    if arc['Archive']['title'] == title:
                        return arc['Archive']['aid']
            time.sleep(3)
        return None

    def get_video_info(self, aid):
        """获取视频信息（带防崩溃和真实错误打印）"""
        # 注意这里的 URL：带 vupre 前缀，这是目前创作中心编辑稿件时用的真实内部接口
        url = 'https://member.bilibili.com/x/vupre/web/archive/view'
        
        r = self.session.get(url, params={'aid': aid}, timeout=10)
        
        try:
            res_json = r.json()
        except Exception:
            #print(f"\n[!] B站接口未返回JSON数据，原始内容前500个字符如下:")
            #print(r.text[:500])
            #print("-" * 40)
            raise Exception("接口返回了非JSON数据(可能是Cookie权限不足或被重定向)")
            
        if res_json.get('code') != 0:
            raise Exception(f"获取视频信息失败: {res_json}")
            
        return res_json['data']
        

    def add_to_season(self, section_id, aid, cid, title):
        """将稿件压入指定的合集分区"""
        episodes = [{'aid': aid, 'cid': cid, 'title': title, 'charging_pay': 0}]
        r = self.session.post(
            f'https://member.bilibili.com/x2/creative/web/season/section/episodes/add?csrf={self.bili_jct}',
            json={'sectionId': section_id, 'episodes': episodes, 'csrf': self.bili_jct},
            timeout=10
        ).json()
        if r.get('code') != 0:
            raise Exception(f"添加合集失败: {r}")
        return r
