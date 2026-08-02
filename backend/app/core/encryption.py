"""Fernet-based symmetric encryption for stored database connection credentials.

Never log or return decrypted values. `ENCRYPTION_KEY` must be a 32-byte urlsafe-base64 key
(generate with `Fernet.generate_key()`); rotate it via a re-encryption migration, not in place.
"""

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings
from app.exceptions import AppError


class DecryptionError(AppError):
    status_code = 500
    code = "DECRYPTION_FAILED"

    def __init__(self, message: str = "Stored credential could not be decrypted."):
        super().__init__(message)


class CredentialCipher:
    def __init__(self, key: str | None = None):
        settings = get_settings()
        self._fernet = Fernet((key or settings.encryption_key).encode())

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise DecryptionError() from exc


_default_cipher: CredentialCipher | None = None


def get_cipher() -> CredentialCipher:
    global _default_cipher
    if _default_cipher is None:
        _default_cipher = CredentialCipher()
    return _default_cipher
