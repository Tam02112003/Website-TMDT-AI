from fastapi import Depends, Request
from crud.user import get_current_user
from core.aws.sns_client import sns_client
from datetime import datetime
import json
from core.settings import settings

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
    sns_client.publish_message(
        topic_arn=settings.AWS.SNS_USER_ACTIVITY_TOPIC_ARN,
        message=json.dumps(event_data),
        subject="UserActivity"
    )
    return user
