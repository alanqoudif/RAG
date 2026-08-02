import time

import pytest

from app.core.security import (
    AccessTokenClaims,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.exceptions import UnauthorizedError


def test_password_hash_roundtrip():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed)


def test_password_hash_rejects_wrong_password():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("wrong password", hashed) is False


def test_password_hash_is_salted_and_unique_per_call():
    h1 = hash_password("same-password")
    h2 = hash_password("same-password")
    assert h1 != h2


def test_access_token_roundtrip():
    claims = AccessTokenClaims(
        user_id="11111111-1111-1111-1111-111111111111",
        tenant_id="22222222-2222-2222-2222-222222222222",
        email="user@example.com",
        is_tenant_admin=True,
        roles=["tenant_admin"],
    )
    token = create_access_token(claims)
    decoded = decode_access_token(token)
    assert decoded.user_id == claims.user_id
    assert decoded.tenant_id == claims.tenant_id
    assert decoded.is_tenant_admin is True
    assert decoded.roles == ["tenant_admin"]


def test_decode_rejects_tampered_token():
    claims = AccessTokenClaims(
        user_id="1", tenant_id="2", email="a@b.com", is_tenant_admin=False, roles=[]
    )
    token = create_access_token(claims)
    tampered = token[:-4] + ("A" if token[-4] != "A" else "B") + token[-3:]
    with pytest.raises(UnauthorizedError):
        decode_access_token(tampered)


def test_decode_rejects_expired_token(monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "0")
    get_settings.cache_clear()
    try:
        claims = AccessTokenClaims(
            user_id="1", tenant_id="2", email="a@b.com", is_tenant_admin=False, roles=[]
        )
        token = create_access_token(claims)
        time.sleep(1.2)
        with pytest.raises(UnauthorizedError):
            decode_access_token(token)
    finally:
        monkeypatch.delenv("ACCESS_TOKEN_EXPIRE_MINUTES", raising=False)
        get_settings.cache_clear()
