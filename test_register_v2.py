#!/usr/bin/env python3
"""Claude 注册机 — 使用本地 1.json 邮箱池。

用法: python test_register_v2.py
"""

import sys, os, time, argparse, json, random, string
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from cloudflare.filemail import FileMailPool
from chrome_bot import chromeBot
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from utils.cookie_utils import CookieManager
import logging

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

logger = logging.getLogger(__name__)


def run_once(pool, use_proxy=True):
    """运行一次注册。返回 (email, sessionKey, cookies) 或 None"""
    if not use_proxy:
        os.environ["CLAUDE_NO_PROXY"] = "1"

    email_addr, password = pool.acquire()
    if not email_addr:
        print("[✗] 邮箱池已空")
        return None
    print(f"[1/4] 邮箱: {email_addr}")

    try:
        # 读取代理
        proxyip, port = "127.0.0.1", "7897"
        try:
            with open("Proxy.txt") as f:
                line = f.readline().strip()
                if ":" in line:
                    proxyip, port = line.rsplit(":", 1)
        except Exception:
            pass

        # 浏览器
        print(f"[2/4] 启动浏览器 (proxy={proxyip}:{port})...")
        bot = chromeBot()
        chrome = bot.createWebView(proxyip, port)
        chrome.get("https://claude.ai/login")
        chrome.set_window_position(0, 0)

        # 等 React 渲染
        print("  等待页面渲染...")
        time.sleep(5)
        try:
            WebDriverWait(chrome, 30).until(
                lambda d: d.execute_script(
                    "return document.querySelector('input[type=email], input[type=text], button[type=submit]') !== null"
                )
            )
            print("  ✓ 表单已加载")
        except Exception:
            print("  ! 30s 超时，保存截图...")
            chrome.save_screenshot(str(RESULTS_DIR / f"timeout_{email_addr.replace('@','_')}.png"))

        # 填写邮箱
        from chrome_bot.insbot import wait_for_element, wait_for_element_clickable

        # 尝试多个选择器
        email_input = None
        for sel in [
            '//input[@type="email"]',
            '//input[@type="text"]',
            '//input[contains(@placeholder,"mail") or contains(@placeholder,"Email")]',
            '//input',
        ]:
            email_input = wait_for_element(chrome, By.XPATH, sel, timeout=3)
            if email_input:
                break

        if not email_input:
            print("[✗] 未找到邮箱输入框")
            chrome.save_screenshot(str(RESULTS_DIR / f"noinput_{email_addr.replace('@','_')}.png"))
            pool.release(email_addr)
            chrome.quit()
            return None

        email_input.clear()
        email_input.send_keys(email_addr)
        time.sleep(random.randint(2, 4))

        # 找提交按钮
        submit_btn = None
        for sel in [
            '//button[@type="submit"]',
            '//button[contains(text(),"Continue")]',
            '//button[contains(.,"Continue")]',
            '//button',
        ]:
            submit_btn = wait_for_element_clickable(chrome, By.XPATH, sel, timeout=3)
            if submit_btn:
                break

        if submit_btn:
            submit_btn.click()
            print("  ✓ 已点击提交")
        else:
            print("[✗] 未找到提交按钮")
            pool.release(email_addr)
            chrome.quit()
            return None

        # 等待 magic link
        print(f"[3/4] 等待 Claude magic link (IMAP)...")
        result = pool.wait_for_magic_link(email_addr, password, poll_seconds=120)

        if result.get("type") != "True":
            print(f"  ✗ {result.get('msg')}")
            chrome.save_screenshot(str(RESULTS_DIR / f"nomagic_{email_addr.replace('@','_')}.png"))
            pool.release(email_addr)
            chrome.quit()
            return None

        magic_url = result["link"]
        print(f"  ✓ Magic link: {magic_url[:80]}...")
        chrome.get(magic_url)
        time.sleep(5)

        # 保存 cookies + sessionKey
        print("[4/4] 保存结果...")
        cookies = CookieManager.get_all_cookies(chrome)
        fname = email_addr.replace("@", "_at_").replace(".", "_")
        CookieManager.save_cookies(cookies, file_path=str(RESULTS_DIR / f"cookies_{fname}.json"))

        session_key = None
        for c in cookies:
            if c.get("name") == "sessionKey":
                session_key = c.get("value", "")
                break

        if session_key:
            with open(RESULTS_DIR / "sessionKeys.txt", "a", encoding="utf-8") as f:
                f.write(f"{email_addr}\t{session_key}\t{password}\n")
            print(f"  ✓ sessionKey: {session_key[:40]}...")
            pool.mark_used(email_addr)
        else:
            print("  ⚠ 未找到 sessionKey (可能需要额外步骤)")
            pool.release(email_addr)

        chrome.quit()
        return email_addr, session_key, cookies

    except Exception as e:
        print(f"[✗] 异常: {e}")
        import traceback
        traceback.print_exc()
        pool.release(email_addr)
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--no-proxy", action="store_true")
    args = parser.parse_args()

    pool = FileMailPool(
        filepath=os.path.join(os.path.dirname(__file__), "..", "1.json"),
        used_file=str(RESULTS_DIR / "used_emails.json"),
    )
    print(f"邮箱池: {pool.available_count()} 可用 / {len(pool.accounts)} 总数\n")

    success = 0
    for i in range(args.count):
        if args.count > 1:
            print(f"\n{'='*50}\n第 {i+1}/{args.count} 次\n{'='*50}")
        result = run_once(pool, use_proxy=not args.no_proxy)
        if result:
            success += 1
        if i < args.count - 1:
            time.sleep(30)

    print(f"\n完成: {success}/{args.count}")
    print(f"剩余邮箱: {pool.available_count()}")
    if success:
        print(f"结果: {RESULTS_DIR / 'sessionKeys.txt'}")


if __name__ == "__main__":
    main()
