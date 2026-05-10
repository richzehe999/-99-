"""
Webhook notifier template.

Fill in webhook_url in config.enhanced.yaml to enable push notifications.
"""
from __future__ import annotations
import json
import requests


def send_webhook_message(webhook_url: str, title: str, content: str, timeout: int = 8) -> dict:
    if not webhook_url:
        return {"ok": False, "reason": "empty webhook_url"}

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": content,
        },
    }
    resp = requests.post(webhook_url, data=json.dumps(payload), headers={"Content-Type": "application/json"}, timeout=timeout)
    return {"ok": resp.ok, "status_code": resp.status_code, "text": resp.text[:500]}
