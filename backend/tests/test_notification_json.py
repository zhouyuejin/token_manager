import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse

from app.api.v1.notifications import notification_to_response
from app.models.notification import Notification, NotificationType
from app.services.notification_service import create_notification


def test_legacy_notification_metadata_is_json_safe():
    notification = Notification(
        notif_id="notif_test", user_id="user_test", type=NotificationType.quota_decrease,
        title="额度已扣减", is_read=0, created_at=datetime(2026, 10, 8),
        extra_data='{"quota_remain": Infinity, "nested": [NaN, -Infinity, 1e999, 42], "label": "Infinity"}',
    )
    expected = {"quota_remain": None, "nested": [None, None, None, 42], "label": "Infinity"}
    response = notification_to_response(notification)
    assert response.metadata == expected
    JSONResponse(jsonable_encoder(response))
    assert notification.to_dict()["metadata"] == expected
    json.dumps(notification.to_dict(), allow_nan=False)


def test_new_notification_metadata_is_json_safe():
    db = MagicMock()
    metadata = {"quota_remain": float("inf"), "nested": [float("nan"), 42]}
    with patch("app.services.notification_service.ws_manager.send_to_user", new_callable=AsyncMock):
        notification = asyncio.run(create_notification(
            db, "user_test", NotificationType.quota_decrease, "额度已扣减", metadata=metadata,
        ))
    assert json.loads(notification.extra_data) == {"quota_remain": None, "nested": [None, 42]}
    json.dumps(json.loads(notification.extra_data), allow_nan=False)


def test_project_growth_notification_uses_project_name_in_response():
    notification = Notification(
        notif_id="notif_project", user_id="user_test", type=NotificationType.system,
        title="项目用量异常增长", is_read=0, created_at=datetime(2026, 10, 8),
        content="项目 project_99e513332f29f089 最近 1 小时消费 $0.02406270，约为历史小时均值的 4.1 倍。",
        extra_data='{"kind":"project_usage_growth","project_id":"project_99e513332f29f089"}',
    )
    response = notification_to_response(notification, {"project_99e513332f29f089": "中文项目"})
    assert response.content == "项目 中文项目 最近 1 小时消费 $0.02406270，约为历史小时均值的 4.1 倍。"
    assert notification_to_response(notification, {}).content == notification.content
