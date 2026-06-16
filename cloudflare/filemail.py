"""本地文件邮箱池 — 从 1.json 读取 Outlook 账号，每次注册消耗一个。

用法:
    pool = FileMailPool("1.json")
    email, password = pool.acquire()       # 取一个
    code = pool.wait_for_code(email, ...)  # 通过 IMAP 等验证码
    pool.release(email)                    # 失败时归还
    pool.mark_used(email)                  # 成功时标记为已用
"""

import os, re, time, email, imaplib
from pathlib import Path
from bs4 import BeautifulSoup
from email.header import decode_header


class FileMailPool:
    """从本地文件读取账号池"""

    def __init__(self, filepath="1.json", used_file="used_emails.json"):
        self.filepath = Path(filepath)
        self.used_file = Path(used_file)
        self._load()

    def _load(self):
        """加载账号和已用记录"""
        self.accounts = {}
        with open(self.filepath, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split("----")
                if len(parts) >= 2:
                    email = parts[0].strip()
                    password = parts[1].strip()
                    self.accounts[email] = {
                        "password": password,
                        "user_id": parts[2].strip() if len(parts) > 2 else "",
                        "token": parts[3].strip() if len(parts) > 3 else "",
                    }

        import json
        self.used = set()
        if self.used_file.exists():
            try:
                self.used = set(json.loads(self.used_file.read_text()))
            except Exception:
                pass

    def _save_used(self):
        import json
        self.used_file.write_text(json.dumps(list(self.used), ensure_ascii=False))

    def available_count(self):
        return len([e for e in self.accounts if e not in self.used])

    def acquire(self):
        """获取一个未使用的 Outlook 邮箱，返回 (email, password) 或 (None, None)"""
        for email, info in self.accounts.items():
            if email not in self.used:
                self.used.add(email)
                self._save_used()
                return email, info["password"]
        return None, None

    def release(self, email):
        """归还邮箱到池中"""
        self.used.discard(email)
        self._save_used()

    def mark_used(self, email):
        """标记为已成功使用（不归还）"""
        pass  # already in used set

    # ── IMAP 邮件验证码获取 ──
    def wait_for_magic_link(
        self,
        email_address,
        password,
        poll_seconds=90,
        poll_interval=5,
        magic_prefix="https://claude.ai/magic-link",
    ):
        """通过 Outlook IMAP 轮询 Claude magic link"""
        deadline = time.time() + poll_seconds

        # 连接 Outlook IMAP
        conn = imaplib.IMAP4_SSL("outlook.office365.com")
        try:
            conn.login(email_address, password)
        except Exception as e:
            return {"type": "error", "msg": f"IMAP 登录失败: {e}"}

        try:
            while time.time() < deadline:
                conn.select("INBOX", readonly=True)
                # 搜索最近的邮件
                status, data = conn.search(None, "ALL")
                if status != "OK":
                    time.sleep(poll_interval)
                    continue

                msg_ids = data[0].split()
                # 从最新开始查
                for mid in reversed(msg_ids[-10:]):
                    status, msg_data = conn.fetch(mid, "(RFC822)")
                    if status != "OK":
                        continue
                    raw = msg_data[0][1]
                    msg = email.message_from_bytes(raw)
                    subject = str(decode_header(msg["Subject"] or "") or "")

                    # 只查 Claude 相关邮件
                    if not ("claude" in subject.lower() or "log in" in subject.lower() or "anthropic" in subject.lower()):
                        continue

                    # 遍历 MIME parts 找 magic link
                    for part in msg.walk():
                        if part.get_content_type() == "text/html":
                            try:
                                html = part.get_payload(decode=True)
                                if isinstance(html, bytes):
                                    html = html.decode("utf-8", errors="ignore")
                                soup = BeautifulSoup(html, "html.parser")
                                for a in soup.find_all("a"):
                                    href = a.get("href", "")
                                    if magic_prefix in href:
                                        conn.close()
                                        conn.logout()
                                        return {"type": "True", "link": href}
                            except Exception:
                                continue

                        if part.get_content_type() == "text/plain":
                            try:
                                text = part.get_payload(decode=True)
                                if isinstance(text, bytes):
                                    text = text.decode("utf-8", errors="ignore")
                                match = re.search(
                                    r"https://claude\.ai/magic-link[^\s\"'<>]+", text
                                )
                                if match:
                                    conn.close()
                                    conn.logout()
                                    return {"type": "True", "link": match.group(0)}
                            except Exception:
                                continue

                time.sleep(poll_interval)

            return {"type": "error", "msg": f"No magic link after {poll_seconds}s"}
        finally:
            try:
                conn.close()
                conn.logout()
            except Exception:
                pass


# 全局池单例
_pool = None


def get_pool(filepath="1.json"):
    global _pool
    if _pool is None:
        _pool = FileMailPool(filepath)
    return _pool
