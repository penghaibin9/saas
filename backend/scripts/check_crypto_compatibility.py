"""Isolated dependency smoke test: public fixtures only, no DB/network/config writes.

The release image must run this command with its installed frozen dependency.
This is not a vulnerability scan or a proof about real customer key availability.
"""
from __future__ import annotations

import base64
import importlib.util
from importlib.metadata import version
import json
from pathlib import Path

EXPECTED_VERSION = "50.0.1"
# Deliberately public NON-PRODUCTION fixture; never used by application config.
PUBLIC_TEST_KEY = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8="
LEGACY_VECTOR = "gAAAAABfXhAA3CVfXU6Ui7Iz8rkxJgvSFI8YaCrplZU58PQf3irQ9ygV0iETmYJlMaindU84FXeE6ynCHIXakeotZadwfafJcOBsByeHR4QAMwmpcDdUqESWeD3Z72YSVb3qEzId4R7o"
PUBLIC_MESSAGE = "PR265 synthetic compatibility only"


def require(condition: bool, code: str) -> None:
    if not condition:
        raise RuntimeError(code)


def check_version() -> None:
    require(version("cryptography") == EXPECTED_VERSION, "CRYPTOGRAPHY_FREEZE_MISMATCH")


def check_fernet() -> None:
    from cryptography.fernet import Fernet, InvalidToken
    cipher = Fernet(PUBLIC_TEST_KEY.encode())
    require(cipher.decrypt(LEGACY_VECTOR.encode()).decode() == PUBLIC_MESSAGE,
            "LEGACY_CIPHERTEXT_INCOMPATIBLE")
    require(cipher.decrypt(cipher.encrypt(PUBLIC_MESSAGE.encode())).decode() == PUBLIC_MESSAGE,
            "FERNET_ROUNDTRIP_FAILED")
    raw = bytearray(base64.urlsafe_b64decode(LEGACY_VECTOR))
    raw[-1] ^= 1
    try:
        cipher.decrypt(base64.urlsafe_b64encode(raw))
    except InvalidToken:
        pass
    else:
        raise RuntimeError("TAMPERED_CIPHERTEXT_ACCEPTED")


def check_application_fields() -> None:
    # Import a private copy, not the installed service module. Override only key
    # suppliers with public test values; do not load .env or access customer keys.
    path = Path(__file__).resolve().parents[1] / "app/core/field_crypto.py"
    spec = importlib.util.spec_from_file_location("_pr265_field_compatibility", path)
    require(spec is not None and spec.loader is not None, "FIELD_MODULE_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    new_public_key = base64.urlsafe_b64encode(bytes(range(32, 64))).decode()
    module._current_key = lambda: ("2", new_public_key)
    module._all_keys = lambda: {"1": PUBLIC_TEST_KEY, "2": new_public_key}
    for stored in (LEGACY_VECTOR, "k1:" + LEGACY_VECTOR):
        require(module.decrypt_field(stored) == PUBLIC_MESSAGE, "FIELD_LEGACY_DECRYPT_FAILED")
    stored = module.encrypt_field(PUBLIC_MESSAGE)
    require(stored.startswith("k2:"), "FIELD_ENVELOPE_CHANGED")
    require(module.decrypt_field(stored) == PUBLIC_MESSAGE, "FIELD_ROUNDTRIP_FAILED")
    # No rewrap is performed on any data store; only synthetic strings in memory.
    rewrapped = module.rewrap("k1:" + LEGACY_VECTOR)
    require(rewrapped.startswith("k2:") and module.decrypt_field(rewrapped) == PUBLIC_MESSAGE,
            "FIELD_IN_MEMORY_REWRAP_FAILED")


def check_mysql_rsa() -> None:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from pymysql import _auth
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private.public_key().public_bytes(serialization.Encoding.PEM,
                                              serialization.PublicFormat.SubjectPublicKeyInfo)
    password, salt = b"synthetic-not-a-login", b"0123456789abcdefghij"
    ciphertext = _auth.sha2_rsa_encrypt(password, salt, public)
    # Match the existing MySQL wire algorithm; this does not select a new policy.
    plain = private.decrypt(ciphertext, padding.OAEP(
        mgf=padding.MGF1(hashes.SHA1()), algorithm=hashes.SHA1(), label=None))
    expected = bytes(byte ^ salt[index % len(salt)] for index, byte in enumerate(password + b"\0"))
    require(plain == expected, "MYSQL_RSA_AUTH_COMPATIBILITY_FAILED")


def main() -> int:
    checks = []
    stage = "installed-version"
    try:
        check_version()
        checks.append(stage)
        for stage, check in (("legacy-fernet-and-tamper", check_fernet),
                             ("application-field-envelopes", check_application_fields),
                             ("pymysql-rsa-auth", check_mysql_rsa)):
            check()
            checks.append(stage)
    except Exception as exc:
        # No raw exception, plaintext, ciphertext, PEM or key material in output.
        print(json.dumps({"cryptoCompatibilityPassed": False, "failedStage": stage,
                          "errorType": type(exc).__name__, "completedChecks": checks,
                          "releaseApproved": False}))
        return 1
    print(json.dumps({"cryptoCompatibilityPassed": True, "cryptographyVersion": EXPECTED_VERSION,
                      "checks": checks, "customerDataAccessed": False, "releaseApproved": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
