"""Encryption at rest for provider secrets (PRD FR-24).

Fernet (AES128-CBC + HMAC) keyed deterministically from the application
encryption key in the environment/secret store:

    key = urlsafe_b64(sha256(app_encryption_key))

Rules honoured here:

* the plaintext secret is never logged, echoed, or embedded in exceptions;
* a missing/empty application key raises :class:`ValueError` — no silent
  fallback to unencrypted storage;
* a token decrypted with the wrong key raises :class:`ValueError`
  (Fernet ``InvalidToken``) without revealing any key material.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


def derive_key(app_encryption_key: str) -> bytes:
    """Derive a 32-byte urlsafe-base64 Fernet key from ``app_encryption_key``.

    Args:
        app_encryption_key: Application key material (``EGA_APP_ENCRYPTION_KEY``).

    Returns:
        urlsafe-b64 encoded key suitable for :class:`cryptography.fernet.Fernet`.

    Raises:
        ValueError: when the application key is missing or empty.
    """
    if not app_encryption_key:
        raise ValueError(
            "Application encryption key is missing or empty; refusing to derive a key."
        )
    digest = hashlib.sha256(app_encryption_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_secret(plaintext: str, key: bytes) -> str:
    """Encrypt ``plaintext`` (a provider API key) into an opaque Fernet token.

    Args:
        plaintext: The secret value. Never logged or included in errors.
        key: Key bytes from :func:`derive_key`.

    Returns:
        Opaque token safe to persist in the database.

    Raises:
        ValueError: when the plaintext or the key is missing/empty.
    """
    if not plaintext:
        raise ValueError("Refusing to encrypt an empty secret.")
    if not key:
        raise ValueError("Encryption key is missing; refusing to encrypt a secret.")
    return Fernet(key).encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(token: str, key: bytes) -> str:
    """Reverse :func:`encrypt_secret`.

    Raises:
        ValueError: when the token or key is missing/empty, or the token was
            produced with a different key. The error never contains the
            plaintext or any key material.
    """
    if not token:
        raise ValueError("Refusing to decrypt an empty token.")
    if not key:
        raise ValueError("Encryption key is missing; refusing to decrypt a token.")
    try:
        return Fernet(key).decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        raise ValueError(
            "Secret token could not be decrypted: invalid token or wrong application key."
        ) from None
