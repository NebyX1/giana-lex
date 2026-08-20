import base64

from cryptography.fernet import Fernet
from flask import current_app


class CredentialCipher:
    def __init__(self, keys_spec: str, active_key_id: str):
        self._keys: dict[str, Fernet] = {}
        self._active_key_id = active_key_id
        if not keys_spec or not active_key_id:
            return
        for pair in keys_spec.split(","):
            pair = pair.strip()
            if not pair:
                continue
            if ":" not in pair:
                continue
            key_id, key_hex = pair.split(":", 1)
            key_id = key_id.strip()
            key_hex = key_hex.strip()
            if not key_id or not key_hex:
                continue
            try:
                fernet_key = base64.urlsafe_b64encode(bytes.fromhex(key_hex))
                self._keys[key_id] = Fernet(fernet_key)
            except (ValueError, Exception):
                continue
        if active_key_id and active_key_id not in self._keys:
            raise RuntimeError(f"Active encryption key '{active_key_id}' not found in CREDENTIAL_ENCRYPTION_KEYS")

    @property
    def active_key_id(self) -> str:
        return self._active_key_id

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        fernet = self._keys.get(self._active_key_id)
        if fernet is None:
            raise RuntimeError("No active encryption key configured")
        return fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

    def decrypt(self, ciphertext: str, key_id: str | None = None) -> str:
        if not ciphertext:
            return ""
        fernet = self._keys.get(key_id or self._active_key_id)
        if fernet is None and self._keys:
            fernet = next(iter(self._keys.values()))
        if fernet is None:
            raise RuntimeError("No decryption key available")
        return fernet.decrypt(ciphertext.encode("ascii")).decode("utf-8")


def get_cipher() -> CredentialCipher:
    cipher = current_app.extensions.get("credential_cipher")
    if cipher is None:
        cipher = CredentialCipher(
            current_app.config["CREDENTIAL_ENCRYPTION_KEYS"],
            current_app.config["CREDENTIAL_ACTIVE_KEY_ID"],
        )
        current_app.extensions["credential_cipher"] = cipher
    return cipher
