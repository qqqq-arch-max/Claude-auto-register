"""Claude 注册页面 DOM 探测工具。

用法: python discover_dom.py

打开 Claude 登录页面，等 10 秒让用户手动完成 Cloudflare challenge（如果有），
然后自动扫描页面所有 input/button/链接，生成 domList.json。
"""
import time, json, sys, os
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from chrome_bot import chromeBot
from selenium.webdriver.common.by import By


def discover():
    bot = chromeBot()

    # Read proxy
    proxyip, port = "127.0.0.1", "7897"
    try:
        with open("Proxy.txt") as f:
            line = f.readline().strip()
            if ":" in line:
                proxyip, port = line.rsplit(":", 1)
    except Exception:
        pass

    print(f"代理: {proxyip}:{port}")
    print("启动浏览器...")
    chrome = bot.createWebView(proxyip, port)
    chrome.get("https://claude.ai/login")
    chrome.set_window_position(0, 0)

    print("\n" + "=" * 60)
    print("请在浏览器窗口中完成以下操作:")
    print("  1. 等页面完全加载")
    print("  2. 如果有 Cloudflare 验证，手动通过")
    print("  3. 确保看到 Claude 登录表单")
    print("=" * 60)
    print("\n等待 15 秒，然后自动扫描...")
    time.sleep(15)

    # 用 JS 扫描所有交互元素
    print("\n扫描页面元素...")
    elements = chrome.execute_script("""
        const result = {inputs: [], buttons: [], links: [], checkboxes: []};

        document.querySelectorAll('input').forEach(el => {
            result.inputs.push({
                tag: 'input',
                type: el.type || 'text',
                name: el.name || '',
                id: el.id || '',
                placeholder: el.placeholder || '',
                autocomplete: el.autocomplete || '',
                aria_label: el.getAttribute('aria-label') || '',
                xpath_simple: el.type ? `//input[@type='${el.type}']` : '//input',
                xpath_id: el.id ? `//input[@id='${el.id}']` : '',
                xpath_name: el.name ? `//input[@name='${el.name}']` : '',
            });
        });

        document.querySelectorAll('button, [role="button"]').forEach(el => {
            const text = (el.textContent || '').trim().slice(0, 50);
            result.buttons.push({
                tag: el.tagName,
                type: el.type || '',
                text: text,
                id: el.id || '',
                aria_label: el.getAttribute('aria-label') || '',
                xpath_text: text ? `//button[contains(text(),'${text.slice(0, 15)}')]` : '',
            });
        });

        document.querySelectorAll('a[href]').forEach(el => {
            const href = el.getAttribute('href') || '';
            if (href.includes('magic') || href.includes('login') || href.includes('sign')) {
                result.links.push({text: el.textContent?.trim()?.slice(0, 50), href: href});
            }
        });

        document.querySelectorAll('input[type="checkbox"]').forEach(el => {
            result.checkboxes.push({id: el.id, name: el.name});
        });

        return result;
    """)

    print(f"\n📋 Input 元素 ({len(elements['inputs'])}):")
    for inp in elements['inputs']:
        print(f"  type={inp['type']:8s}  placeholder={inp['placeholder'][:30]:30s}  id={inp['id'][:20]:20s}  name={inp['name'][:15]}")

    print(f"\n🔘 Button 元素 ({len(elements['buttons'])}):")
    for btn in elements['buttons']:
        print(f"  text={btn['text'][:40]:40s}  type={btn['type']:8s}  id={btn['id']}")

    print(f"\n🔗 Magic/Login 链接 ({len(elements['links'])}):")
    for link in elements['links']:
        print(f"  {link['text'][:40]} → {link['href'][:80]}")

    print(f"\n☑ Checkbox ({len(elements['checkboxes'])}):")
    for cb in elements['checkboxes']:
        print(f"  id={cb['id']}  name={cb['name']}")

    # 保存到文件
    output = {
        "_comment": "自动生成的 DOM 选择器，可手动调整后替换 domList.json",
        "_scanned_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "_url": chrome.current_url,
    }
    for inp in elements['inputs']:
        key = inp['aria_label'].replace(' ', '_').lower() if inp['aria_label'] else f"input_{inp['type']}"
        if inp['xpath_id']:
            output[f"_{key}"] = inp['xpath_id']
        elif inp['xpath_name']:
            output[f"_{key}"] = inp['xpath_name']

    out_path = Path("logs/dom_discovery.json")
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(elements, f, ensure_ascii=False, indent=2)
    print(f"\n完整结果已保存: {out_path}")

    chrome.quit()
    print("浏览器已关闭。")


if __name__ == "__main__":
    discover()
