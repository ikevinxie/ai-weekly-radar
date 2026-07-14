"""网络请求工具：统一超时、User-Agent、GitHub token 注入。"""
from __future__ import annotations

import json
import os
import ssl
import urllib.request

USER_AGENT = "ai-project-collector/1.0 (weekly personal digest)"
TIMEOUT = 30


def _ssl_context() -> ssl.SSLContext:
    # macOS 的 python.org 发行版默认没有 CA 证书；依次回退 certifi → 系统证书
    cafile = None
    try:
        import certifi
        cafile = certifi.where()
    except ImportError:
        if os.path.exists("/etc/ssl/cert.pem"):
            cafile = "/etc/ssl/cert.pem"
    return ssl.create_default_context(cafile=cafile)


_CTX = _ssl_context()


def fetch_text(url: str, *, headers: dict | None = None) -> str:
    all_headers = {"User-Agent": USER_AGENT}
    if "api.github.com" in url and os.environ.get("GITHUB_TOKEN"):
        all_headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    if headers:
        all_headers.update(headers)
    req = urllib.request.Request(url, headers=all_headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=_CTX) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_json(url: str, *, headers: dict | None = None):
    return json.loads(fetch_text(url, headers=headers))


def post_json(url: str, payload: dict) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=_CTX) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace") or "{}")
