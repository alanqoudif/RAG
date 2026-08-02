import pytest
from cryptography.fernet import Fernet

from app.core.encryption import CredentialCipher, DecryptionError


def test_encrypt_decrypt_roundtrip():
    cipher = CredentialCipher(Fernet.generate_key().decode())
    plaintext = "super-secret-database-password"
    ciphertext = cipher.encrypt(plaintext)
    assert ciphertext != plaintext
    assert cipher.decrypt(ciphertext) == plaintext


def test_ciphertext_not_plaintext_substring():
    cipher = CredentialCipher(Fernet.generate_key().decode())
    plaintext = "p@ssw0rd-1234"
    ciphertext = cipher.encrypt(plaintext)
    assert plaintext not in ciphertext


def test_decrypt_with_wrong_key_fails():
    cipher_a = CredentialCipher(Fernet.generate_key().decode())
    cipher_b = CredentialCipher(Fernet.generate_key().decode())
    ciphertext = cipher_a.encrypt("value")
    with pytest.raises(DecryptionError):
        cipher_b.decrypt(ciphertext)


def test_decrypt_garbage_fails():
    cipher = CredentialCipher(Fernet.generate_key().decode())
    with pytest.raises(DecryptionError):
        cipher.decrypt("not-a-valid-fernet-token")
