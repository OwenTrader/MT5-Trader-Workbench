from python_service.app.models.alerts import PriceAlert
from python_service.app.services.alert_service import evaluate_alerts
from python_service.app.services.notifier_service import notify_all


async def dispatch_price_alerts(price_rules: list[PriceAlert], current_prices: dict[str, float]) -> None:
    _, messages = evaluate_alerts(price_rules, current_prices)
    for message in messages:
        await notify_all('价格预警触发', message)
