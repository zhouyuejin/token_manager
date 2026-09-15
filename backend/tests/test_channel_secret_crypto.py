import json

from app.models.channel import Channel, ChannelType
from app.schemas.admin import ChannelCreate, ChannelUpdate
from app.services.proxy_service import ProxyService
from app.services.secret_crypto import (
    decrypt_secret,
    encrypt_secret,
    is_encrypted_secret,
    mask_secret,
)
from app.api.v1.admin import _channel_response, _encrypt_channel_create, _apply_channel_update


def test_encrypt_secret_round_trip_and_masks():
    encrypted = encrypt_secret("sk-live-secret")

    assert encrypted != "sk-live-secret"
    assert is_encrypted_secret(encrypted)
    assert decrypt_secret(encrypted) == "sk-live-secret"
    assert mask_secret("sk-live-secret") == "sk-liv...cret"


def test_decrypt_secret_keeps_legacy_plaintext_compatible():
    assert decrypt_secret("legacy-key") == "legacy-key"


def test_proxy_pick_key_returns_decrypted_key_pool_members():
    channel = Channel(
        channel_id="ch_1",
        name="OpenAI",
        type=ChannelType.openai,
        endpoint="https://api.example.com",
        api_key=encrypt_secret("sk-main"),
        extra_keys=json.dumps([encrypt_secret("sk-extra")]),
        key_strategy="sequential",
    )

    assert ProxyService(db=None).pick_key(channel) == "sk-main"


def test_channel_create_encrypts_persisted_keys_and_response_masks_them():
    data = ChannelCreate(
        name="OpenAI",
        type="openai",
        endpoint="https://api.example.com",
        api_key="sk-main-secret",
        extra_keys=["sk-extra-secret"],
    )
    values = _encrypt_channel_create(data)

    assert values["api_key"] != "sk-main"
    assert is_encrypted_secret(values["api_key"])
    assert decrypt_secret(values["api_key"]) == "sk-main-secret"
    extra_keys = json.loads(values["extra_keys"])
    assert decrypt_secret(extra_keys[0]) == "sk-extra-secret"

    channel = Channel(
        channel_id="ch_1",
        name=data.name,
        type=ChannelType.openai,
        endpoint=data.endpoint,
        api_key=values["api_key"],
        extra_keys=values["extra_keys"],
        key_strategy="round_robin",
        priority=0,
        timeout=60,
    )
    response = _channel_response(channel)
    assert response.api_key == "sk-mai...cret"
    assert response.extra_keys == ["sk-ext...cret"]


def test_channel_update_empty_key_keeps_existing_and_new_key_reencrypts():
    channel = Channel(
        channel_id="ch_1",
        name="OpenAI",
        type=ChannelType.openai,
        endpoint="https://api.example.com",
        api_key=encrypt_secret("sk-old"),
        extra_keys=json.dumps([encrypt_secret("sk-extra-old")]),
    )

    changed = _apply_channel_update(channel, ChannelUpdate(api_key="", extra_keys=[]))
    assert "api_key" not in changed
    assert decrypt_secret(channel.api_key) == "sk-old"
    assert changed["extra_keys"] is None
    assert channel.extra_keys is None

    changed = _apply_channel_update(channel, ChannelUpdate(api_key="sk-new"))
    assert decrypt_secret(channel.api_key) == "sk-new"
    assert changed["api_key"] == "***"
