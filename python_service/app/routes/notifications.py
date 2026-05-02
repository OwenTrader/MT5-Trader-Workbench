from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from python_service.app.services.notifier_service import send_windows_notification, send_dingtalk_notification, send_wecom_notification, send_feishu_notification

router = APIRouter()

@router.post("/test")
async def test_notification():
    # send_windows_notification is now a no-op in the backend. 
    # Use frontend-based notifications for testing.
    return {"status": "ok", "message": "Backend notification disabled. Please test via the Frontend (Settings -> Test Playback)."}

@router.post("/test_dingtalk")
async def test_dingtalk_notification():
    result = await send_dingtalk_notification(
        message="这是一条来自交易工作台的钉钉Bot测试消息！"
    )
    return PlainTextResponse(
        result.get("response_body") or "",
        status_code=result.get("status_code", 500),
    )


@router.post("/test_wecom")
async def test_wecom_notification():
    result = await send_wecom_notification(
        message="这是一条来自交易工作台的企业微信 Bot 测试消息！"
    )
    return PlainTextResponse(
        result.get("response_body") or "",
        status_code=result.get("status_code", 500),
    )


@router.post("/test_feishu")
async def test_feishu_notification():
    result = await send_feishu_notification(
        message="这是一条来自交易工作台的飞书 Bot 测试消息！"
    )
    return PlainTextResponse(
        result.get("response_body") or "",
        status_code=result.get("status_code", 500),
    )
