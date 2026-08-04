"""Shared utility functions for Hotata Airer integration.

Lives in its own module to avoid the circular import between hub.py and
config_flow.py (hub imports _get_device_list from config_flow; config_flow
imports build_login_body from hub).
"""

from __future__ import annotations

import base64
import hashlib
import time
import uuid
from typing import Any

from cryptography.hazmat.primitives import hashes, padding as sym_padding, serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .const import (
    ACCOUNT_PRIVATE_KEY,
    AES_IV,
    AES_KEY,
    APP_SECRET,
    APP_VERSION_APP,
)

# Pre-load the RSA private key once at module level
_RSA_PRIVATE_KEY = serialization.load_der_private_key(
    base64.b64decode(ACCOUNT_PRIVATE_KEY), password=None
)


def encrypt_password(password: str) -> str:
    """AES-CBC encrypt password, then base64 encode."""
    padder = sym_padding.PKCS7(128).padder()
    padded = padder.update(password.encode()) + padder.finalize()
    encryptor = Cipher(algorithms.AES(AES_KEY), modes.CBC(AES_IV)).encryptor()
    encrypted = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(encrypted).decode()


def build_login_body(values: dict[str, Any]) -> dict[str, Any]:
    """Build login request body with RSA signature."""
    body = {
        **values,
        "appVersion": APP_VERSION_APP,
        "sysVersion": "android_15",
        "traceId": str(uuid.uuid4()),
        "imei": str(uuid.uuid4()),
        "phoneModel": "Home Assistant",
        "timestamp": int(time.time() * 1000),
    }
    plain = "&".join(
        f"{k}={v}"
        for k, v in sorted(body.items())
        if v is not None and not isinstance(v, (list, dict))
    )
    body["sign"] = base64.b64encode(
        _RSA_PRIVATE_KEY.sign(plain.encode(), asym_padding.PKCS1v15(), hashes.SHA256())
    ).decode()
    return body


def generate_sign(payload: dict[str, Any]) -> str:
    """Generate MD5 signature for API request."""
    p = payload.copy()
    p.pop("sign", None)
    arr = []
    for k in sorted(p.keys()):
        v = p[k]
        if v is None or v == "":
            continue
        if isinstance(v, (dict, list)):
            continue
        arr.append(f"{k}={v}")
    raw = "&".join(arr) + APP_SECRET
    return hashlib.md5(raw.encode("utf8")).hexdigest()
