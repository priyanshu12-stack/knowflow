"""Write-only connection secrets (TRD §7 `encrypted_secret_ref`, ADR-006, ADR-000 G-4).

Secrets are encrypted with Fernet (AES-128-CBC + HMAC-SHA256). The key comes from `SECRET_KEY`
or, if unset, from a generated key file under data/ (gitignored). The API never returns a
secret, and logs never contain one.
"""

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings
from app.core.errors import AppError


def _key(settings: Settings) -> bytes:
    configured = settings.secret_key.get_secret_value()
    if configured:
        return configured.encode()
    path: Path = settings.secret_key_file
    if path.is_file():
        return path.read_bytes().strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    # Create with owner-only permissions where the OS supports it.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(key)
    return key


def encrypt(settings: Settings, secret: str) -> str:
    return Fernet(_key(settings)).encrypt(secret.encode()).decode()


def decrypt(settings: Settings, token: str) -> str:
    try:
        return Fernet(_key(settings)).decrypt(token.encode()).decode()
    except (InvalidToken, ValueError) as exc:
        raise AppError(
            "secret_unreadable",
            "The stored connection password can't be decrypted (the secret key changed). "
            "Remove the connection and add it again.",
            409,
        ) from exc
