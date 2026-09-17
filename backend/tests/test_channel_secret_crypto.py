import json
import hashlib

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


def test_channel_update_individual_extra_keys_preserves_other_ciphertexts():
    original = [encrypt_secret("sk-first"), encrypt_secret("sk-second"), encrypt_secret("sk-third")]
    channel = Channel(api_key=encrypt_secret("sk-main"), extra_keys=json.dumps(original))
    changed = _apply_channel_update(channel, ChannelUpdate(extra_key_updates={1: "sk-replaced", 2: None}, extra_keys_revision=hashlib.sha256(channel.extra_keys.encode()).hexdigest()))
    keys = json.loads(channel.extra_keys)
    assert keys[0] == original[0]
    assert decrypt_secret(keys[1]) == "sk-replaced"
    assert len(keys) == 2
    assert changed == {"extra_keys": "***"}


def test_channel_update_rejects_invalid_index_without_partial_changes():
    import pytest
    from fastapi import HTTPException
    channel = Channel(api_key=encrypt_secret("sk-main"), extra_keys=json.dumps([encrypt_secret("sk-first")]))
    before = channel.api_key, channel.extra_keys
    with pytest.raises(HTTPException):
        _apply_channel_update(channel, ChannelUpdate(api_key="sk-new", extra_key_updates={5: "sk-replaced"}, extra_keys_revision=hashlib.sha256(channel.extra_keys.encode()).hexdigest()))
    assert (channel.api_key, channel.extra_keys) == before


def test_channel_update_rejects_conflicting_or_masked_item_replacements():
    import pytest
    from fastapi import HTTPException
    channel = Channel(extra_keys=json.dumps([encrypt_secret("sk-first")]))
    before = channel.extra_keys
    for payload in [
        {"extra_keys": [], "extra_key_updates": {0: "sk-new"}},
        {"extra_key_updates": {0: ""}},
        {"extra_key_updates": {0: "sk-old...1234"}},
        {"extra_key_updates": {-1: "sk-new"}},
    ]:
        with pytest.raises(HTTPException):
            _apply_channel_update(channel, ChannelUpdate(**payload, extra_keys_revision=hashlib.sha256(channel.extra_keys.encode()).hexdigest()))
        assert channel.extra_keys == before
    assert _apply_channel_update(channel, ChannelUpdate(extra_key_updates={0: None}, extra_keys_revision=hashlib.sha256(channel.extra_keys.encode()).hexdigest())) == {"extra_keys": None}
    assert channel.extra_keys is None


def test_channel_update_rejects_stale_secret_list_revision():
    import pytest
    from fastapi import HTTPException
    old_keys = json.dumps([encrypt_secret("sk-first"), encrypt_secret("sk-second"), encrypt_secret("sk-third")])
    revision = hashlib.sha256(old_keys.encode()).hexdigest()
    channel = Channel(extra_keys=json.dumps(json.loads(old_keys)[1:]))
    before = channel.extra_keys
    with pytest.raises(HTTPException) as error:
        _apply_channel_update(channel, ChannelUpdate(extra_key_updates={1: None}, extra_keys_revision=revision))
    assert error.value.status_code == 409
    assert channel.extra_keys == before


def test_channel_detail_revision_round_trip_supports_individual_edit(db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.v1.admin import router
    from app.core.database import get_db
    from app.dependencies import require_admin
    from app.models.user import User, UserRole

    channel = Channel(channel_id="revision_round_trip", name="Revision test", type=ChannelType.openai,
                      endpoint="https://api.example.com", api_key=encrypt_secret("sk-main-secret"),
                      extra_keys=json.dumps([encrypt_secret("sk-first-secret"), encrypt_secret("sk-second-secret")]))
    db.add(channel)
    db.commit()
    test_app = FastAPI()
    test_app.include_router(router, prefix="/admin")
    test_app.dependency_overrides[get_db] = lambda: db
    test_app.dependency_overrides[require_admin] = lambda: User(user_id="test_admin", username="Test admin", role=UserRole.admin)
    with TestClient(test_app) as client:
        detail = client.get("/admin/channels/revision_round_trip")
        assert detail.status_code == 200
        revision = detail.json()["extra_keys_revision"]
        assert revision == hashlib.sha256(channel.extra_keys.encode()).hexdigest()
        payload = {"extra_keys_revision": revision, "extra_key_updates": {"1": "sk-replaced-secret"}}
        result = client.put("/admin/channels/revision_round_trip", json=payload)
        assert result.status_code == 200
        keys = json.loads(channel.extra_keys)
        assert [decrypt_secret(key) for key in keys] == ["sk-first-secret", "sk-replaced-secret"]
        assert client.put("/admin/channels/revision_round_trip", json=payload).status_code == 409
