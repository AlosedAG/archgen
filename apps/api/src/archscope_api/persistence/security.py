"""Passwords, session tokens, and encryption of stored credentials."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from cryptography.fernet import Fernet, InvalidToken

_HASH_PREFIX = "pbkdf2_sha256"
_HASH_ITERATIONS = 600_000


def hash_password(password: str, *, iterations: int = _HASH_ITERATIONS) -> str:
    """``pbkdf2_sha256$<iterations>$<salt>$<hex digest>`` (same format as the legacy app)."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()
    return f"{_HASH_PREFIX}${iterations}${salt}${digest}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored or not stored.startswith(_HASH_PREFIX + "$"):
        return False
    try:
        _, iterations, salt, digest = stored.split("$", 3)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations)).hex()
    except ValueError:
        return False
    return hmac.compare_digest(candidate, digest)


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def token_id(token: str) -> str:
    """What's stored for a session: the token's SHA-256, never the token."""
    return hashlib.sha256(token.encode()).hexdigest()


# Used only when no secret key is configured in local / test environments,
# so development works out of the box. Production refuses to start without one.
_DEV_SECRET = "archscope-local-development-only"


def new_secret_key() -> str:
    return Fernet.generate_key().decode()


class SecretBox:
    """Encrypts / decrypts stored credentials with the server's secret key."""

    def __init__(self, secret_key: str | None):
        if secret_key:
            try:
                self._fernet = Fernet(secret_key.encode())
            except ValueError:
                # Accept any passphrase by deriving a Fernet key from it.
                self._fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret_key.encode()).digest()))
        else:
            self._fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(_DEV_SECRET.encode()).digest()))

    def encrypt(self, plaintext: str) -> bytes:
        return self._fernet.encrypt(plaintext.encode())

    def decrypt(self, ciphertext: bytes) -> str | None:
        """The plaintext, or None if it can't be decrypted (e.g. the key changed)."""
        try:
            return self._fernet.decrypt(ciphertext).decode()
        except InvalidToken:
            return None
