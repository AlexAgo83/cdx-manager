import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone

from .errors import CdxError


BUNDLE_SCHEMA_VERSION = 1
_SALT_BYTES = 16
_NONCE_BYTES = 16
_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_PBKDF2_ITERATIONS = 200000


def _now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat()


def _b64_encode(data):
    return base64.b64encode(data).decode("ascii")


def _b64_decode(data):
    try:
        return base64.b64decode(data.encode("ascii"))
    except (AttributeError, ValueError, UnicodeEncodeError) as error:
        raise CdxError("Bundle contains invalid base64 data.") from error


def read_bundle_meta(data):
    try:
        wrapper = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CdxError("Invalid bundle format.") from error

    if wrapper.get("schema_version") != BUNDLE_SCHEMA_VERSION:
        raise CdxError("Unsupported bundle schema version.")
    return wrapper


def _derive_keys(passphrase, salt):
    if not passphrase:
        raise CdxError("A non-empty passphrase is required for bundles that include auth data.")
    if isinstance(passphrase, str):
        passphrase = passphrase.encode("utf-8")
    if hasattr(hashlib, "scrypt"):
        key_material = hashlib.scrypt(
            passphrase,
            salt=salt,
            n=_SCRYPT_N,
            r=_SCRYPT_R,
            p=_SCRYPT_P,
            dklen=64,
        )
    else:
        key_material = hashlib.pbkdf2_hmac(
            "sha256",
            passphrase,
            salt,
            _PBKDF2_ITERATIONS,
            dklen=64,
        )
    return key_material[:32], key_material[32:]


def _xor_keystream(data, key, nonce):
    output = bytearray()
    counter = 0
    while len(output) < len(data):
        block = hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest()
        output.extend(block)
        counter += 1
    return bytes(a ^ b for a, b in zip(data, output[:len(data)]))


def encode_bundle(payload, include_auth=False, passphrase=None):
    payload_bytes = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    wrapper = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "bundle_version": 1,
        "created_at": _now_iso(),
        "include_auth": bool(include_auth),
        "encrypted": bool(include_auth),
        "session_names": [item["name"] for item in payload.get("sessions", [])],
    }
    if include_auth:
        salt = os.urandom(_SALT_BYTES)
        nonce = os.urandom(_NONCE_BYTES)
        enc_key, mac_key = _derive_keys(passphrase, salt)
        ciphertext = _xor_keystream(payload_bytes, enc_key, nonce)
        mac = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
        wrapper.update({
            "salt": _b64_encode(salt),
            "nonce": _b64_encode(nonce),
            "hmac_sha256": _b64_encode(mac),
            "payload": _b64_encode(ciphertext),
        })
    else:
        wrapper["payload"] = _b64_encode(payload_bytes)
    return json.dumps(wrapper, indent=2).encode("utf-8")


def decode_bundle(data, passphrase=None):
    wrapper = read_bundle_meta(data)

    encrypted = bool(wrapper.get("encrypted"))
    payload_b64 = wrapper.get("payload")
    if not isinstance(payload_b64, str):
        raise CdxError("Bundle payload is missing.")

    if encrypted:
        salt = _b64_decode(wrapper.get("salt", ""))
        nonce = _b64_decode(wrapper.get("nonce", ""))
        expected_mac = _b64_decode(wrapper.get("hmac_sha256", ""))
        ciphertext = _b64_decode(payload_b64)
        enc_key, mac_key = _derive_keys(passphrase, salt)
        actual_mac = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(actual_mac, expected_mac):
            raise CdxError("Invalid bundle passphrase or corrupted bundle.")
        payload_bytes = _xor_keystream(ciphertext, enc_key, nonce)
    else:
        payload_bytes = _b64_decode(payload_b64)

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CdxError("Bundle payload is corrupt.") from error

    return {"meta": wrapper, "payload": payload}
