"""gptmail adapter — replaces Cloudflare email and QQ IMAP for Claude register."""
import time, re, requests

API_KEY = "mak_3lthZpyOvD9BfFtrVhcQsiEEBiRY0dTVaaf5wI3rfI"
BASE_URL = "https://gptmail.passkissyou.online"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json; charset=utf-8",
}
POLL_TIMEOUT = 60  # max seconds to wait for magic link
POLL_INTERVAL = 3  # seconds between polls


def create_email_rules(prefix):
    """Reserve an Outlook mailbox from gptmail pool."""
    try:
        resp = requests.post(
            f"{BASE_URL}/api/mailboxes/reserve",
            headers=HEADERS,
            json={
                "category": "safe",
                "keyword": "code,Claude,Anthropic,verification",
                "lease_seconds": 1800,
                "consume": True,
            },
            timeout=15,
        )
        data = resp.json()
        if data.get("ok") and data.get("email"):
            return {"type": "True", "mail": data["email"]}
        return {"type": "error", "msg": data.get("error", "gptmail unavailable")}
    except Exception as e:
        return {"type": "error", "msg": str(e)}


def get_magic_link(email_address, poll_seconds=POLL_TIMEOUT):
    """Poll gptmail API for Claude magic link sent to the email.

    Returns: {"type": "True", "link": "https://claude.ai/magic-link#..."}
             or {"type": "error", "msg": "..."}
    """
    deadline = time.time() + poll_seconds
    while time.time() < deadline:
        try:
            resp = requests.get(
                f"{BASE_URL}/api/mail/code",
                headers=HEADERS,
                params={
                    "email": email_address,
                    "keyword": "log in,Claude,claude.ai,magic",
                    "folders": "inbox,junk",
                    "limit": 3,
                },
                timeout=15,
            )
            data = resp.json()
        except Exception as e:
            time.sleep(POLL_INTERVAL)
            continue

        if not data.get("ok"):
            time.sleep(POLL_INTERVAL)
            continue

        # Check code field first (for numeric codes)
        code = data.get("code")
        if code:
            return {"type": "True", "link": code}

        # Check raw messages for magic link
        messages = data.get("messages") or data.get("data") or []
        if isinstance(messages, list):
            for msg in messages:
                body = ""
                if isinstance(msg, dict):
                    body = msg.get("body") or msg.get("html") or msg.get("text") or ""
                elif isinstance(msg, str):
                    body = msg
                if body:
                    # Find claude.ai magic link
                    match = re.search(r"https://claude\.ai/magic-link[^\s\"'<>]+", body)
                    if match:
                        return {"type": "True", "link": match.group(0)}

        time.sleep(POLL_INTERVAL)

    return {"type": "error", "msg": f"No magic link found after {poll_seconds}s"}
