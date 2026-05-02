from pydantic import BaseModel

class Settings(BaseModel):
    mt5_path: str = ''
    auto_connect: bool = False
    price_alerts_path: str = ''
    account_monitoring_interval: int = 5
    volatility_check_interval: int = 60
    overlay_font_size: int = 24
    overlay_font_color: str = "#4ade80"
    overlay_symbols: list[str] = ["XAUUSD", "USDJPY"]
    overlay_width: int = 320
    overlay_height: int = 250
    dingtalk_enabled: bool = False
    dingtalk_token: str = ''
    dingtalk_secret: str = ''
    wecom_enabled: bool = False
    wecom_webhook_url: str = ''
    feishu_enabled: bool = False
    feishu_webhook_url: str = ''
    push_price_alerts: bool = True
    push_volatility_alerts: bool = True
    push_indicator_alerts: bool = True
    theme: str = 'light'
    language: str = 'zh-CN'
    alert_sound_enabled: bool = True
    alert_sound_path: str = ''
    alert_sound_volume: float = 0.5
