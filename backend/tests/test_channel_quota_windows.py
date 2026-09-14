from datetime import datetime, timezone

from app.schemas.admin import ChannelQuotaResponse, QuotaDetail
from app.services.sync_service import normalize_quota_windows


def test_channel_quota_response_exposes_windows():
    response = ChannelQuotaResponse(
        channel_id="ch_1",
        channel_name="Coding Plan",
        windows=[
            QuotaDetail(
                type="five_hour",
                label="5小时",
                limit=100,
                used=25,
                remain=75,
                percent=25,
                reset_at="2026-09-14T15:00:00Z",
            )
        ],
    )

    assert response.model_dump()["windows"][0]["type"] == "five_hour"


def test_normalize_quota_windows_calculates_remain_percent_and_reset_countdown():
    now = datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc)

    windows = normalize_quota_windows(
        [
            {
                "type": "five_hour",
                "label": "5小时",
                "limit": 100,
                "used": 40,
                "reset_at": "2026-09-14T15:00:00Z",
            },
            {
                "type": "weekly",
                "label": "本周",
                "limit": 1000,
                "remain": 700,
            },
        ],
        now=now,
    )

    assert windows[0]["remain"] == 60
    assert windows[0]["percent"] == 40
    assert windows[0]["reset_in_seconds"] == 18_000
    assert windows[1]["used"] == 300
    assert windows[1]["percent"] == 30


def test_normalize_quota_windows_derives_counts_from_percent_when_provider_omits_counts():
    windows = normalize_quota_windows(
        [
            {
                "type": "five_hour",
                "label": "5小时",
                "limit": 1000,
                "percent": 25,
            }
        ]
    )

    assert windows[0]["used"] == 250
    assert windows[0]["remain"] == 750
