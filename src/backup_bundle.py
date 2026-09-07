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
_AEAD_NONCE_BYTES = 12
_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_PBKDF2_ITERATIONS = 200000
_AEAD_ALGORITHM = "aes-256-gcm"
_LEGACY_ALGORITHM = "sha256-xor-hmac"
_KDF_SCRYPT = "scrypt"
_KDF_PBKDF2 = "pbkdf2-hmac-sha256"
_SUPPORTED_KDFS = (_KDF_SCRYPT, _KDF_PBKDF2)


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

    if not isinstance(wrapper, dict):
        raise CdxError("Invalid bundle format.")
    if wrapper.get("schema_version") != BUNDLE_SCHEMA_VERSION:
        raise CdxError("Unsupported bundle schema version.")
    return wrapper


def _available_kdf(kdf):
    return kdf != _KDF_SCRYPT or hasattr(hashlib, "scrypt")


def _default_kdf():
    """The strongest KDF this runtime can compute. Recorded in the bundle."""
    return _KDF_SCRYPT if _available_kdf(_KDF_SCRYPT) else _KDF_PBKDF2


def _bundle_kdf_candidates(wrapper):
    """KDFs to try when decoding, in order.

    A recorded KDF is authoritative: the importing runtime's own capabilities
    must not silently select a different derivation, or a portable bundle stops
    decoding after a move between machines. Bundles written before the field was
    honoured record nothing reliable, so those keep the compatibility behaviour
    of trying every KDF this runtime can compute.
    """
    recorded = wrapper.get("kdf")
    if recorded is None:
        default = _default_kdf()
        ordered = [default, *(kdf for kdf in _SUPPORTED_KDFS if kdf != default)]
        return [kdf for kdf in ordered if _available_kdf(kdf)]
    if not isinstance(recorded, str) or recorded not in _SUPPORTED_KDFS:
        raise CdxError("Unsupported bundle key derivation function.")
    return [recorded]


def _derive_key_material(passphrase, salt, kdf):
    if kdf == _KDF_SCRYPT:
        if not _available_kdf(_KDF_SCRYPT):
            raise CdxError(
                "This bundle records the scrypt key derivation function, which this Python runtime "
                "does not provide. Decode it with a Python built against OpenSSL scrypt support."
            )
        return hashlib.scrypt(
            passphrase,
            salt=salt,
            n=_SCRYPT_N,
            r=_SCRYPT_R,
            p=_SCRYPT_P,
            dklen=64,
        )
    if kdf == _KDF_PBKDF2:
        return hashlib.pbkdf2_hmac(
            "sha256",
            passphrase,
            salt,
            _PBKDF2_ITERATIONS,
            dklen=64,
        )
    raise CdxError("Unsupported bundle key derivation function.")


def _derive_keys(passphrase, salt, kdf=None):
    if not passphrase:
        raise CdxError("A non-empty passphrase is required for bundles that include auth data.")
    if isinstance(passphrase, str):
        passphrase = passphrase.encode("utf-8")
    key_material = _derive_key_material(passphrase, salt, kdf or _default_kdf())
    return key_material[:32], key_material[32:]


def _derive_aead_key(passphrase, salt, kdf=None):
    enc_key, _mac_key = _derive_keys(passphrase, salt, kdf)
    return enc_key


def _load_aesgcm():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as error:
        raise CdxError(
            "Auth bundle encryption requires the Python package 'cryptography'. "
            "Install cdx-manager through pipx/uv/pip, or install cryptography for the Python used by cdx."
        ) from error
    return AESGCM


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
    }
    if include_auth:
        salt = os.urandom(_SALT_BYTES)
        nonce = os.urandom(_AEAD_NONCE_BYTES)
        kdf = _default_kdf()
        aesgcm = _load_aesgcm()(_derive_aead_key(passphrase, salt, kdf))
        ciphertext = aesgcm.encrypt(nonce, payload_bytes, None)
        wrapper.update({
            "encryption": _AEAD_ALGORITHM,
            "kdf": kdf,
            "salt": _b64_encode(salt),
            "nonce": _b64_encode(nonce),
            "payload": _b64_encode(ciphertext),
        })
    else:
        wrapper["session_names"] = [item["name"] for item in payload.get("sessions", [])]
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
        ciphertext = _b64_decode(payload_b64)
        algorithm = wrapper.get("encryption") or _LEGACY_ALGORITHM
        kdf_candidates = _bundle_kdf_candidates(wrapper)
        if algorithm == _AEAD_ALGORITHM:
            aead = _load_aesgcm()
            payload_bytes = None
            failure = None
            for kdf in kdf_candidates:
                # Derivation errors are about the bundle, not the passphrase, so
                # they must escape rather than be retried as a bad secret.
                cipher = aead(_derive_aead_key(passphrase, salt, kdf))
                try:
                    payload_bytes = cipher.decrypt(nonce, ciphertext, None)
                    break
                except Exception as error:  # a wrong KDF looks exactly like a wrong passphrase.
                    failure = error
            if payload_bytes is None:
                raise CdxError("Invalid bundle passphrase or corrupted bundle.") from failure
        elif algorithm == _LEGACY_ALGORITHM:
            expected_mac = _b64_decode(wrapper.get("hmac_sha256", ""))
            payload_bytes = None
            for kdf in kdf_candidates:
                enc_key, mac_key = _derive_keys(passphrase, salt, kdf)
                actual_mac = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
                if hmac.compare_digest(actual_mac, expected_mac):
                    payload_bytes = _xor_keystream(ciphertext, enc_key, nonce)
                    break
            if payload_bytes is None:
                raise CdxError("Invalid bundle passphrase or corrupted bundle.")
        else:
            raise CdxError("Unsupported bundle encryption algorithm.")
    else:
        payload_bytes = _b64_decode(payload_b64)

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CdxError("Bundle payload is corrupt.") from error

    return {"meta": wrapper, "payload": payload}
