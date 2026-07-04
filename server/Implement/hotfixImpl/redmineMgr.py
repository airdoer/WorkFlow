# -*- coding: utf-8 -*-
"""
Redmine 客户端工具

参考自 ue-ci-code/scripts/common_qa_tools/redminemgr.py，按 game-watchman 的需求精简：
- 提供 get_issue / get_all_users 等基础接口
- 提供 extract_issue_ids_from_text 工具，从 P4 提交描述里提取形如 #286063 的 redmine 单号
- 提供 get_qa_kim_usernames：解析 issue.custom_fields 中 QA 字段的 user_id 列表，
  再通过 users.json 的 mail 邮箱前缀作为 Kim username 返回
"""
import json
import re
import logging
from typing import List, Optional, Dict

import requests

logger = logging.getLogger(__name__)


class RedmineMgr(object):
    REDMINE_URL = "https://c7-game-redmine.corp.kuaishou.com/"
    API_KEY = "c7669fcbaacbbd7106ebd2a3da57e9597cfa6b15"
    HEADERS = {
        "Content-Type": "application/json",
        "X-Redmine-API-Key": API_KEY,
    }
    DEFAULT_TIMEOUT = 8

    QA_CUSTOM_FIELD_NAMES = ("QA", "qa", "测试", "测试负责人", "测试人")

    # 进程级缓存：避免在一次冲突检测中反复请求 users.json
    _users_cache: Optional[List[Dict]] = None
    _id_to_user_cache: Dict[int, Dict] = {}

    # ---------------------------------------------------------------- Issue
    def get_issue(self, issue_id) -> Optional[Dict]:
        if not issue_id:
            return None
        url = f"{self.REDMINE_URL}issues/{issue_id}.json"
        params = {"key": self.API_KEY, "include": "watchers"}
        try:
            resp = requests.get(url, params=params, timeout=self.DEFAULT_TIMEOUT)
            if not resp.ok:
                logger.warning(f"RedmineMgr.get_issue({issue_id}) status={resp.status_code}")
                return None
            return resp.json().get("issue")
        except requests.RequestException as e:
            logger.warning(f"RedmineMgr.get_issue({issue_id}) exception: {e}")
            return None

    # ---------------------------------------------------------------- Users
    def get_all_users(self, force: bool = False) -> List[Dict]:
        """获取所有 redmine 用户（带 mail），结果缓存到类变量。"""
        if RedmineMgr._users_cache is not None and not force:
            return RedmineMgr._users_cache

        url = f"{self.REDMINE_URL}users.json"
        params = {"key": self.API_KEY, "limit": 100, "offset": 0}
        users: List[Dict] = []
        try:
            while True:
                resp = requests.get(url, params=params, timeout=self.DEFAULT_TIMEOUT)
                if not resp.ok:
                    logger.warning(f"RedmineMgr.get_all_users status={resp.status_code}")
                    break
                js = resp.json() or {}
                batch = js.get("users") or []
                users.extend(batch)
                total = js.get("total_count") or 0
                params["offset"] = len(users)
                if not batch or len(users) >= total:
                    break
        except requests.RequestException as e:
            logger.warning(f"RedmineMgr.get_all_users exception: {e}")

        RedmineMgr._users_cache = users
        RedmineMgr._id_to_user_cache = {u.get("id"): u for u in users if u.get("id") is not None}
        return users

    def get_user_by_id(self, user_id) -> Optional[Dict]:
        if user_id is None:
            return None
        try:
            user_id = int(user_id)
        except (TypeError, ValueError):
            return None
        if not RedmineMgr._id_to_user_cache:
            self.get_all_users()
        return RedmineMgr._id_to_user_cache.get(user_id)

    @staticmethod
    def mail_prefix(mail: str) -> str:
        if not mail or "@" not in mail:
            return ""
        return mail.split("@", 1)[0].strip()

    # ---------------------------------------------------------------- Helpers
    @staticmethod
    def extract_issue_ids_from_text(text: str) -> List[int]:
        """从一段文本中提取所有 redmine 单号（# 后 5~8 位数字，去重保持顺序）。"""
        if not text:
            return []
        ids = []
        seen = set()
        for m in re.finditer(r"#(\d{5,8})", text):
            i = int(m.group(1))
            if i not in seen:
                seen.add(i)
                ids.append(i)
        return ids

    def _extract_qa_user_ids(self, issue_info: Dict) -> List[int]:
        """从 issue.custom_fields 中找到 QA 字段的 values（user_id 列表）。"""
        if not issue_info:
            return []
        ids: List[int] = []
        for cf in issue_info.get("custom_fields") or []:
            name = cf.get("name") or ""
            if name not in self.QA_CUSTOM_FIELD_NAMES:
                continue
            # values 可能是 list[str] / value 可能是 list[str] 或 str
            raw = cf.get("values")
            if not raw:
                raw = cf.get("value")
            if raw is None:
                continue
            if not isinstance(raw, list):
                raw = [raw]
            for v in raw:
                if v is None or v == "":
                    continue
                try:
                    ids.append(int(v))
                except (TypeError, ValueError):
                    continue
            break
        return ids

    def get_qa_kim_usernames(self, issue_info: Dict) -> List[str]:
        """
        给定 issue 详情，返回 QA 同学的 Kim username（邮箱前缀），可能多个。

        流程：
          1. 从 issue.custom_fields 中找到 QA 字段，拿到 values（user_id 列表）
          2. 通过 get_all_users() 缓存查找用户，取其 mail 字段
          3. 取 mail 的 '@' 之前作为 Kim username 返回
        """
        kim_users: List[str] = []
        for uid in self._extract_qa_user_ids(issue_info):
            user = self.get_user_by_id(uid)
            if not user:
                continue
            prefix = self.mail_prefix(user.get("mail") or "")
            if prefix and prefix not in kim_users:
                kim_users.append(prefix)
        return kim_users

