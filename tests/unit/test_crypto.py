"""Unit tests for provider-secret encryption at rest (PRD FR-24).

The rules under test: the derived key is deterministic, the plaintext never appears
in the token, a wrong application key fails loudly (``ValueError``) instead of
silently returning garbage, and no error message contains key material.
"""

from __future__ import annotations

import base64

import pytest
from ega_providers import decrypt_secret, derive_key, encrypt_secret

APP_KEY = "test-application-encryption-key-0001"
OTHER_APP_KEY = "a-completely-different-application-key"
PLAINTEXT = "sk-ant-api03-TestSecretKeyValue-abcdefghijklmnop"


def test_derive_key_is_deterministic_and_urlsafe_base64_of_32_bytes():
    first = derive_key(APP_KEY)
    second = derive_key(APP_KEY)
    assert first == second
    assert base64.urlsafe_b64decode(first) == base64.urlsafe_b64decode(first)
    assert len(base64.urlsafe_b64decode(first)) == 32


def test_derive_key_differs_for_different_application_keys():
    assert derive_key(APP_KEY) != derive_key(OTHER_APP_KEY)


@pytest.mark.parametrize("empty", ["", None])
def test_derive_key_refuses_a_missing_application_key(empty):
    with pytest.raises(ValueError, match="missing or empty"):
        derive_key(empty)


def test_encrypt_then_decrypt_round_trips_the_secret():
    key = derive_key(APP_KEY)
    token = encrypt_secret(PLAINTEXT, key)
    assert decrypt_secret(token, key) == PLAINTEXT


def test_token_is_opaque_and_does_not_contain_the_plaintext():
    key = derive_key(APP_KEY)
    token = encrypt_secret(PLAINTEXT, key)
    assert PLAINTEXT not in token
    assert "TestSecretKeyValue" not in token
    assert token != PLAINTEXT


def test_encrypting_the_same_secret_twice_yields_different_tokens():
    key = derive_key(APP_KEY)
    assert encrypt_secret(PLAINTEXT, key) != encrypt_secret(PLAINTEXT, key)


def test_decrypt_with_the_wrong_application_key_fails_without_leaking_material():
    token = encrypt_secret(PLAINTEXT, derive_key(APP_KEY))
    with pytest.raises(ValueError) as info:
        decrypt_secret(token, derive_key(OTHER_APP_KEY))
    message = str(info.value)
    assert PLAINTEXT not in message
    assert "invalid token or wrong application key" in message


def test_decrypt_rejects_a_tampered_token():
    key = derive_key(APP_KEY)
    token = encrypt_secret(PLAINTEXT, key)
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    with pytest.raises(ValueError):
        decrypt_secret(tampered, key)


def test_encrypt_refuses_empty_input_or_missing_key():
    key = derive_key(APP_KEY)
    with pytest.raises(ValueError, match="empty secret"):
        encrypt_secret("", key)
    with pytest.raises(ValueError, match="Encryption key is missing"):
        encrypt_secret(PLAINTEXT, b"")


def test_decrypt_refuses_empty_input_or_missing_key():
    key = derive_key(APP_KEY)
    with pytest.raises(ValueError, match="empty token"):
        decrypt_secret("", key)
    with pytest.raises(ValueError, match="Encryption key is missing"):
        decrypt_secret("not-a-real-token", b"")


def test_decrypt_rejects_garbage_that_is_not_a_fernet_token():
    with pytest.raises(ValueError):
        decrypt_secret("definitely-not-a-fernet-token", derive_key(APP_KEY))


def test_unicode_secrets_survive_the_round_trip():
    key = derive_key(APP_KEY)
    secret = "clé-secrète-🔐-ünïcode"
    assert decrypt_secret(encrypt_secret(secret, key), key) == secret
