from python_service.app.models.monitoring import AccountCondition

def evaluate_account(conditions: list[AccountCondition], account_info: dict) -> tuple[list[AccountCondition], list[str]]:
    triggered = []
    messages = []
    
    for cond in conditions:
        if not cond.is_active:
            continue
            
        current_value = account_info.get(cond.metric)
        if current_value is None:
            continue
            
        if cond.direction == 'above' and current_value >= cond.threshold:
            triggered.append(cond)
            messages.append(f"Account {cond.metric} reached {current_value} (Threshold: >= {cond.threshold})")
        elif cond.direction == 'below' and current_value <= cond.threshold:
            triggered.append(cond)
            messages.append(f"Account {cond.metric} reached {current_value} (Threshold: <= {cond.threshold})")
            
    return triggered, messages
