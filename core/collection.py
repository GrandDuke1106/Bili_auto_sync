# core/collection.py — B 站合集管理 API 封装
import json
import time

import requests

from utils.config_manager import COOKIES_FILE


class BiliCollectionManager:
    """B 站创作中心合集（season）管理。

    支持 cookie 自动加载（兼容 biliup 和 stream-gears 两种格式）、
    合集列表查询、稿件查找、以及将稿件加入指定合集分区。
    """

    def __init__(self):
        self.cookies = {}
        if COOKIES_FILE.exists():
            with open(COOKIES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # stream-gears (Rust) 生成的 cookie 格式
                if 'cookie_info' in data and 'cookies' in data['cookie_info']:
                    for c in data['cookie_info']['cookies']:
                        self.cookies[c['name']] = c['value']
                else:
                    # 老版本 biliup 格式（扁平 key-value）
                    for k, v in data.items():
                        if isinstance(v, str):
                            self.cookies[k] = v

        self.bili_jct = self.cookies.get("bili_jct", "")

        self.session = requests.Session()
        self.session.cookies.update(self.cookies)
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://member.bilibili.com/",
        })

    def list_seasons(self):
        """获取当前账号的所有合集列表。"""
        r = self.session.get(
            'https://member.bilibili.com/x2/creative/web/seasons',
            params={'pn': 1, 'ps': 50, 'order': 'mtime', 'sort': 'desc', 'draft': 1},
            timeout=10,
        ).json()
        if r.get('code') != 0:
            raise Exception(f"获取合集列表失败: {r}")
        return r['data']

    def get_recent_archive(self, title, retries=3):
        """按标题匹配最近上传的稿件，返回其 aid。

        带重试机制，应对 B 站后台数据延迟。
        """
        for _ in range(retries):
            r = self.session.get(
                'https://member.bilibili.com/x/web/archives'
                '?status=is_pubing,pubed,not_pubed&pn=1&ps=10',
                timeout=10,
            ).json()
            if r.get('code') == 0:
                for arc in r['data'].get('arc_audits', []):
                    if arc['Archive']['title'] == title:
                        return arc['Archive']['aid']
            time.sleep(3)
        return None

    def get_video_info(self, aid):
        """获取指定 aid 的稿件详细信息。"""
        r = self.session.get(
            'https://member.bilibili.com/x/vupre/web/archive/view',
            params={'aid': aid},
            timeout=10,
        )
        try:
            res_json = r.json()
        except Exception:
            raise Exception("接口返回了非 JSON 数据（可能是 Cookie 权限不足或被重定向）")

        if res_json.get('code') != 0:
            raise Exception(f"获取视频信息失败: {res_json}")

        return res_json['data']

    def add_to_season(self, section_id, aid, cid, title):
        """将指定稿件加入合集的某个分区。"""
        episodes = [{'aid': aid, 'cid': cid, 'title': title, 'charging_pay': 0}]
        r = self.session.post(
            f'https://member.bilibili.com/x2/creative/web/season/section/episodes/add'
            f'?csrf={self.bili_jct}',
            json={'sectionId': section_id, 'episodes': episodes, 'csrf': self.bili_jct},
            timeout=10,
        ).json()
        if r.get('code') != 0:
            raise Exception(f"添加合集失败: {r}")
        return r
