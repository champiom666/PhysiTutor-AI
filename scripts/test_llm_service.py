#!/usr/bin/env python3
"""测试脚本：验证能否成功调用 Gemini API。"""
import socket
import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 强制使用 IPv4，避免在 IPv6 不可达的网络下连接超时
_orig_getaddrinfo = socket.getaddrinfo
def _getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _getaddrinfo_ipv4


def call_gemini_rest(api_key: str, model: str, prompt: str, timeout: int = 60) -> str:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"Content-Type": "application/json", "X-goog-api-key": api_key}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    session = requests.Session()
    retry = Retry(
        total=2,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"],
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))

    resp = session.post(url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    result = resp.json()
    return result["candidates"][0]["content"]["parts"][0]["text"].strip()


def _load_env():
    """从 .env 加载变量到 os.environ（不依赖 python-dotenv）。"""
    import os
    env_file = PROJECT_ROOT / ".env"
    if not env_file.is_file():
        return
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip('"\'')
                if key:
                    os.environ.setdefault(key, value)


def main():
    import os
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass
    if not os.getenv("GEMINI_API_KEY"):
        _load_env()

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model_name = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")

    if not api_key or "your_" in api_key.lower():
        print("Error: GEMINI_API_KEY 未设置或无效，请检查 .env", file=sys.stderr)
        return 1

    timeout_sec = 60
    try:
        text = call_gemini_rest(api_key, model_name, "用10个字描述一个人的性格特点", timeout=timeout_sec)
        print(text)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
