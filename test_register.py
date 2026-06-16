#!/usr/bin/env python3
"""Claude 注册机快速测试 — 单次注册，保存 sessionKey+cookies，输出到 results/。

用法:
    python test_register.py                  # 单次注册
    python test_register.py --no-proxy       # 不用代理
    python test_register.py --headless       # 无头模式（调试用）
    python test_register.py --count 3        # 连续注册 3 个

输出:
    results/
      cookies_<email>.json
      sessionKeys.txt          # 追加模式，所有 sessionKey 汇总
"""

import sys, os, time, argparse, json
from pathlib import Path

# 确保可以 import 项目模块
sys.path.insert(0, os.path.dirname(__file__))

# Windows 控制台 UTF-8
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def run_once(use_proxy=True):
    """运行一次 Claude 注册，返回 (email, sessionKey, cookies) 或 None"""
    from main import getOneMail, initChrome, get_dom_list, get_ip, generate_random_string
    from chrome_bot.insbot import wait_for_element, wait_for_element_clickable
    from selenium.webdriver.common.by import By
    from cloudflare.gptmail import get_magic_link
    from utils.cookie_utils import CookieManager
    import logging, random

    logger = logging.getLogger(__name__)

    if not use_proxy:
        os.environ["CLAUDE_NO_PROXY"] = "1"

    # 1. 获取邮箱
    print("[1/5] 获取临时邮箱...")
    _mail = getOneMail()
    if not _mail:
        print("  ✗ 获取邮箱失败")
        return None
    print(f"  ✓ {_mail}")

    # 2. 打开浏览器
    print("[2/5] 启动浏览器...")
    _chrome = initChrome(0, 0)
    dom_list = get_dom_list()
    print(f"  当前 URL: {_chrome.current_url}")

    # 3. 填写邮箱
    print("[3/5] 填写注册表单...")
    mailInput = wait_for_element(_chrome, By.XPATH, dom_list["mailInput"], timeout=30)
    if not mailInput:
        print("  ✗ 未找到邮箱输入框（DOM 选择器可能已过期）")
        _chrome.save_screenshot(str(RESULTS_DIR / "error_mailinput.png"))
        return None

    mailInput.send_keys(_mail)
    time.sleep(random.randint(2, 5))

    nextMailButton = wait_for_element_clickable(
        _chrome, By.XPATH, dom_list["nextMailButton"], timeout=30
    )
    if nextMailButton:
        nextMailButton.click()
        print("  ✓ 已提交邮箱")
    else:
        print("  ✗ 未找到提交按钮")
        _chrome.save_screenshot(str(RESULTS_DIR / "error_submit.png"))
        return None

    # 4. 等待 magic link
    print("[4/5] 等待 Claude magic link...")
    time.sleep(3)
    jump_result = get_magic_link(_mail)
    if jump_result.get("type") != "True":
        print(f"  ✗ 未收到 magic link: {jump_result.get('msg')}")
        _chrome.save_screenshot(str(RESULTS_DIR / "error_nomagic.png"))
        return None

    magic_url = jump_result["link"]
    print(f"  ✓ Magic link: {magic_url[:80]}...")
    _chrome.get(magic_url)

    # 5. 后续步骤（勾选条款、保存 sessionKey）
    print("[5/5] 完成注册后续...")
    try:
        jumpPageYears = wait_for_element(_chrome, By.XPATH, dom_list["jumpPageYears"], timeout=30)
        if jumpPageYears:
            cookies = CookieManager.get_all_cookies(_chrome)
            CookieManager.save_cookies(
                cookies,
                file_path=str(RESULTS_DIR / f"cookies_{_mail.replace('@', '_at_')}.json")
            )

            # 提取 sessionKey
            session_key = None
            for c in cookies:
                if c.get("name") == "sessionKey":
                    session_key = c.get("value", "")
                    break

            if session_key:
                # 追加到汇总文件
                with open(RESULTS_DIR / "sessionKeys.txt", "a", encoding="utf-8") as f:
                    f.write(f"{_mail}\t{session_key}\n")
                print(f"  ✓ 注册成功！sessionKey 已保存")
                print(f"    Email: {_mail}")
                print(f"    sessionKey: {session_key[:40]}...")
            else:
                print("  ⚠ 注册完成但未找到 sessionKey cookie")

            _chrome.quit()
            return _mail, session_key, cookies
        else:
            print("  ✗ 跳转后页面加载失败")
            _chrome.save_screenshot(str(RESULTS_DIR / "error_postlogin.png"))
            _chrome.quit()
            return None
    except Exception as e:
        print(f"  ✗ 注册过程异常: {e}")
        _chrome.save_screenshot(str(RESULTS_DIR / "error_exception.png"))
        _chrome.quit()
        return None


def main():
    parser = argparse.ArgumentParser(description="Claude 注册机测试")
    parser.add_argument("--no-proxy", action="store_true", help="不使用代理")
    parser.add_argument("--headless", action="store_true", help="无头模式（不推荐）")
    parser.add_argument("--count", type=int, default=1, help="连续注册数量")
    args = parser.parse_args()

    success = 0
    for i in range(args.count):
        if args.count > 1:
            print(f"\n{'='*50}")
            print(f"第 {i+1}/{args.count} 次注册")
            print(f"{'='*50}\n")

        result = run_once(use_proxy=not args.no_proxy)
        if result:
            success += 1

        if i < args.count - 1:
            wait = 30
            print(f"\n等待 {wait}s 后继续...")
            time.sleep(wait)

    print(f"\n完成: {success}/{args.count} 成功")
    if success:
        print(f"结果保存在: {RESULTS_DIR}")
        print(f"  sessionKeys.txt — 所有 sessionKey 汇总")
        print(f"  cookies_*.json — 各账号 cookie 备份")


if __name__ == "__main__":
    main()
