import httpx
import time
import hmac
import hashlib
import base64
import urllib.parse

# from plyer import notification  # Removed to avoid residual Python tray icons


def _mask_webhook_url(webhook_url: str) -> str:
    if not webhook_url:
        return "<empty>"

    if len(webhook_url) <= 20:
        return webhook_url

    return f"{webhook_url[:12]}***{webhook_url[-6:]}"

def send_windows_notification(title: str, message: str):
    # This is now handled by the frontend (Electron) to avoid Python tray icon issues.
    print(f"Windows notification skipped in backend (moved to frontend): {title} - {message}")

async def send_dingtalk_notification(message: str, token: str = None, secret: str = None):
    """
    Sends a notification to a DingTalk Bot.
    If token/secret are not provided, it tries to fetch from settings.
    """
    if not token:
        from python_service.app.routes.settings import get_settings
        settings = get_settings()
        if not settings.dingtalk_enabled:
            return {
                "ok": False,
                "status_code": 400,
                "response_body": "DingTalk notification skipped: dingtalk bot is disabled",
            }
        token = settings.dingtalk_token
        secret = settings.dingtalk_secret

    if not token:
        return {
            "ok": False,
            "status_code": 400,
            "response_body": "DingTalk notification skipped: access token is missing",
        }

    try:
        timestamp = str(round(time.time() * 1000))
        url = f"https://oapi.dingtalk.com/robot/send?access_token={token}"
        
        if secret:
            secret_enc = secret.encode('utf-8')
            string_to_sign = '{}\n{}'.format(timestamp, secret)
            string_to_sign_enc = string_to_sign.encode('utf-8')
            hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
            sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
            url += f"&timestamp={timestamp}&sign={sign}"

        headers = {'Content-Type': 'application/json'}
        payload = {
            "msgtype": "text",
            "text": {
                "content": f"[Trader Workbench]\n{message}"
            }
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)

        response_body = response.text

        try:
            response_json = response.json()
        except ValueError:
            response_json = None

        ok = response.status_code == 200 and isinstance(response_json, dict) and response_json.get('errcode') == 0
        return {
            "ok": ok,
            "status_code": response.status_code,
            "response_body": response_body,
        }
            
    except Exception as e:
        print(f"DingTalk notification error: {e}")
        return {
            "ok": False,
            "status_code": 502,
            "response_body": f"DingTalk notification error: {e}",
        }


async def send_wecom_notification(message: str, webhook_url: str = None):
    if not webhook_url:
        from python_service.app.routes.settings import get_settings
        settings = get_settings()
        if not settings.wecom_enabled:
            return {
                "ok": False,
                "status_code": 400,
                "response_body": "WeCom notification skipped: wecom bot is disabled",
            }
        webhook_url = settings.wecom_webhook_url

    if not webhook_url:
        return {
            "ok": False,
            "status_code": 400,
            "response_body": "WeCom notification skipped: webhook url is missing",
        }

    try:
        headers = {'Content-Type': 'application/json'}
        payload = {
            "msgtype": "text",
            "text": {
                "content": f"[Trader Workbench]\n{message}"
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=payload, headers=headers)

        response_body = response.text

        try:
            response_json = response.json()
        except ValueError:
            response_json = None

        ok = response.status_code == 200 and isinstance(response_json, dict) and response_json.get('errcode') == 0
        return {
            "ok": ok,
            "status_code": response.status_code,
            "response_body": response_body,
        }

    except Exception as e:
        print(f"WeCom notification error: {e}")
        return {
            "ok": False,
            "status_code": 502,
            "response_body": f"WeCom notification error: {e}",
        }


async def send_feishu_notification(message: str, webhook_url: str = None):
    if not webhook_url:
        from python_service.app.routes.settings import get_settings
        settings = get_settings()
        if not settings.feishu_enabled:
            print("Feishu notification skipped: feishu bot is disabled")
            return {
                "ok": False,
                "status_code": 400,
                "response_body": "Feishu notification skipped: feishu bot is disabled",
            }
        webhook_url = settings.feishu_webhook_url

    if not webhook_url:
        print("Feishu notification skipped: webhook url is missing")
        return {
            "ok": False,
            "status_code": 400,
            "response_body": "Feishu notification skipped: webhook url is missing",
        }

    try:
        headers = {'Content-Type': 'application/json'}
        payload = {
            "msg_type": "text",
            "content": {
                "text": f"[Trader Workbench]\n{message}"
            }
        }

        masked_webhook_url = _mask_webhook_url(webhook_url)
        print(f"Feishu notification: sending message to webhook {masked_webhook_url}")

        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=payload, headers=headers)

        response_body = response.text

        print(f"Feishu notification: HTTP {response.status_code}")
        print(f"Feishu notification: response body {response_body}")

        if response.status_code != 200:
            print("Feishu notification: send failed due to non-200 HTTP status")
            return {
                "ok": False,
                "status_code": response.status_code,
                "response_body": response_body,
            }

        try:
            response_json = response.json()
        except ValueError:
            print("Feishu notification: send failed because response body is not valid JSON")
            return {
                "ok": False,
                "status_code": response.status_code,
                "response_body": response_body,
            }

        response_code = response_json.get("code")
        response_msg = response_json.get("msg")
        print(f"Feishu notification: parsed response code={response_code}, msg={response_msg}")

        if response_code == 0:
            print("Feishu notification: send success")
            return {
                "ok": True,
                "status_code": response.status_code,
                "response_body": response_body,
            }

        print("Feishu notification: send failed")
        return {
            "ok": False,
            "status_code": response.status_code,
            "response_body": response_body,
        }

    except Exception as e:
        print(f"Feishu notification error: {e}")
        return {
            "ok": False,
            "status_code": 502,
            "response_body": f"Feishu notification error: {e}",
        }


async def notify_all(title: str, message: str):
    from python_service.app.routes.settings import get_settings
    settings = get_settings()

    if title == "价格预警触发" and not settings.push_price_alerts:
        return

    if title == "波动预警触发" and not settings.push_volatility_alerts:
        return

    if title == "指标预警触发" and not settings.push_indicator_alerts:
        return

    # send_windows_notification(title, message)  # Moved to frontend for silent/custom sound support
    await send_dingtalk_notification(message)
    await send_wecom_notification(message)
    await send_feishu_notification(message)
