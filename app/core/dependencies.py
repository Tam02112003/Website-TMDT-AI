from fastapi import Depends, Request
from crud.user import get_current_user
from core.kafka.kafka_client import producer
from datetime import datetime
import json

async def log_activity(request: Request, user: dict = Depends(get_current_user)):
    event_data = {
        "user_id": user.get("id"),
        "user_email": user.get("sub"),
        "action": request.scope['endpoint'].__name__,
        "path": request.url.path,
        "method": request.method,
        "ip_address": request.client.host,
        "timestamp": datetime.now().isoformat(),
    }
    producer.send("user_activity_events", json.dumps(event_data).encode('utf-8'))
    return user
